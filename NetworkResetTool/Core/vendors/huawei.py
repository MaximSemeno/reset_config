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

           
        self.connection.send_command("n")
        
        try:
            self._wait_response (
            expected="[Y/N]",
            timeout=5
        )
        except TimeoutError:
            print ("Не получен вопрос перезагрузки")
            return False
        
            
        
        print("\n[+] Сохранённая конфигурация удалена")
        print("[*] Запускаем перезагрузку...")

        self.connection.send_command("n")

        if self._wait_response(
            expected="System is rebooting",
            timeout=10
        ):
            print("Оборудование перезагружается!")
            return True

        else: 
            print ("Оборудование не ушло на перезагрузку!")
            return False

           