import re
import time


class HuaweiFirstLogin:
    def __init__(self, connection):
        self.connection = connection
        self.username = "admin"
        self.default_password = "admin@huawei.com"
        self.new_password = "Qq123456"

    def login(self, timeout=600):
        deadline = time.monotonic() + timeout
        buffer = ""
        stage = "start"
        initial_setup = False
        confirmed = False
        actions = 0

        patterns = [
            ("enter", r"(?:Press ENTER to get started\.|"
                      r"Please Press ENTER\.)"),
            ("username", r"Username:\s*"),
            ("change", r"Change now\?\s*\[Y/N\]:\s*"),
            ("old", r"Please enter old password:\s*"),
            ("new", r"Please enter new password:\s*"),
            ("confirm_new", r"Please confirm new password:\s*"),
            ("initial", r"Enter Password:\s*"),
            ("confirm_initial", r"Confirm Password:\s*"),
            ("password", r"(?:^|[\r\n])[ \t]*Password:\s*"),
            ("ready", r"(?:^|[\r\n])[ \t]*<[^<>\r\n]+>[ \t]*"),
        ]

        while time.monotonic() < deadline:
            chunk = self.connection.read_output(wait=0.3)

            if chunk:
                print(chunk, end="", flush=True)
                buffer += chunk

            if re.search(
                r"authentication fail|incorrect password|"
                r"passwords? (?:do not|does not) match|"
                r"password.*(?:too short|too simple|"
                r"does not meet|must contain)",
                buffer,
                re.IGNORECASE
            ):
                raise RuntimeError(
                    "Устройство отклонило вход или новый пароль"
                )

            # Находим ближайший запрос в накопленном ответе.
            matches = []
            for event, pattern in patterns:
                match = re.search(pattern, buffer, re.IGNORECASE)
                if match:
                    matches.append((match.start(), event, match))

            if not matches:
                buffer = buffer[-16000:]
                continue

            _, event, match = min(matches, key=lambda item: item[0])
            before = buffer[:match.start()]
            buffer = buffer[match.end():]

            if event == "ready":
                if not confirmed:
                    raise RuntimeError(
                        "Вход получен без ожидаемой настройки пароля; "
                        "заводское состояние не подтверждено"
                    )
                print("\n[+] Первый вход завершён")
                return True

            if event == "enter":
                if stage not in ("start",):
                    raise RuntimeError(
                        "Сеанс прервался во время настройки пароля"
                    )
                response = ""

            elif event == "username" and stage == "start":
                response = self.username
                stage = "password"

            elif event == "password" and stage == "password":
                response = self.default_password
                stage = "change"

            elif event == "change" and stage == "change":
                response = "y"
                stage = "old"

            elif event == "old" and stage == "old":
                response = self.default_password
                stage = "new"

            elif event == "new" and stage == "new":
                response = self.new_password
                stage = "confirm_new"

            elif event == "initial" and stage == "start":
                initial_setup = bool(re.search(
                    r"initial password is required|"
                    r"configure the login password",
                    before,
                    re.IGNORECASE
                ))
                if not initial_setup:
                    raise RuntimeError(
                        "Неизвестный контекст запроса Enter Password"
                    )
                response = self.new_password
                stage = "confirm_initial"

            elif (
                event == "confirm_new" and stage == "confirm_new"
            ) or (
                event == "confirm_initial"
                and stage == "confirm_initial"
            ):
                response = self.new_password
                confirmed = True
                stage = "ready"

            else:
                raise RuntimeError(
                    f"Неожиданный запрос {event}, этап {stage}"
                )

            actions += 1
            if actions > 12:
                raise RuntimeError("Слишком много запросов входа")

            self.connection.send_command(response)

        raise TimeoutError(
            "Не удалось завершить первый вход за отведённое время"
        )