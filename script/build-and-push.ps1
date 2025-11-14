param(
    [string]$JfrogToken
)

# Получение директории скрипта
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_ROOT = Split-Path -Parent $SCRIPT_DIR
Set-Location $PROJECT_ROOT

# Чтение версии из файла VERSION
$VERSION_FILE = Join-Path $PROJECT_ROOT "VERSION"
if (Test-Path $VERSION_FILE) {
    $VERSION = (Get-Content $VERSION_FILE -Raw).Trim()
    Write-Host "Найдена версия: $VERSION"
} else {
    Write-Host "Предупреждение: Файл VERSION не найден, используется версия по умолчанию"
    $VERSION = "0.0.0"
}

# Загрузка переменных окружения
$ENV_FILE = Join-Path $PROJECT_ROOT ".env"
if (Test-Path $ENV_FILE) {
    Get-Content $ENV_FILE | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $value)
        }
    }
}

# Установка переменных
$JFROG_REGISTRY = [Environment]::GetEnvironmentVariable("JFROG_REGISTRY")
$REPOSITORY = [Environment]::GetEnvironmentVariable("REPOSITORY")
$IMAGE_NAME = [Environment]::GetEnvironmentVariable("IMAGE_NAME")
$TAG = [Environment]::GetEnvironmentVariable("TAG")
if (-not $TAG) { $TAG = $VERSION }

$JFROG_USER = [Environment]::GetEnvironmentVariable("JFROG_USER")
if (-not $JFROG_USER) { $JFROG_USER = "admin" }

# Экспорт версии для docker-compose
[Environment]::SetEnvironmentVariable("VERSION", $VERSION)

# Использование токена из параметра или переменной
if ($JfrogToken) { 
    $JFROG_TOKEN = $JfrogToken 
} else { 
    $JFROG_TOKEN = [Environment]::GetEnvironmentVariable("JFROG_TOKEN") 
}

# Проверка переменных
if (-not $JFROG_REGISTRY -or -not $REPOSITORY -or -not $IMAGE_NAME -or -not $JFROG_TOKEN) {
    Write-Host "Ошибка: Проверьте JFROG_REGISTRY, REPOSITORY, IMAGE_NAME и JFROG_TOKEN"
    exit 1
}

# Основные функции
function Login-ToJfrog {
    Write-Host "Вход в JFrog..."
    cmd /c "echo $JFROG_TOKEN | docker login $JFROG_REGISTRY -u $JFROG_USER --password-stdin"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Ошибка: Не удалось войти в JFrog"
        exit 1
    }
}

function Build-Image {
    Write-Host "Сборка образа версии $VERSION..."
    docker-compose -f "docker-compose.build.yml" build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Ошибка: Сборка образа не удалась"
        exit 1
    }
}

function Push-Image {
    Write-Host "Отправка образа версии $VERSION..."
    docker-compose -f "docker-compose.build.yml" push
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Ошибка: Отправка образа не удалась"
        exit 1
    }
}

# Основной процесс
function Main {
    try {
        Login-ToJfrog
        Build-Image
        Push-Image
        Write-Host "Готово: $JFROG_REGISTRY/$REPOSITORY/$IMAGE_NAME`:$TAG (версия: $VERSION)"
    } catch {
        Write-Host "Ошибка выполнения: $_"
        exit 1
    }
}

Main