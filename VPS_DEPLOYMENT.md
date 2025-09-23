# 🚀 ShadowX Bot - Развертывание на Ubuntu 24.04 VPS

Полное руководство по развертыванию ShadowX Bot на VPS сервере с Ubuntu 24.04.

## 📋 Требования

### Минимальные системные требования:
- **ОС**: Ubuntu 24.04 LTS
- **RAM**: 1 GB (рекомендуется 2 GB)
- **CPU**: 1 vCPU (рекомендуется 2 vCPU)
- **Диск**: 10 GB свободного места
- **Интернет**: Стабильное подключение

### Необходимые данные:
- 🤖 **Telegram Bot Token** (получить у [@BotFather](https://t.me/botfather))
- 👤 **Admin User ID** (получить у [@userinfobot](https://t.me/userinfobot))

## 🎯 Быстрое развертывание (Рекомендуется)

### 1. Подключение к VPS
```bash
ssh root@your-vps-ip
```

### 2. Скачивание проекта
```bash
# Клонируйте репозиторий
git clone https://github.com/your-username/shadowx-bot.git
cd shadowx-bot

# Или загрузите файлы проекта на сервер
```

### 3. Запуск автоматического развертывания
```bash
# Сделайте скрипт исполняемым
chmod +x ubuntu-deploy.sh

# Запустите развертывание
sudo ./ubuntu-deploy.sh
```

### 4. Настройка конфигурации
Во время установки скрипт попросит отредактировать файл `.env`:

```bash
nano /opt/shadowx/.env
```

Заполните обязательные поля:
```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxyz
ADMIN_IDS=123456789,987654321
```

### 5. Проверка статуса
```bash
cd /opt/shadowx
docker compose ps
docker compose logs -f
```

## 🔧 Ручное развертывание

Если автоматический скрипт не подходит, выполните шаги вручную:

### 1. Обновление системы
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Установка Docker
```bash
# Удаление старых версий
sudo apt-get remove -y docker docker-engine docker.io containerd runc

# Установка зависимостей
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Добавление GPG ключа Docker
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Добавление репозитория
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установка Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Запуск Docker
sudo systemctl start docker
sudo systemctl enable docker
```

### 3. Настройка проекта
```bash
# Создание директорий
sudo mkdir -p /opt/shadowx/{data,logs,scripts}
cd /opt/shadowx

# Копирование файлов проекта
# (скопируйте все файлы вашего проекта в /opt/shadowx)

# Создание .env файла
sudo nano .env
```

### 4. Развертывание
```bash
# Сборка и запуск
sudo docker compose build --no-cache
sudo docker compose up -d

# Проверка статуса
sudo docker compose ps
```

## ⚙️ Конфигурация

### Основные настройки в `.env`:

```env
# Обязательные настройки
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321

# AI модерация
AI_PROFANITY_ENABLED=1
AI_BACKEND=ensemble
AI_PROFANITY_THRESHOLD=0.7
SPAM_SCORE_THRESHOLD=0.6

# Производительность
MESSAGE_QUEUE_MIN_INTERVAL=20
MESSAGE_QUEUE_MAX_INTERVAL=30
MIN_MESSAGE_WORDS=4

# Система
LOG_LEVEL=INFO
TIMEZONE=UTC
```

### Docker Compose настройки:

Файл `docker-compose.yml` уже оптимизирован для продакшена:
- ✅ Multi-stage build для оптимизации размера
- ✅ Health checks для мониторинга
- ✅ Resource limits для стабильности
- ✅ Security настройки
- ✅ Логирование с ротацией

## 🔍 Управление и мониторинг

### Основные команды:

```bash
# Переход в директорию проекта
cd /opt/shadowx

# Просмотр статуса
docker compose ps

# Просмотр логов
docker compose logs -f

# Перезапуск бота
docker compose restart

# Остановка
docker compose down

# Обновление
docker compose pull
docker compose up -d --force-recreate
```

### Системный сервис:

```bash
# Статус автозапуска
sudo systemctl status shadowx-bot

# Включение автозапуска
sudo systemctl enable shadowx-bot

# Запуск/остановка через systemd
sudo systemctl start shadowx-bot
sudo systemctl stop shadowx-bot
```

### Мониторинг ресурсов:

```bash
# Использование ресурсов контейнерами
docker stats

# Использование диска
df -h /opt/shadowx

# Системные ресурсы
htop

# Логи системы
journalctl -u shadowx-bot -f
```

## 💾 Резервное копирование

### Автоматический бэкап:

```bash
# Запуск скрипта бэкапа
sudo /opt/shadowx/scripts/backup.sh

# Просмотр доступных бэкапов
sudo /opt/shadowx/scripts/backup.sh --list

# Восстановление из бэкапа
sudo /opt/shadowx/scripts/backup.sh --restore /opt/shadowx-backups/backup-file.tar.gz
```

### Ручной бэкап:

```bash
# Создание бэкапа базы данных
sudo cp /opt/shadowx/data/bot_database.db /opt/shadowx-backups/manual-backup-$(date +%Y%m%d).db

# Бэкап конфигурации
sudo cp /opt/shadowx/.env /opt/shadowx-backups/env-backup-$(date +%Y%m%d)
```

## 🔥 Безопасность

### Настройка файрвола:

```bash
# Статус UFW
sudo ufw status

# Базовые правила (уже настроены скриптом)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh

# Применение правил
sudo ufw enable
```

### Обновления безопасности:

```bash
# Автоматические обновления безопасности
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### Мониторинг безопасности:

```bash
# Проверка подозрительной активности
sudo journalctl -u ssh -f

# Статистика fail2ban
sudo fail2ban-client status
```

## 🚨 Устранение неполадок

### Частые проблемы:

#### 1. Контейнер не запускается
```bash
# Проверка логов
docker compose logs

# Проверка конфигурации
cat .env

# Перезапуск с пересборкой
docker compose down
docker compose build --no-cache
docker compose up -d
```

#### 2. Нет места на диске
```bash
# Очистка Docker
docker system prune -a

# Очистка логов
sudo journalctl --vacuum-time=7d

# Удаление старых бэкапов
sudo find /opt/shadowx-backups -name "*.tar.gz" -mtime +30 -delete
```

#### 3. Высокое использование памяти
```bash
# Проверка использования
docker stats

# Перезапуск контейнера
docker compose restart

# Проверка swap
free -h
```

#### 4. Проблемы с AI моделями
```bash
# Проверка доступности моделей
docker compose exec shadowx-bot python -c "from utils.filters import _ensure_ai_loaded; _ensure_ai_loaded()"

# Очистка кэша моделей
docker compose down
docker volume prune
docker compose up -d
```

### Логи и диагностика:

```bash
# Основные логи бота
docker compose logs shadowx-bot

# Системные логи
sudo journalctl -u shadowx-bot

# Логи Docker
sudo journalctl -u docker

# Мониторинг в реальном времени
sudo tail -f /var/log/shadowx-monitor.log
```

## 📊 Производительность

### Оптимизация для VPS:

1. **Память**: Бот использует ~256-512MB RAM
2. **CPU**: Оптимизирован для 1-2 vCPU
3. **Диск**: Ротация логов и автоочистка
4. **Сеть**: Эффективное использование API Telegram

### Масштабирование:

Для высоких нагрузок:
- Увеличьте лимиты памяти в `docker-compose.yml`
- Настройте Redis для кэширования (опционально)
- Используйте webhook вместо polling

## 🆘 Поддержка

### Полезные ссылки:
- 📖 [Документация Docker](https://docs.docker.com/)
- 🤖 [Telegram Bot API](https://core.telegram.org/bots/api)
- 🐧 [Ubuntu 24.04 LTS](https://ubuntu.com/download/server)

### Контакты:
- 📧 Создайте Issue в репозитории
- 💬 Telegram: @your_support_contact

---

## ✅ Чек-лист развертывания

- [ ] VPS с Ubuntu 24.04 готов
- [ ] Получен Bot Token от @BotFather
- [ ] Получен Admin User ID
- [ ] Скачан проект на сервер
- [ ] Запущен скрипт `ubuntu-deploy.sh`
- [ ] Настроен файл `.env`
- [ ] Проверен статус контейнеров
- [ ] Протестирован бот в Telegram
- [ ] Настроен мониторинг
- [ ] Создан первый бэкап

**🎉 Поздравляем! ShadowX Bot успешно развернут на вашем VPS!**
