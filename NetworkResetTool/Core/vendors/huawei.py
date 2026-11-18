import re
import time

class HuaweiS5720:


    def _wait_response(self, expected, timeout=30):
        deadline = time.monotonic() + timeout
        output = ""

        while time.monotonic() < deadline:
            chunk = self.connection.read_output(wait=0.3)

            if chunk:
                output += chunk
                print(chunk, end="", flush=True)

                if expected in output:
                    return output

        raise TimeoutError(
            f"За {timeout} секунд не получен ответ: {expected!r}"
        )

    def __init__(self, connection):
        self.connection = connection
        self.model = None
        self.version_output = ""
        self.serial_number = None

    def detect(self):
        print("\n[*] Определяем модель устройства...")

        self.connection.send_command("display version")

        output = self.connection.read_output(wait=10)

        self.version_output = output

        # Ищем модель серии S5720
        match = re.search(
            r"\bS57[\w-]*\b",
            output,
            re.IGNORECASE
        )

        if match:
            self.model = match.group(0).upper()

            print(f"[+] Найдена модель: {self.model}")
            return True

        print("[!] Huawei S5720 не обнаружен")
        print(output  )
        return False

    def get_serial_number(self, timeout=15):
        self.serial_number = None
        self.connection.send_command("display esn")

        deadline = time.monotonic() + timeout
        output = ""

        while time.monotonic() < deadline:
            output += self.connection.read_output(wait=0.3)

            match = re.search(
                r"^[ \t]*ESN of slot 0:[ \t]*"
                r"([A-Za-z0-9_-]+)[ \t]*\r?\n",
                output,
                re.MULTILINE | re.IGNORECASE
            )

            if match:
                self.serial_number = match.group(1)
                return True

        return False


    def reset(self):
        import re

        if not self.model or not self.model.startswith("S57"):
            print("[!] Модель не подтверждена")
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
        
        try:
            output = self._wait_response(
                expected="[Y/N]",
                timeout=15
            )
        except TimeoutError:
            print("Не получен вопрос подтверждения сброса")
            return False
        

       
           
        self.connection.send_command("Y")
        
        try:
            self._wait_response (
            expected="[Y/N]",
            timeout=10
        )
        except TimeoutError:
            print ("Не получен вопрос перезагрузки")
            return False
        
            
        
        print("\n[+] Сохранённая конфигурация удалена")
        print("[*] Запускаем перезагрузку...")

        self.connection.send_command("Y")

        try:
            self._wait_response(
            expected="System is rebooting",
            timeout=400
        )
            

        except TimeoutError:
            print ("Оборудование не ушло на перезагрузку!")
            return False
        print("Оборудование перезагружается!")
        return True

               