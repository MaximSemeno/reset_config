import re
import time
from pathlib import Path


class DeviceAuth:

    def __init__(self, connection):
        self.connection = connection

    def load_credentials(self):
        project_dir = Path(__file__).resolve().parent.parent

        path = (
            project_dir.parent
            
            / "credentials.txt"
        )

        credentials = []

        with path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.rstrip("\r\n")

                if not line.strip() or line.lstrip().startswith("#"):
                    continue

                if ":" not in line:
                    continue

                username, password = line.split(":", 1)
                credentials.append((username.strip(), password))

        if not credentials:
            raise ValueError("Не найдены учётные данные")

        return credentials

    def wait_for_prompt(self, patterns, timeout=20):
        deadline = time.monotonic() + timeout
        buffer = ""

        while time.monotonic() < deadline:
            output = self.connection.read_output(wait=0.3)

            if output:
                buffer += output
                buffer = buffer[-3000:]

                for name, pattern in patterns.items():
                    if re.search(pattern, buffer, re.IGNORECASE):
                        return name

        return "timeout"

    def login(self):
        credentials = self.load_credentials()

        print(f"[*] Загружено учётных записей: {len(credentials)}")

        for number, (username, _) in enumerate(credentials, 1):
            print(f"{number}. {username} (пароль скрыт)")

        choice = input("\nВыбери номер записи: ").strip()

        if not choice.isdigit():
            print("[!] Некорректный номер")
            return False

        index = int(choice) - 1

        if not 0 <= index < len(credentials):
            print("[!] Такой записи нет")
            return False

        username, password = credentials[index]

        print("[*] Проверяем приглашение консоли...")
        self.connection.send_command("")

        result = self.wait_for_prompt({
            "ready": r"(?:<[^<>\r\n]+>|\[[^\[\]\r\n]+\])\s*$",
            "username": r"(?:Username|Login):\s*$",
            "password": r"Password:\s*$",
        })

        if result == "ready":
            print("[+] Консоль уже авторизована")
            return True

        if result != "username":
            print(f"[!] Неожиданный ответ: {result}")
            return False

        self.connection.send_command(username)

        result = self.wait_for_prompt({
            "password": r"Password:\s*$",
            "failed": r"(?:invalid|incorrect|authentication failed)",
        })

        if result != "password":
            print(f"[!] Не удалось перейти к вводу пароля: {result}")
            return False

        self.connection.send_command(password)

        time.sleep(3)
        result = self.wait_for_prompt({
            "ready": r"(?:<[^<>\r\n]+>|\[[^\[\]\r\n]+\])\s*$",
            "failed": r"(?:invalid|incorrect|authentication fail)",
            "username": r"Username:\s*$",
            "password": r"Password:\s*$",
        })

        if result == "ready":
            print(f"[+] Авторизация успешна: {username}")
            print(f"[+] Подошла запись №{index + 1}")
            return True

        print(f"[!] Авторизация не удалась: {result}")
        return False