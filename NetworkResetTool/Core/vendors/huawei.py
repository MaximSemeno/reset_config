import re
import time

class HuaweiS5720:

    def __init__(self, connection):
        self.connection = connection
        self.model = None
        self.version_output = ""

    def detect(self):
        print("\n[*] Определяем модель устройства...")

        self.connection.send_command("display version")

        output = self.connection.read_output(wait=10)

        self.version_output = output

        # Ищем модель серии S5720
        match = re.search(
            r"\bS5720[\w-]*\b",
            output,
            re.IGNORECASE
        )

        if match:
            self.model = match.group(0).upper()

            print(f"[+] Найдена модель: {self.model}")
            return True

        print("[!] Huawei S5720 не обнаружен")
        print(output)
        return False

    def _wait_response(self, timeout=30):
        import time

        deadline = time.monotonic() + timeout
        output = ""

        while time.monotonic() < deadline:
            chunk = self.connection.read_output(wait=0.3)

            if chunk:
                output += chunk
                print(chunk, end="", flush=True)

                if output.rstrip().endswith(("[Y/N]:", "[Y/N]")):
                    return output

                if "Succeeded in clearing" in output:
                    return output

                if "System is rebooting" in output:
                    return output

                if "Error:" in output:
                    return output

        return output

    def reset(self):
        import re

        if not self.model or not self.model.startswith("S5720"):
            print("[!] Модель S5720 не подтверждена")
            return False

        print(f"\n[!] СБРОС УСТРОЙСТВА: {self.model}")
        print("[!] Сохранённая конфигурация будет удалена")
        print("[!] Устройство перезагрузится")

    

        # Команды сброса выполняются из пользовательского режима
        self.connection.send_command("undo terminal monitor")
        self.connection.read_output(wait=5)

        print("\n[*] Удаляем сохранённую конфигурацию...")
        self.connection.send_command("reset factory-configuration")
        time.sleep(5)
        
        output = self._wait_response()
        

        if not re.search(r"\[Y/N\]\s*:", output, re.I):
            print("\n[!] Не получено подтверждение удаления")
            return False

        
        self.connection.send_command("y")
        output = self._wait_response(timeout=40)

        
        print("\n[+] Сохранённая конфигурация удалена")
        print("[*] Запускаем перезагрузку...")

        self.connection.send_command("y")
        output = self._wait_response(timeout=40)


        