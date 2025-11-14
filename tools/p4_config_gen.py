# tools/p4_config_gen.py

"""
P4 Config Generator

Скрипт для автоматической генерации YAML конфигурации серверов Perforce из списка хостов.
Выполняет фильтрацию, проверку доступности, устранение дубликатов и форматирование имен.

Основные возможности:
- Чтение списка хостов из текстового файла
- Удаление дубликатов и сортировка
- Проверка доступности хостов (ping)
- Устранение дубликатов по IP адресам
- Автоматическое добавление домена к коротким именам
- Генерация читаемых имен серверов
- Создание YAML конфигурации для мониторинга P4

Использование:
    python p4_config_gen.py input_hosts.txt output_config.yaml [OPTIONS]

Пример:
    python p4_config_gen.py hosts.txt config/servers.yaml -d example.com -u p4admin
"""

import argparse
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

# Добавляем корневую директорию проекта в Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Инициализация логирования
from core.logging import setup_logging

logger = setup_logging()

# Конфигурационные константы
DEFAULT_DOMAIN = "company.com"
DEFAULT_P4USER = "p4monitor"
DEFAULT_STREAM_MASK = "*role*"
DEFAULT_PORT = "1666"
DEFAULT_MAX_WORKERS = 10
DEFAULT_TIMEOUT = 5


def parse_args():
    """
    Парсинг аргументов командной строки.

    Returns:
        argparse.Namespace: Объект с распарсенными аргументами
    """
    parser = argparse.ArgumentParser(
        description="Генератор конфигурации P4 серверов из списка хостов",
        epilog="Пример: python p4_config_gen.py hosts.txt config/servers.yaml -d example.com",
    )
    parser.add_argument(
        "input_file", help="Входной файл со списком хостов (по одному на строку)"
    )
    parser.add_argument(
        "output_file", help="Выходной YAML файл для сохранения конфигурации серверов"
    )
    parser.add_argument(
        "-d",
        "--domain",
        default=DEFAULT_DOMAIN,
        help=f"Домен для добавления к коротким именам хостов (по умолчанию: {DEFAULT_DOMAIN})",
    )
    parser.add_argument(
        "-u",
        "--user",
        default=DEFAULT_P4USER,
        help=f"Имя пользователя P4 для конфигурации (по умолчанию: {DEFAULT_P4USER})",
    )
    parser.add_argument(
        "-m",
        "--stream-mask",
        default=DEFAULT_STREAM_MASK,
        help=f"Маска потоков для фильтрации (по умолчанию: {DEFAULT_STREAM_MASK})",
    )
    parser.add_argument(
        "-p",
        "--port",
        default=DEFAULT_PORT,
        help=f"Порт P4 сервера по умолчанию (по умолчанию: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--no-ping",
        action="store_true",
        help="Пропустить проверку доступности хостов (ping)",
    )
    parser.add_argument(
        "--no-ip-dedup",
        action="store_true",
        help="Пропустить удаление дубликатов по IP адресам",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f"Максимальное количество потоков для параллельной обработки (по умолчанию: {DEFAULT_MAX_WORKERS})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Таймаут проверки доступности хостов в секундах (по умолчанию: {DEFAULT_TIMEOUT})",
    )

    return parser.parse_args()


def read_hosts_file(filename):
    """
    Читает файл с хостами и возвращает очищенный список.

    Args:
        filename (str): Путь к файлу со списком хостов

    Returns:
        list: Список уникальных хостов (без пустых строк)

    Raises:
        SystemExit: Если файл не найден
    """
    try:
        with open(filename, "r") as file:
            hosts = [line.strip() for line in file if line.strip()]
        return hosts
    except FileNotFoundError:
        logger.error(f"Файл {filename} не найден")
        sys.exit(1)


def remove_duplicates_and_sort(hosts):
    """
    Удаляет дубликаты и сортирует список хостов.

    Args:
        hosts (list): Список хостов для обработки

    Returns:
        list: Отсортированный список уникальных хостов
    """
    return sorted(set(hosts))


