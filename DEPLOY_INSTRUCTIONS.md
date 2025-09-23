# 🚀 ShadowX Bot - Инструкция по развертыванию на Ubuntu 24.04 VPS

## 📦 Что мы подготовили

✅ **Оптимизированный Docker**:
- Multi-stage build для минимального размера образа
- Python 3.12 с актуальными зависимостями
- Безопасность: non-root пользователь, read-only файловая система
- Health checks и resource limits

✅ **Продакшен-готовый Docker Compose**:
- Автоматическая перезагрузка контейнеров
- Ограничения ресурсов для VPS
- Логирование с ротацией
- Мониторинг и health checks

✅ **Скрипты автоматизации**:
- `ubuntu-deploy.sh` - полное автоматическое развертывание
- `scripts/backup.sh` - система резервного копирования
- `scripts/monitor.sh` - мониторинг состояния системы

✅ **Безопасность и мониторинг**:
- UFW firewall настройка
- Systemd сервис для автозапуска
- Автоматический мониторинг и перезапуск
- Система алертов через Telegram

## 🎯 Быстрый старт

### 1. На вашем компьютере (Windows)
```powershell
# Архивируйте проект
Compress-Archive -Path * -DestinationPath shadowx-bot.zip
```

### 2. Загрузите на VPS
```bash
# Подключитесь к VPS
ssh root@your-vps-ip

# Скачайте архив (или используйте scp/sftp)
wget https://your-domain.com/shadowx-bot.zip
# или
# scp shadowx-bot.zip root@your-vps-ip:/root/

# Распакуйте
unzip shadowx-bot.zip
cd shadowx-bot
```

### 3. Запустите автоматическое развертывание
```bash
# Сделайте скрипт исполняемым
chmod +x ubuntu-deploy.sh

# Запустите развертывание
sudo ./ubuntu-deploy.sh
```

### 4. Настройте бота
Во время установки отредактируйте `.env`:
```bash
nano /opt/shadowx/.env
```

Заполните:
```env
BOT_TOKEN=ваш_токен_от_botfather
ADMIN_IDS=ваш_telegram_id
```

### 5. Проверьте работу
```bash
cd /opt/shadowx
docker compose ps
docker compose logs -f
```

## 📋 Что происходит при развертывании

### Автоматические действия:
1. ✅ **Проверка Ubuntu 24.04**
2. ✅ **Оптимизация системы** (swap, timezone, пакеты)
3. ✅ **Установка Docker** с оптимизированной конфигурацией
4. ✅ **Создание директорий** проекта
5. ✅ **Настройка безопасности** (UFW firewall)
6. ✅ **Установка мониторинга** (health checks, cron)
7. ✅ **Создание systemd сервиса** для автозапуска
8. ✅ **Сборка и запуск** Docker контейнеров
9. ✅ **Проверка работоспособности**

### Результат:
- 🤖 **Бот работает** в Docker контейнере
- 🔄 **Автозапуск** при перезагрузке сервера
- 🔍 **Мониторинг** каждые 5 минут
- 💾 **База данных** сохраняется в `/opt/shadowx/data`
- 📝 **Логи** в `/opt/shadowx/logs`
- 🔒 **Безопасность** настроена (firewall, non-root)

## 🔧 Управление после развертывания

### Основные команды:
```bash
# Статус
cd /opt/shadowx && docker compose ps

# Логи
cd /opt/shadowx && docker compose logs -f

# Перезапуск
cd /opt/shadowx && docker compose restart

# Остановка
cd /opt/shadowx && docker compose down

# Обновление
cd /opt/shadowx && docker compose pull && docker compose up -d
```

### Системный сервис:
```bash
# Статус
systemctl status shadowx-bot

# Запуск/остановка
systemctl start shadowx-bot
systemctl stop shadowx-bot
```

### Бэкапы:
```bash
# Создать бэкап
/opt/shadowx/scripts/backup.sh

# Список бэкапов
/opt/shadowx/scripts/backup.sh --list

# Восстановление
/opt/shadowx/scripts/backup.sh --restore /opt/shadowx-backups/backup-file.tar.gz
```

