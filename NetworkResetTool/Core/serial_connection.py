import serial
from serial.tools import list_ports
import time


class SerialConnection:
    def __init__(self, port, baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.connection = None

    def connect(self):
        self.connection = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.2,
            write_timeout=2,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False
        )

        print(f"[+] Подключено: {self.port}")

    def send_command(self, command):
        if not self.connection or not self.connection.is_open:
            raise ConnectionError("Нет подключения")

        self.connection.write(
            (command + "\r\n").encode("utf-8")
        )
        self.connection.flush()

    def read_output(self, wait=2):
        if not self.connection or not self.connection.is_open:
            raise ConnectionError("Нет подключения")

        output = bytearray()
        deadline = time.monotonic() + wait

        while time.monotonic() < deadline:
            count = self.connection.in_waiting

            if count:
                output.extend(self.connection.read(count))
            else:
                time.sleep(0.05)

        return output.decode("utf-8", errors="replace")

    def disconnect(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
            print("[+] Соединение закрыто")


def get_available_ports():
    return list(list_ports.comports())