def ping_host(host, timeout):
    """
    Проверяет доступность хоста с помощью ping команды.

    Args:
        host (str): Имя хоста или IP адрес для проверки
        timeout (int): Таймаут выполнения ping в секундах

    Returns:
        tuple: (host, is_available) - хост и флаг доступности
    """
    try:
        # Определяем параметр ping в зависимости от ОС
        # Для Windows используем '-n 1', для Linux/Mac '-c 1'
        param = "-n" if sys.platform.lower().startswith("win") else "-c"
        result = subprocess.run(
            ["ping", param, "1", host], capture_output=True, text=True, timeout=timeout
        )
        return host, result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return host, False


def check_hosts_availability(hosts, max_workers=10, timeout=5):
    """
    Многопоточная проверка доступности списка хостов.

    Args:
        hosts (list): Список хостов для проверки
        max_workers (int): Максимальное количество параллельных потоков
        timeout (int): Таймаут для каждой проверки

    Returns:
        list: Список доступных хостов
    """
    available_hosts = []

    logger.info("Проверка доступности хостов...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Создаем задачи для каждого хоста
        future_to_host = {
            executor.submit(ping_host, host, timeout): host for host in hosts
        }

        # Обрабатываем завершенные задачи
        for future in as_completed(future_to_host):
            host, is_available = future.result()
            if is_available:
                logger.info(f"✓ {host} - доступен")
                available_hosts.append(host)
            else:
                logger.info(f"✗ {host} - недоступен")

    return available_hosts


def get_real_ip(host):
    """
    Получает реальный IP адрес хоста через DNS запрос.

    Args:
        host (str): Хост в формате hostname[:port]

    Returns:
        tuple: (host, ip) - оригинальный хост и его IP адрес
    """
    try:
        # Извлекаем хост без порта для DNS запроса
        hostname = host.split(":")[0]
        ip = socket.gethostbyname(hostname)
        return host, ip
    except socket.gaierror:
        return host, None


def remove_duplicate_ips(hosts, max_workers=10):
    """
    Удаляет хосты с одинаковыми IP адресами, оставляя первый встреченный.

    Args:
        hosts (list): Список хостов для обработки
        max_workers (int): Количество потоков для параллельного выполнения

    Returns:
        list: Список хостов с уникальными IP адресами
    """
    host_ip_map = {}
    ip_host_map = {}

    logger.info("Получение IP адресов для устранения дубликатов...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_host = {executor.submit(get_real_ip, host): host for host in hosts}

        for future in as_completed(future_to_host):
            host, ip = future.result()
            if ip:
                logger.debug(f"{host} -> {ip}")
                host_ip_map[host] = ip
                # Сохраняем только первый хост для каждого IP
                if ip not in ip_host_map:
                    ip_host_map[ip] = host

    # Возвращаем уникальные хосты (по IP)
    unique_hosts = list(ip_host_map.values())
    logger.info(f"Найдено {len(unique_hosts)} хостов с уникальными IP адресами")
    return unique_hosts


def enhance_p4port(host_port, domain, default_port):
    """
    Добавляет домен к коротким именам хостов для формирования FQDN.

    Примеры:
        - 'est-p4-server1:1666' -> 'est-p4-server1.company.com:1666'
        - 'p4-main.company.com:1666' -> 'p4-main.company.com:1666' (без изменений)
        - 'server01:1666' -> 'server01.company.com:1666'

    Args:
        host_port (str): Хост в формате hostname[:port]
        domain (str): Домен для добавления
        default_port (str): Порт по умолчанию если не указан

    Returns:
        str: Улучшенный хост с FQDN
    """
    try:
        # Разделяем хост и порт
        if ":" in host_port:
            host, port = host_port.split(":", 1)
        else:
            host = host_port
            port = default_port

        # Если хост уже содержит точку (FQDN), оставляем как есть
        if "." in host:
            logger.debug(f"Хост {host} уже содержит FQDN, оставляем без изменений")
            return f"{host}:{port}"
        else:
            # Добавляем домен к короткому имени
            enhanced_host = f"{host}.{domain}"
            enhanced_p4port = f"{enhanced_host}:{port}"
            logger.debug(f"Улучшен хост: {host_port} -> {enhanced_p4port}")
            return enhanced_p4port

    except Exception as e:
        logger.warning(
            f"Ошибка при обработке хоста {host_port}: {e}, оставляем без изменений"
        )
        return host_port


def get_short_hostname(host_port):
    """
    Извлекает короткое имя хоста из строки host:port.

    Примеры:
        - 'est-p4-server1:1666' -> 'est-p4-server1'
        - 'p4-main.company.com:1666' -> 'p4-main'
        - 'server01:1666' -> 'server01'

    Args:
        host_port (str): Хост в формате hostname[:port]

    Returns:
        str: Короткое имя хоста (первая часть до точки)
    """
    # Разделяем хост и порт
    host = host_port.split(":")[0]

    # Извлекаем первую часть до точки (короткое имя)
    short_name = host.split(".")[0]

    return short_name


def format_server_name(short_hostname):
    """
    Форматирует короткое имя хоста в читаемое имя сервера.

    Примеры:
        - 'est-p4-server1' -> 'Est P4 Server1'
        - 'p4-main' -> 'P4 Main'
        - 'server01' -> 'Server01'

    Args:
        short_hostname (str): Короткое имя хоста

    Returns:
        str: Отформатированное читаемое имя сервера
    """
    # Заменяем дефисы и подчеркивания на пробелы
    name_with_spaces = short_hostname.replace("-", " ").replace("_", " ")

    # Разделяем на слова и обрабатываем каждое слово
    words = name_with_spaces.split()
    formatted_words = []

    for word in words:
        # Если слово содержит цифры, оставляем как есть (server01 -> Server01)
        if any(char.isdigit() for char in word):
            # Делаем первую букву заглавной, остальные как есть
            formatted_word = word[0].upper() + word[1:] if word else word
        else:
            # Для слов без цифр (p4 -> P4, main -> Main)
            formatted_word = word.capitalize()

        formatted_words.append(formatted_word)

    return " ".join(formatted_words)


def enhance_hostname_if_needed(host_port, used_names):
    """
    Улучшает имя хоста, если оно слишком короткое или неуникальное.
    Добавляет доменный контекст или числовой суффикс при необходимости.

    Args:
        host_port (str): Хост в формате hostname[:port]
        used_names (set): Множество уже использованных имен

    Returns:
        str: Уникальное и читаемое имя сервера
    """
    short_name = get_short_hostname(host_port)
    base_name = format_server_name(short_name)

    # Если имя слишком общее (одно слово) или уже используется
    if " " not in base_name or base_name in used_names:
        # Добавляем суффикс на основе оригинального хоста
        host = host_port.split(":")[0]

        # Если есть доменная часть, используем её для контекста
        if "." in host:
            domain_parts = host.split(".")[1:]  # все части после первого
            if domain_parts:
                # Берем первую часть домена для контекста
                domain_context = domain_parts[0].capitalize()
                enhanced_name = f"{base_name} {domain_context}"
            else:
                enhanced_name = base_name
        else:
            # Если нет домена, оставляем как есть
            enhanced_name = base_name

        # Если имя все еще неуникальное, добавляем числовой суффикс
        original_name = enhanced_name
        counter = 2
        while enhanced_name in used_names:
            enhanced_name = f"{original_name} {counter}"
            counter += 1
    else:
        enhanced_name = base_name

    used_names.add(enhanced_name)
    return enhanced_name


def process_hosts(args):
    """
    Основной процесс обработки хостов и генерации конфигурации.

    Выполняет последовательно:
    1. Чтение и первичную обработку хостов
    2. Проверку доступности (опционально)
    3. Удаление дубликатов по IP (опционально)
    4. Форматирование имен и портов
    5. Генерацию YAML конфигурации

    Args:
        args (argparse.Namespace): Аргументы командной строки

    Raises:
        SystemExit: При критических ошибках обработки
    """
    try:
        logger.info(f"Начало обработки файла: {args.input_file}")

        # Чтение входного файла
        hosts = read_hosts_file(args.input_file)
        logger.info(f"Прочитано {len(hosts)} хостов из входного файла")

        # Удаление дубликатов и сортировка
        unique_hosts = remove_duplicates_and_sort(hosts)
        duplicates_count = len(hosts) - len(unique_hosts)

        if duplicates_count > 0:
            logger.info(
                f"Удалено {duplicates_count} дубликатов, осталось {len(unique_hosts)} уникальных хостов"
            )
        else:
            logger.info(f"Дубликатов не найдено, {len(unique_hosts)} уникальных хостов")

        # Проверка доступности хостов (опционально)
        if not args.no_ping:
            available_hosts = check_hosts_availability(
                unique_hosts, args.max_workers, args.timeout
            )
            logger.info(f"Доступных хостов: {len(available_hosts)}")

            if not available_hosts:
                logger.error("Нет доступных хостов для обработки")
                return
        else:
            available_hosts = unique_hosts
            logger.info("Проверка доступности отключена")

        # Удаление дубликатов по IP (опционально)
        if not args.no_ip_dedup:
            final_hosts = remove_duplicate_ips(available_hosts, args.max_workers)
            ip_duplicates_count = len(available_hosts) - len(final_hosts)
            if ip_duplicates_count > 0:
                logger.info(f"Удалено {ip_duplicates_count} дубликатов по IP")
            logger.info(f"После удаления дубликатов по IP: {len(final_hosts)}")
        else:
            final_hosts = available_hosts
            logger.info("Удаление дубликатов по IP отключено")

        # Создание структуры данных для YAML
        servers = []
        used_names = set()

        logger.info("Генерация конфигурации серверов...")
        for host in final_hosts:
            # Улучшаем порт (добавляем домен если нужно)
            enhanced_p4port = enhance_p4port(host, args.domain, args.port)

            # Генерируем уникальное читаемое имя
            server_name = enhance_hostname_if_needed(host, used_names)

            server = {
                "name": server_name,
                "p4port": enhanced_p4port,
                "p4user": args.user,
                "stream_mask": args.stream_mask,
            }
            servers.append(server)

            logger.debug(f"Создан сервер: {server_name} -> {enhanced_p4port}")

        config = {"servers": servers}

        # Создаем директорию для выходного файла, если она не существует
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Запись в YAML файл
        with open(args.output_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, indent=2)

        logger.info(f"Успешно обработано {len(final_hosts)} уникальных хостов")
        logger.info(f"Конфигурация сохранена в: {args.output_file}")

        # Логируем итоговый список серверов
        logger.info("Созданные серверы в конфигурации:")
        for server in servers:
            logger.info(f"  - {server['name']}: {server['p4port']}")

    except FileNotFoundError:
        logger.error(f"Файл {args.input_file} не найден")
        sys.exit(1)
    except PermissionError:
        logger.error(
            f"Нет прав доступа к файлу {args.input_file} или {args.output_file}"
        )
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error(f"Ошибка YAML при записи файла: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при обработке файла: {e}", exc_info=True)
        sys.exit(1)


def main():
    """
    Основная функция скрипта.

    Выполняет:
    - Парсинг аргументов командной строки
    - Настройку логирования параметров
    - Запуск основного процесса обработки
    """
    args = parse_args()

    # Логирование параметров запуска
    logger.info("=" * 50)
    logger.info("P4 Config Generator - Запуск обработки")
    logger.info("=" * 50)
    logger.info(f"Входной файл: {args.input_file}")
    logger.info(f"Выходной файл: {args.output_file}")
    logger.info(f"Домен: {args.domain}")
    logger.info(f"Пользователь P4: {args.user}")
    logger.info(f"Маска потоков: {args.stream_mask}")
    logger.info(f"Порт по умолчанию: {args.port}")
    logger.info(f"Проверка доступности: {'отключена' if args.no_ping else 'включена'}")
    logger.info(
        f"Удаление дубликатов по IP: {'отключено' if args.no_ip_dedup else 'включено'}"
    )
    logger.info(f"Максимум потоков: {args.max_workers}")
    logger.info(f"Таймаут: {args.timeout} сек")
    logger.info("=" * 50)

    process_hosts(args)

    logger.info("Скрипт завершил работу успешно")


if __name__ == "__main__":
    main()
