#!/bin/bash

# ShadowX Bot Backup Script
# Создание резервных копий данных бота

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
DEPLOY_DIR="/opt/shadowx"
BACKUP_DIR="/opt/shadowx-backups"
REMOTE_BACKUP_DIR=""  # Set for remote backups (e.g., /mnt/backup)
TELEGRAM_CHAT_ID=""   # Set for Telegram notifications
TELEGRAM_BOT_TOKEN="" # Set for Telegram notifications

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Send Telegram notification
send_telegram_notification() {
    local message="$1"
    if [[ -n "$TELEGRAM_BOT_TOKEN" && -n "$TELEGRAM_CHAT_ID" ]]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            -d "text=${message}" \
            -d "parse_mode=HTML" > /dev/null
    fi
}

# Create backup
create_backup() {
    log "Starting backup process..."
    
    # Check if deploy directory exists
    if [[ ! -d "$DEPLOY_DIR" ]]; then
        error "Deploy directory $DEPLOY_DIR not found"
    fi
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Backup name with timestamp
    BACKUP_NAME="shadowx-backup-$(date +%Y%m%d-%H%M%S)"
    BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"
    
    log "Creating backup: $BACKUP_NAME"
    mkdir -p "$BACKUP_PATH"
    
    # Backup database
    if [[ -f "$DEPLOY_DIR/data/bot_database.db" ]]; then
        log "Backing up database..."
        cp "$DEPLOY_DIR/data/bot_database.db" "$BACKUP_PATH/"
        
        # Create SQL dump for easier restoration
        sqlite3 "$DEPLOY_DIR/data/bot_database.db" .dump > "$BACKUP_PATH/database_dump.sql"
    else
        warn "Database file not found"
    fi
    
    # Backup configuration
    if [[ -f "$DEPLOY_DIR/.env" ]]; then
        log "Backing up configuration..."
        cp "$DEPLOY_DIR/.env" "$BACKUP_PATH/"
    else
        warn "Configuration file not found"
    fi
    
    # Backup logs
    if [[ -d "$DEPLOY_DIR/logs" ]]; then
        log "Backing up logs..."
        cp -r "$DEPLOY_DIR/logs" "$BACKUP_PATH/"
    fi
    
    # Create metadata file
    cat > "$BACKUP_PATH/metadata.txt" << EOF
Backup Created: $(date)
Hostname: $(hostname)
Docker Version: $(docker --version)
Container Status:
$(cd "$DEPLOY_DIR" && docker compose ps 2>/dev/null || echo "No containers running")
EOF
    
    # Compress backup
    log "Compressing backup..."
    cd "$BACKUP_DIR"
    tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
    rm -rf "$BACKUP_NAME"
    
    BACKUP_SIZE=$(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)
    log "Backup created: ${BACKUP_NAME}.tar.gz (${BACKUP_SIZE})"
    
    # Copy to remote location if configured
    if [[ -n "$REMOTE_BACKUP_DIR" && -d "$REMOTE_BACKUP_DIR" ]]; then
        log "Copying to remote backup location..."
        cp "${BACKUP_NAME}.tar.gz" "$REMOTE_BACKUP_DIR/"
    fi
    
    # Send notification
    send_telegram_notification "✅ ShadowX Bot backup completed successfully
📦 File: ${BACKUP_NAME}.tar.gz
📊 Size: ${BACKUP_SIZE}
🕐 Time: $(date)"
    
    return 0
}

# Cleanup old backups
cleanup_old_backups() {
    local keep_count=${1:-7}  # Keep last 7 backups by default
    
    log "Cleaning up old backups (keeping last $keep_count)..."
    
    cd "$BACKUP_DIR"
    
    # Remove old local backups
    ls -t shadowx-backup-*.tar.gz 2>/dev/null | tail -n +$((keep_count + 1)) | xargs -r rm -f
    
    # Remove old remote backups if configured
    if [[ -n "$REMOTE_BACKUP_DIR" && -d "$REMOTE_BACKUP_DIR" ]]; then
        cd "$REMOTE_BACKUP_DIR"
        ls -t shadowx-backup-*.tar.gz 2>/dev/null | tail -n +$((keep_count + 1)) | xargs -r rm -f
    fi
    
    log "Cleanup completed"
}