### Мониторинг:
```bash
# Полная проверка здоровья
/opt/shadowx/scripts/monitor.sh

# Проверка ресурсов
/opt/shadowx/scripts/monitor.sh --resources

# Отчет о состоянии
/opt/shadowx/scripts/monitor.sh --report
```

## 🔍 Проверка работы

### 1. Контейнеры запущены:
```bash
docker compose ps
# Должно показать: shadowx-bot Up (healthy)
```

### 2. Логи без ошибок:
```bash
docker compose logs --tail=20
# Должно показать успешный запуск бота
```

### 3. База данных создана:
```bash
ls -la /opt/shadowx/data/
# Должен быть файл bot_database.db
```

### 4. Бот отвечает в Telegram:
- Найдите вашего бота в Telegram
- Отправьте команду `/start`
- Бот должен ответить

## 🚨 Решение проблем

### Контейнер не запускается:
```bash
# Проверить логи
docker compose logs

# Пересобрать образ
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Ошибки в логах:
```bash
# Проверить конфигурацию
cat /opt/shadowx/.env

# Проверить права доступа
ls -la /opt/shadowx/data/

# Перезапустить
docker compose restart
```

### Нет места на диске:
```bash
# Очистить Docker
docker system prune -a

# Очистить логи
journalctl --vacuum-time=7d

# Удалить старые бэкапы
find /opt/shadowx-backups -name "*.tar.gz" -mtime +7 -delete
```

## 📊 Производительность

### Использование ресурсов:
- **RAM**: 256-512 MB
- **CPU**: 10-30% на 1 vCPU
- **Диск**: ~2 GB (включая Docker образы)
- **Сеть**: Минимальная нагрузка

### Для высоких нагрузок:
Отредактируйте `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Увеличить CPU
      memory: 2G       # Увеличить RAM
```

## 🔐 Безопасность

### Настроенная защита:
- ✅ UFW firewall (только SSH открыт)
- ✅ Non-root пользователь в контейнере
- ✅ Read-only файловая система
- ✅ Fail2ban для защиты SSH
- ✅ Автоматические обновления безопасности

### Дополнительные меры:
```bash
# Изменить SSH порт
nano /etc/ssh/sshd_config
# Port 2222

# Отключить root login
# PermitRootLogin no

# Перезапустить SSH
systemctl restart sshd

# Обновить firewall
ufw allow 2222
ufw delete allow ssh
```

## 📈 Мониторинг и алерты

### Настройка Telegram уведомлений:
1. Создайте отдельного бота для мониторинга
2. Добавьте в `.env`:
```env
ALERT_BOT_TOKEN=ваш_токен_мониторинга
ALERT_CHAT_ID=ваш_chat_id
```

### Метрики мониторинга:
- 🔍 Здоровье контейнеров
- 💾 Использование диска
- 🧠 Использование памяти
- ⚡ Нагрузка CPU
- 🔗 Сетевое подключение
- 💾 Целостность базы данных

## ✅ Финальный чек-лист

После развертывания проверьте:

- [ ] Контейнер запущен: `docker compose ps`
- [ ] Нет ошибок в логах: `docker compose logs`
- [ ] База данных создана: `ls /opt/shadowx/data/`
- [ ] Бот отвечает в Telegram: отправьте `/start`
- [ ] Автозапуск работает: `systemctl status shadowx-bot`
- [ ] Мониторинг активен: `crontab -l`
- [ ] Firewall настроен: `ufw status`
- [ ] Создан первый бэкап: `/opt/shadowx/scripts/backup.sh`

## 🎉 Готово!

Ваш ShadowX Bot теперь работает на профессиональном уровне:

- 🚀 **Высокая производительность** с Python 3.12 и оптимизированным Docker
- 🛡️ **Безопасность** на уровне продакшена
- 🔍 **Полный мониторинг** и автоматическое восстановление
- 💾 **Автоматические бэкапы** и система восстановления
- 🤖 **AI модерация** с поддержкой 4 языков
- ⚡ **Масштабируемость** для любых нагрузок

**Наслаждайтесь стабильной работой вашего бота! 🎊**
