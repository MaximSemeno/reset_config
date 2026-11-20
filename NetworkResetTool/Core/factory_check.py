import re
import time
from collections import Counter
from pathlib import Path


ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

MORE = re.compile(
    r"-{2,}[ \t]*More[ \t]*-{2,}",
    re.IGNORECASE,
)

PROMPT = re.compile(
    r"(?:^|\n)[ \t]*<[^<>\r\n]+>[ \t]*$"
)

PHYSICAL_PORT = re.compile(
    r"interface (?:GigabitEthernet|XGigabitEthernet)"
    r"\d+/\d+/\d+$"
)

def clean_terminal(text):
    """Учитываем возврат каретки, Backspace и стирание строки."""
    completed = []
    line = []
    cursor = 0
    position = 0

    while position < len(text):
        char = text[position]

        if char == "\x1b":
            match = ANSI.match(text, position)

            if match:
                sequence = match.group(0)

                if sequence.endswith("K"):
                    mode = sequence[2:-1]

                    if mode in ("", "0"):
                        del line[cursor:]
                    elif mode == "1":
                        for index in range(min(cursor + 1, len(line))):
                            line[index] = " "
                    elif mode == "2":
                        line = []

                position = match.end()
                continue

        if char == "\r":
            cursor = 0

        elif char == "\n":
            completed.append("".join(line).rstrip())
            line = []
            cursor = 0

        elif char == "\x08":
            cursor = max(0, cursor - 1)

        elif char == "\t":
            spaces = 8 - cursor % 8

            for _ in range(spaces):
                if cursor < len(line):
                    line[cursor] = " "
                else:
                    line.append(" ")
                cursor += 1

        elif char >= " ":
            while len(line) < cursor:
                line.append(" ")

            if cursor < len(line):
                line[cursor] = char
            else:
                line.append(char)

            cursor += 1

        position += 1

    completed.append("".join(line).rstrip())
    return "\n".join(completed)

def receive_output(connection, timeout=120):
    output = ""
    pages = 0
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        chunk = connection.read_output(wait=0.3)

        if not chunk:
            continue

        output += chunk

        # Считаем маркеры в исходном потоке, пока они не стёрты.
        raw = ANSI.sub("", output)
        found_pages = len(MORE.findall(raw))

        while pages < found_pages:
            connection.send_raw(" ")
            pages += 1

        # Восстанавливаем видимый текст с правильными отступами.
        clean = clean_terminal(output)
        clean = MORE.sub("", clean)

        if PROMPT.search(clean):
            return clean

    raise TimeoutError("Не получен полный ответ оборудования")


def read_command(connection, command, timeout=120):
    # Получаем свежее приглашение перед отправкой команды.
    connection.send_command("")
    receive_output(connection, timeout=10)

    connection.send_command(command)
    return receive_output(connection, timeout=timeout)


def parse_startup(output):
    fields = {}

    for label, value in re.findall(
        r"^[ \t]*([^:\r\n]+):[ \t]*([^\r\n]*)$",
        output,
        re.MULTILINE,
    ):
        fields[label.strip().lower()] = value.strip()

    required = (
        "startup system software",
        "startup patch package",
        "startup saved-configuration file",
        "next startup saved-configuration file",
    )

    for field in required:
        if not fields.get(field):
            raise ValueError(
                f"В display startup отсутствует поле: {field}"
            )

    return fields


def package_name(value):
    return value.replace("\\", "/").rsplit("/", 1)[-1]