# Restore from backup
restore_backup() {
    local backup_file="$1"
    
    if [[ -z "$backup_file" ]]; then
        error "Please specify backup file to restore"
    fi
    
    if [[ ! -f "$backup_file" ]]; then
        error "Backup file not found: $backup_file"
    fi
    
    log "Restoring from backup: $backup_file"
    
    # Stop containers
    cd "$DEPLOY_DIR"
    docker compose down || true
    
    # Extract backup
    TEMP_DIR=$(mktemp -d)
    tar -xzf "$backup_file" -C "$TEMP_DIR"
    
    BACKUP_FOLDER=$(ls "$TEMP_DIR")
    
    # Restore database
    if [[ -f "$TEMP_DIR/$BACKUP_FOLDER/bot_database.db" ]]; then
        log "Restoring database..."
        cp "$TEMP_DIR/$BACKUP_FOLDER/bot_database.db" "$DEPLOY_DIR/data/"
    fi
    
    # Restore configuration
    if [[ -f "$TEMP_DIR/$BACKUP_FOLDER/.env" ]]; then
        log "Restoring configuration..."
        cp "$TEMP_DIR/$BACKUP_FOLDER/.env" "$DEPLOY_DIR/"
    fi
    
    # Cleanup
    rm -rf "$TEMP_DIR"
    
    # Restart containers
    docker compose up -d
    
    log "Restore completed successfully"
    
    send_telegram_notification "🔄 ShadowX Bot restored from backup
📦 File: $(basename "$backup_file")
🕐 Time: $(date)"
}

# List available backups
list_backups() {
    log "Available backups:"
    
    if [[ -d "$BACKUP_DIR" ]]; then
        cd "$BACKUP_DIR"
        for backup in shadowx-backup-*.tar.gz; do
            if [[ -f "$backup" ]]; then
                size=$(du -h "$backup" | cut -f1)
                date_created=$(stat -c %y "$backup" | cut -d' ' -f1,2 | cut -d'.' -f1)
                echo "  $backup ($size) - $date_created"
            fi
        done
    else
        warn "Backup directory not found"
    fi
}

# Test backup integrity
test_backup() {
    local backup_file="$1"
    
    if [[ -z "$backup_file" ]]; then
        error "Please specify backup file to test"
    fi
    
    if [[ ! -f "$backup_file" ]]; then
        error "Backup file not found: $backup_file"
    fi
    
    log "Testing backup integrity: $backup_file"
    
    # Test archive
    if tar -tzf "$backup_file" > /dev/null; then
        log "✅ Archive integrity OK"
    else
        error "❌ Archive is corrupted"
    fi
    
    # Extract to temp and test database
    TEMP_DIR=$(mktemp -d)
    tar -xzf "$backup_file" -C "$TEMP_DIR"
    
    BACKUP_FOLDER=$(ls "$TEMP_DIR")
    
    if [[ -f "$TEMP_DIR/$BACKUP_FOLDER/bot_database.db" ]]; then
        if sqlite3 "$TEMP_DIR/$BACKUP_FOLDER/bot_database.db" "PRAGMA integrity_check;" | grep -q "ok"; then
            log "✅ Database integrity OK"
        else
            error "❌ Database is corrupted"
        fi
    fi
    
    rm -rf "$TEMP_DIR"
    log "Backup test completed successfully"
}

# Main function
main() {
    case "${1:-}" in
        --restore)
            restore_backup "$2"
            ;;
        --list)
            list_backups
            ;;
        --cleanup)
            cleanup_old_backups "${2:-7}"
            ;;
        --test)
            test_backup "$2"
            ;;
        --help)
            echo "Usage: $0 [--restore FILE|--list|--cleanup [COUNT]|--test FILE|--help]"
            echo ""
            echo "Options:"
            echo "  (no args)        Create new backup"
            echo "  --restore FILE   Restore from backup file"
            echo "  --list          List available backups"
            echo "  --cleanup COUNT  Remove old backups (keep COUNT newest)"
            echo "  --test FILE     Test backup integrity"
            echo "  --help          Show this help"
            ;;
        *)
            create_backup
            cleanup_old_backups
            ;;
    esac
}

main "$@"
