# app/utils.py
"""
Утилитарные функции для всего приложения
"""


def human_size(num, suffix="B"):
    """Конвертирует размер в байтах в человеко-читаемый формат"""
    if num is None:
        return "0 B"

    num = float(num)
    # Проходим по единицам измерения от байтов до эксабайтов
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f} Ei{suffix}"  # Эксабайты если очень большой размер