def config_records(text):
    lines = text.replace("\r", "").splitlines()

    if not any(line.strip() == "return" for line in lines):
        raise ValueError(
            "Конфигурация неполная: отсутствует строка return"
        )

    records = Counter()
    context = ""

    for raw in lines:
        line = raw.strip()
        # Эхо команды не является частью конфигурации.
        if line.lower() == "display current-configuration":
            continue

        if not line or line in ("#", "return"):
            if line == "#":
                context = ""
            continue

        if line.startswith("!Software Version"):
            continue

        # Приглашение и эхо команды.
        if re.match(r"^<[^>]+>", line):
            continue

        if not context or not raw[0].isspace():
            context = line

            # Пустые физические порты не сравниваем по количеству.
            # Но любые настройки внутри них учитываем.
            if PHYSICAL_PORT.fullmatch(line):
                continue

            records[(context, "")] += 1

        else:
            # Учитываем наличие пароля консоли,
            # но не сравниваем его защищённое представление.
            if (
                context == "user-interface con 0"
                and line.startswith(
                    "set authentication password cipher "
                )
            ):
                line = (
                    "set authentication password cipher <TEMPORARY>"
                )

            records[(context, line)] += 1

    return records


def hide_secret(text):
    if re.search(
        r"password|secret|community|shared-key",
        text,
        re.IGNORECASE,
    ):
        return text.split()[0] + " <значение скрыто>"

    return text


def compare_config(output, baseline):
    current = config_records(output)
    expected = config_records(baseline)

    differences = []

    for label, records in (
        ("Лишнее или изменено", current - expected),
        ("Отсутствует", expected - current),
    ):
        for (context, line), count in records.items():
            safe_context = hide_secret(context)
            safe_line = hide_secret(line or context)

            differences.append(
                f"{label}: [{safe_context}] "
                f"{safe_line} (x{count})"
            )

    return differences


# Один профиль может обслуживать несколько проверенных версий ПО.
# Добавляем версии только после проверки их заводских настроек.
S5731_S_VERSIONS = {
    "V200R022C10SPC500",
}

# Разрешённые блоки без дополнительных настроек.
EMPTY_BLOCKS = {
    "authentication-profile name default_authen_profile",
    "authentication-profile name dot1x_authen_profile",
    "authentication-profile name dot1xmac_authen_profile",
    "authentication-profile name mac_authen_profile",
    "authentication-profile name multi_authen_profile",
    "authentication-profile name portal_authen_profile",
    "diffserv domain default",
    "radius-server template default",
    "free-rule-template name default_free_rule",
    "portal-access-profile name portal_access_profile",
    "drop-profile default",
    "interface Vlanif1",
    "interface NULL0",
    "user-interface vty 0 4",
    "user-interface vty 16 20",
    "dot1x-access-profile name dot1x_access_profile",
    "mac-access-profile name mac_access_profile",
    "ops",
    "remote-unit",
}

# Разрешённые самостоятельные команды.
ROOT_COMMANDS = {
    "sysname HUAWEI",
    "http server-source -i MEth0/0/1",
    "ssh server-source -i MEth0/0/1",
    "undo icmp name timestamp-request receive",
}

# Разрешённые команды внутри конкретных блоков.
BLOCK_COMMANDS = {
    "pki realm default": {
        "certificate-check none",
    },

    "aaa": {
        "authentication-scheme default",
        "authentication-mode local",
        "authentication-scheme radius",
        "authentication-mode radius",
        "authorization-scheme default",
        "authorization-mode local",
        "accounting-scheme default",
        "accounting-mode none",
        "local-aaa-user password policy administrator",
        "password history record number 0",
        "password expire 0",
        "domain default",
        "authentication-scheme radius",
        "accounting-scheme default",
        "radius-server default",
        "domain default_admin",
        "authentication-scheme default",
    },

    "interface MEth0/0/1": {
        "ip address 192.168.1.253 255.255.255.0",
    },

    "user-interface con 0": {
        "authentication-mode password",
        "set authentication password cipher <TEMPORARY>",
        "user privilege level 15",
    },
}

# Эти команды описывают алгоритмы SSH.
# Конкретный список алгоритмов не используем как признак сброса.
SSH_ALGORITHM_COMMAND = re.compile(
    r"ssh (?:server|client) "
    r"(?:cipher|hmac|key-exchange|publickey) "
    r"[A-Za-z0-9_-]+(?: [A-Za-z0-9_-]+)*"
)

