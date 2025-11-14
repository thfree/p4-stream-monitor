@echo off
setlocal enabledelayedexpansion

:: Получение директории скрипта
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
cd /d "%PROJECT_ROOT%"

:: Чтение версии из файла VERSION
if exist "VERSION" (
    set /p VERSION=<VERSION
    set VERSION=!VERSION: =!
    echo Найдена версия: !VERSION!
) else (
    echo Предупреждение: Файл VERSION не найден, используется версия по умолчанию
    set "VERSION=0.0.0"
)

:: Загрузка переменных окружения из .env файла
if exist ".env" (
    for /f "usebackq delims=" %%i in (".env") do (
        for /f "tokens=1,2 delims===" %%a in ("%%i") do (
            if not "%%a"=="" if not "%%b"=="" (
                set "%%a=%%b"
            )
        )
    )
)

:: Установка значений по умолчанию
if "%TAG%"=="" set "TAG=%VERSION%"
if "%JFROG_USER%"=="" set "JFROG_USER=admin"

:: Экспорт версии
set "VERSION=%VERSION%"

:: Проверка переменных
if "%JFROG_REGISTRY%"=="" (
    echo Ошибка: JFROG_REGISTRY не установлен в .env
    exit /b 1
)
if "%REPOSITORY%"=="" (
    echo Ошибка: REPOSITORY не установлен в .env
    exit /b 1
)
if "%IMAGE_NAME%"=="" (
    echo Ошибка: IMAGE_NAME не установлен в .env
    exit /b 1
)

:: Использование токена из аргумента или переменной
if not "%1"=="" (
    set "JFROG_TOKEN=%1"
)
if "%JFROG_TOKEN%"=="" (
    echo Ошибка: Укажите токен: script.bat ^<токен^> или установите JFROG_TOKEN в .env
    exit /b 1
)

:: Основной процесс
echo Вход в JFrog...
echo %JFROG_TOKEN% | docker login %JFROG_REGISTRY% -u %JFROG_USER% --password-stdin
if errorlevel 1 (
    echo Ошибка: Не удалось войти в JFrog
    exit /b 1
)

echo Сборка образа версии %VERSION%...
docker-compose -f "docker-compose.build.yml" build
if errorlevel 1 (
    echo Ошибка: Сборка образа не удалась
    exit /b 1
)

echo Отправка образа версии %VERSION%...
docker-compose -f "docker-compose.build.yml" push
if errorlevel 1 (
    echo Ошибка: Отправка образа не удалась
    exit /b 1
)

echo Готово: %JFROG_REGISTRY%/%REPOSITORY%/%IMAGE_NAME%:%TAG% (версия: %VERSION%)

endlocal