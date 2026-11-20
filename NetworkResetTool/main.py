import platform
import time
import re

from Core.auth1 import DeviceAuth
from Core.vendors.huawei import HuaweiS5720
from Core.serial_connection import (
    SerialConnection,
    get_available_ports
)
from pathlib import Path
from Core.report import SessionReport
from Core.first_login import HuaweiFirstLogin





def select_port():
    ports = get_available_ports()

    print("\nДоступные последовательные порты:")

    if not ports:
        print("[!] Порты автоматически не обнаружены")
        return input("Введите порт вручную: ").strip()

    for number, port in enumerate(ports, start=1):
        print(
            f"{number}. {port.device} "
            f"({port.description})"
        )

    while True:
        choice = input(
            "\nНомер порта или имя порта: "
        ).strip()

        if choice.isdigit():
            number = int(choice)

            if 1 <= number <= len(ports):
                return ports[number - 1].device

        if choice:
            return choice

        print("[!] Выберите порт")


def process_device(port, report):
    connection = SerialConnection(port=port)
    number = None
    result_text = "Прервано"

    try:
        connection.connect()

        auth = DeviceAuth(connection)
        if not auth.login():
            print("[!] Не удалось войти на оборудование")
            return

        device = HuaweiS5720(connection) 

        if not device.detect():
            print("[!] Модель не определена, сброс остановлен")
            return
        if not device.get_sysname():
            print("[!]Sysname не получен, сброс остановлен")
            return
        if not device.get_serial_number():
            print("[!] Серийник не получен, сброс остановлен")
            return

        print(f"Модель: {device.model}")
        print(f"Sysname: {device.sysname}")
        print(f"Серийный номер: {device.serial_number}")

        # Если запись не удалась, до сброса не дойдём.
        number = report.add_device(
            device.model,
            device.sysname,
            device.serial_number
        )

        confirmation = input(
            "Для сброса введи RESET, для пропуска нажми Enter: "
        ).strip()

        if confirmation != "RESET":
            result_text = "Сброс пропущен пользователем"
            return

        

        result_text = "Первый сброс не подтверждён"

        if not device.reset():
            return

        result_text = "Первый сброс запущен, ожидается загрузка"
        report.add_result(number, result_text)

        print("[*] Ждём загрузки и выполняем первый вход...")
        first_login = HuaweiFirstLogin(connection)
        first_login.login(timeout=600)

        result_text = "Первый вход выполнен, проверка не завершена"
        report.add_result(number, result_text)

        # Пока критерии автоматической проверки не определены,
        # выводим конфигурацию для просмотра оператором.
        connection.send_command("display current-configuration")

        output = ""
        deadline = time.monotonic() + 120

        while time.monotonic() < deadline:
            chunk = connection.read_output(wait=0.3)

            if chunk:
                print(chunk, end="", flush=True)
                output += chunk

            if "---- More ----" in output:
                raise RuntimeError(
                    "Вывод остановился на постраничном просмотре. "
                    "Проверка не завершена"
                )

            if re.search(
                r"(?:^|[\r\n])[ \t]*<[^<>\r\n]+>[ \t]*\Z",
                output
            ):
                break
        else:
            raise TimeoutError("Не получен полный вывод конфигурации")

        confirmation = input(
            "\nЕсли конфигурация проверена, введи CHECKED "
            "для повторного сброса: "
        ).strip()

        if confirmation != "CHECKED":
            result_text = (
                "Проверка не подтверждена; временный пароль может остаться"
            )
            return

        result_text = "Проверено оператором, повторный сброс не подтверждён"
        report.add_result(number, result_text)

        if device.reset():
            result_text = "Проверено оператором; повторный сброс запущен"
        else:
            result_text = "Ошибка повторного сброса"
    except OSError:
        # Ошибки порта или записи отчёта завершают сеанс.
        result_text = "Ошибка ввода-вывода, результат неизвестен"
        raise

    except Exception as error:
        result_text = (
            f"Ошибка {type(error).__name__}, "
            "результат сброса неизвестен"
        )
        print(f"[!] {result_text}")

    finally:
        try:
            if number is not None:
                report.add_result(number, result_text)
        finally:
            connection.disconnect()


def ask_next_device():
    while True:
        print("\n1 — Следующий коммутатор")
        print("0 — Завершить сеанс")

        choice = input("Выбор: ").strip()

        if choice == "1":
            return True
        if choice == "0":
            return False

        print("Введи 1 или 0")


def main():
    print("NETWORK RESET TOOL")
    print(f"Операционная система: {platform.system()}")

    reports_dir = Path(__file__).resolve().parent / "reports"

    try:
        report = SessionReport(reports_dir)
    except OSError as error:
        print(f"[!] Не удалось создать отчёт: {error}")
        return

    print(f"[*] Отчёт: {report.path}")
    interrupted = True

    try:
        while True:
            input(
                "\nПодключи один коммутатор консольным кабелем "
                "и нажми Enter..."
            )

            port = select_port()

            if port:
                process_device(port, report)
            else:
                print("[!] Порт не выбран")

            if not ask_next_device():
                break

        interrupted = False

    except (KeyboardInterrupt, EOFError):
        print("\n[!] Работа прервана пользователем")

    except Exception as error:
        print(f"\n[!] Сеанс остановлен: {error}")

    finally:
        try:
            report.finish(interrupted=interrupted)
        except OSError as error:
            print(f"[!] Не удалось записать окончание отчёта: {error}")

        print(f"[*] Файл отчёта: {report.path}")



if __name__ == "__main__":
    main()