SSH_DH_COMMAND = re.compile(
    r"ssh server dh-exchange min-len \d+"
)


def allowed_root_command(command):
    return (
        command in ROOT_COMMANDS
        or SSH_ALGORITHM_COMMAND.fullmatch(command) is not None
        or SSH_DH_COMMAND.fullmatch(command) is not None
    )


def check_config_rules(output):
    records = config_records(output)
    findings = []

    for (context, command), count in records.items():
        if not command:
            # Заголовок блока или самостоятельная команда.
            allowed = (
                context in EMPTY_BLOCKS
                or context in BLOCK_COMMANDS
                or allowed_root_command(context)
            )
        else:
            # Проверяем команду именно в её блоке.
            allowed = command in BLOCK_COMMANDS.get(context, set())

        if not allowed:
            findings.append(
                "Не предусмотрено профилем: "
                f"[{hide_secret(context)}] "
                f"{hide_secret(command or context)}"
            )

    # Обязательные признаки нашего сценария первого входа.
    required = {
        ("sysname HUAWEI", ""):
            "Имя устройства отличается от HUAWEI",

        ("user-interface con 0", ""):
            "Не найден блок консоли con 0",

        ("user-interface con 0", "authentication-mode password"):
            "Не подтверждена парольная аутентификация консоли",

        (
            "user-interface con 0",
            "set authentication password cipher <TEMPORARY>",
        ):
            "Не найдена строка установленного пароля консоли",
    }

    for record, message in required.items():
        if record not in records:
            findings.append(message)

    return findings


class FactoryCheck:
    def __init__(self, connection, model):
        self.connection = connection
        self.model = model or ""

    def run(self):
        result = {
            "passed": False,
            "status": "Проверка не завершена",
            "cc": "Не определён",
            "pat": "Не определён",
            "details": [],
        }

        try:
            print("[*] Читаем сведения о загрузке...")

            startup_output = read_command(
                self.connection,
                "display startup",
            )

            fields = parse_startup(startup_output)

            result["cc"] = package_name(
                fields["startup system software"]
            )
            result["pat"] = package_name(
                fields["startup patch package"]
            )

            # Профиль относится к S5731-S.
            # На другие семейства автоматически его не переносим.
            if not re.match(
                r"^S5731-S(?:\d|$)",
                self.model.upper(),
            ):
                result["details"].append(
                    f"Нет профиля правил для модели {self.model}"
                )
                return result

            print("[*] Читаем текущую конфигурацию...")

            output = read_command(
                self.connection,
                "display current-configuration",
                timeout=120,
            )

            version_match = re.search(
                r"^!Software Version[ \t]+(\S+)",
                output,
                re.MULTILINE,
            )

            if not version_match:
                result["details"].append(
                    "Не удалось определить версию конфигурации"
                )
                return result

            version = version_match.group(1).upper()

            # Проверяем правила даже на неизвестной версии,
            # но автоматический успех для неё не выдаём.
            findings = check_config_rules(output)

            for field in (
                "startup saved-configuration file",
                "next startup saved-configuration file",
            ):
                if fields[field].upper() != "NULL":
                    findings.append(
                        f"{field}: назначен конфигурационный файл"
                    )

            if version not in S5731_S_VERSIONS:
                result["status"] = "Требуется проверка"
                result["details"] = [
                    f"Профиль ещё не проверен на версии {version}",
                    *findings,
                ]
                return result

            if findings:
                result["status"] = "Требуется проверка"
                result["details"] = findings
                return result

            result["passed"] = True
            result["status"] = "Проверка по правилам пройдена"
            return result

        except (TimeoutError, ValueError) as error:
            # Возвращаем уже прочитанные CC/PAT даже при
            # последующей ошибке получения конфигурации.
            result["details"].append(str(error))
            return result