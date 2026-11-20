import os
from datetime import datetime
from pathlib import Path


class SessionReport:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        self.path = directory / (
            f"reset_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt"
        )
        self.records = []
        self.finished = False

        self.path.touch(exist_ok=False)

    def _save(self):
        temporary = self.path.with_suffix(".tmp")

        with temporary.open("w", encoding="utf-8") as file:
            for number, record in enumerate(self.records, start=1):
                file.write(
                    f"{number}. {record['model']} "
                    f"name: {record['sysname']} | "
                    f"sn: {record['serial']} | "
                    f"cc: {record['cc']} | "
                    f"pat: {record['pat']} | "
                    f"{record['date']} | "
                    f"{record['status']}\n"
                )

            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary, self.path)

    def add_device(self, model, sysname=None, serial_number = None):
        if self.finished:
            raise RuntimeError("Отчёт уже завершён")

        self.records.append({
            "model": model,
            "sysname": sysname or "Не определен",
            "serial": serial_number,
            "cc": "Не определен",
            "pat": "Не определен",
            "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "status": "Ожидает сброса",
        })
        self._save()
        return len(self.records)

    def add_result(self, device_number, result):
        if self.finished:
            raise RuntimeError("Отчёт уже завершён")

        self.records[device_number - 1]["status"] = result
        self._save()

    def add_software(self, device_number, cc, pat):
        if self.finished:
            raise RuntimeError("Отчёт уже завершён")

        record = self.records[device_number - 1]
        record["cc"] = cc
        record["pat"] = pat

        self._save()

    def finish(self, interrupted=False):
        if self.finished:
            return

        for record in self.records:
            if record["status"] == "Ожидает сброса":
                record["status"] = "Прервано, результат неизвестен"

        self._save()
        self.finished = True