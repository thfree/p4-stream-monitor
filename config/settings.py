# config/settings.py

import os

# Настройки логирования

LOGGING = {
    "log_file": os.path.join("logs", "log.log"),
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "level": "DEBUG",  # Можно использовать DEBUG < INFO < WARNING < ERROR < CRITICAL
    "console": True,  # Логировать ли в консоль
    "encoding": "utf-8",
}

# Настройки планировщика
SCHEDULER = {
    "update_interval_hours": 24,  # Интервал автоматического обновления стримов в часах
}
