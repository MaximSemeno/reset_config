import platform

from Core.auth1 import DeviceAuth
from Core.vendors.huawei import HuaweiS5720
from Core.serial_connection import (
    SerialConnection,
    get_available_ports
)





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


def main():
    print("=" * 40)
    print("       NETWORK RESET TOOL v0.2")
    print("=" * 40)

    print(f"Операционная система: {platform.system()}")

    port = select_port()

    if not port:
        print("[!] Порт не выбран")
        return

    device = SerialConnection(port=port)

    try:
        device.connect()

        auth = DeviceAuth(device)

        if not auth.login():
            print("Не удалось войти на оборудование")
            return
        print("Авторизация выполнена успешно ")

        huawei = HuaweiS5720(device)
        if huawei.detect():
            print("Устройство определено. Это Huawei S5720")
            huawei.reset()
        else:
            print("Устройство не определено")

        


       
    except Exception as error:
        print(f"[!] Ошибка: {error}")

    finally:
        device.disconnect()



if __name__ == "__main__":
    main()