#!/bin/bash

# ShadowX Bot Monitoring Script
# Мониторинг состояния бота и системных ресурсов

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
DEPLOY_DIR="/opt/shadowx"
LOG_FILE="/var/log/shadowx-monitor.log"
ALERT_CHAT_ID=""   # Telegram chat ID for alerts
ALERT_BOT_TOKEN="" # Telegram bot token for alerts

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}" | tee -a "$LOG_FILE"
}

# Send alert
send_alert() {
    local message="$1"
    local priority="${2:-normal}"  # normal, warning, critical
    
    # Log alert
    if [[ "$priority" == "critical" ]]; then
        error "ALERT: $message"
    elif [[ "$priority" == "warning" ]]; then
        warn "ALERT: $message"
    else
        info "ALERT: $message"
    fi
    
    # Send Telegram alert if configured
    if [[ -n "$ALERT_BOT_TOKEN" && -n "$ALERT_CHAT_ID" ]]; then
        local emoji="ℹ️"
        case "$priority" in
            warning) emoji="⚠️" ;;
            critical) emoji="🚨" ;;
        esac
        
        curl -s -X POST "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${ALERT_CHAT_ID}" \
            -d "text=${emoji} <b>ShadowX Bot Alert</b>%0A%0A${message}%0A%0A🕐 $(date)" \
            -d "parse_mode=HTML" > /dev/null || true
    fi
}

# Check container health
check_containers() {
    info "Checking container health..."
    
    cd "$DEPLOY_DIR" || exit 1
    
    # Check if containers are running
    if ! docker compose ps -q | grep -q .; then
        send_alert "No containers are running!" "critical"
        return 1
    fi
    
    # Check container status
    local unhealthy_containers=0
    while IFS= read -r container; do
        if [[ -n "$container" ]]; then
            local status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "unknown")
            local running=$(docker inspect --format='{{.State.Running}}' "$container" 2>/dev/null || echo "false")
            
            if [[ "$running" != "true" ]]; then
                send_alert "Container $container is not running" "critical"
                ((unhealthy_containers++))
            elif [[ "$status" == "unhealthy" ]]; then
                send_alert "Container $container is unhealthy" "warning"
                ((unhealthy_containers++))
            fi
        fi
    done < <(docker compose ps -q)
    
    if [[ $unhealthy_containers -eq 0 ]]; then
        log "All containers are healthy"
        return 0
    else
        return 1
    fi
}

# Check system resources
check_resources() {
    info "Checking system resources..."
    
    # Check disk usage
    local disk_usage=$(df "$DEPLOY_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -gt 90 ]]; then
        send_alert "Disk usage is high: ${disk_usage}%" "critical"
    elif [[ $disk_usage -gt 80 ]]; then
        send_alert "Disk usage is getting high: ${disk_usage}%" "warning"
    fi
    
    # Check memory usage
    local mem_usage=$(free | awk '/^Mem:/ {printf "%.0f", $3/$2*100}')
    if [[ $mem_usage -gt 90 ]]; then
        send_alert "Memory usage is high: ${mem_usage}%" "critical"
    elif [[ $mem_usage -gt 80 ]]; then
        send_alert "Memory usage is getting high: ${mem_usage}%" "warning"
    fi
    
    # Check CPU load
    local cpu_load=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    local cpu_cores=$(nproc)
    local load_percentage=$(echo "$cpu_load $cpu_cores" | awk '{printf "%.0f", $1/$2*100}')
    
    if [[ $load_percentage -gt 90 ]]; then
        send_alert "CPU load is high: ${load_percentage}% (load: $cpu_load)" "critical"
    elif [[ $load_percentage -gt 80 ]]; then
        send_alert "CPU load is getting high: ${load_percentage}% (load: $cpu_load)" "warning"
    fi
    
    log "Resources: Disk: ${disk_usage}%, Memory: ${mem_usage}%, CPU: ${load_percentage}%"
}

# Check database
check_database() {
    info "Checking database..."
    
    local db_file="$DEPLOY_DIR/data/bot_database.db"
    
    if [[ ! -f "$db_file" ]]; then
        send_alert "Database file not found!" "critical"
        return 1
    fi
    
    # Check database integrity
    if ! sqlite3 "$db_file" "PRAGMA integrity_check;" | grep -q "ok"; then
        send_alert "Database integrity check failed!" "critical"
        return 1
    fi
    
    # Check database size
    local db_size=$(du -m "$db_file" | cut -f1)
    if [[ $db_size -gt 1000 ]]; then  # 1GB
        send_alert "Database size is large: ${db_size}MB" "warning"
    fi
    
    # Check recent activity (messages in last hour)
    local recent_messages=$(sqlite3 "$db_file" "SELECT COUNT(*) FROM messages WHERE created_at > datetime('now', '-1 hour');" 2>/dev/null || echo "0")
    
    log "Database OK - Size: ${db_size}MB, Recent messages: $recent_messages"
    return 0
}

# Check logs for errors
check_logs() {
    info "Checking logs for errors..."
    
    cd "$DEPLOY_DIR" || exit 1
    
    # Check Docker logs for errors in last 10 minutes
    local error_count=$(docker compose logs --since=10m 2>&1 | grep -i "error\|exception\|traceback\|fatal" | wc -l)
    
    if [[ $error_count -gt 10 ]]; then
        send_alert "High error count in logs: $error_count errors in last 10 minutes" "critical"
    elif [[ $error_count -gt 5 ]]; then
        send_alert "Elevated error count in logs: $error_count errors in last 10 minutes" "warning"
    fi
    
    # Check for specific critical errors
    if docker compose logs --since=10m 2>&1 | grep -q "Connection refused\|Connection timeout\|Authentication failed"; then
        send_alert "Critical connection errors detected in logs" "critical"
    fi
    
    log "Log check complete - $error_count recent errors found"
}

# Check network connectivity
check_network() {
    info "Checking network connectivity..."
    
    # Check Telegram API connectivity
    if ! curl -s --connect-timeout 10 "https://api.telegram.org" > /dev/null; then
        send_alert "Cannot reach Telegram API" "critical"
        return 1
    fi
    
    # Check DNS resolution
    if ! nslookup api.telegram.org > /dev/null 2>&1; then
        send_alert "DNS resolution issues detected" "warning"
    fi
    
    log "Network connectivity OK"
    return 0
}

# Generate status report
generate_report() {
    info "Generating status report..."
    
    cd "$DEPLOY_DIR" || exit 1
    
    local report_file="/tmp/shadowx-status-$(date +%Y%m%d-%H%M%S).txt"
    
    cat > "$report_file" << EOF
ShadowX Bot Status Report
Generated: $(date)
Hostname: $(hostname)
Uptime: $(uptime -p)

=== Container Status ===
$(docker compose ps)

=== Resource Usage ===
$(docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}")

=== System Resources ===
Disk Usage: $(df -h "$DEPLOY_DIR" | awk 'NR==2 {print $5}') ($(df -h "$DEPLOY_DIR" | awk 'NR==2 {print $4}') free)
Memory Usage: $(free -h | awk '/^Mem:/ {print $3"/"$2}')
CPU Load: $(uptime | awk -F'load average:' '{print $2}')

=== Database Info ===
Database Size: $(du -h "$DEPLOY_DIR/data/bot_database.db" 2>/dev/null | cut -f1 || echo "N/A")
Database Tables: $(sqlite3 "$DEPLOY_DIR/data/bot_database.db" ".tables" 2>/dev/null | wc -w || echo "N/A")

=== Recent Logs (last 20 lines) ===
$(docker compose logs --tail=20)
EOF
    
    echo "$report_file"
}

# Auto-restart if needed
auto_restart() {
    info "Checking if restart is needed..."
    
    cd "$DEPLOY_DIR" || exit 1
    
    local restart_needed=false
    
    # Check if containers are not running
    if ! docker compose ps -q | grep -q .; then
        warn "No containers running, restart needed"
        restart_needed=true
    fi
    
    # Check container health
    if ! check_containers > /dev/null 2>&1; then
        warn "Unhealthy containers detected, restart needed"
        restart_needed=true
    fi
    
    if [[ "$restart_needed" == "true" ]]; then
        log "Attempting automatic restart..."
        
        # Create backup before restart
        if command -v /opt/shadowx/scripts/backup.sh &> /dev/null; then
            /opt/shadowx/scripts/backup.sh
        fi
        
        # Restart containers
        docker compose down
        sleep 5
        docker compose up -d
        
        # Wait and check
        sleep 30
        if check_containers > /dev/null 2>&1; then
            send_alert "Automatic restart successful" "normal"
            log "Automatic restart completed successfully"
        else
            send_alert "Automatic restart failed - manual intervention required" "critical"
            error "Automatic restart failed"
        fi
    else
        log "No restart needed"
    fi
}

# Full health check
health_check() {
    log "Starting health check..."
    
    local checks_passed=0
    local total_checks=5
    
    # Run all checks
    check_containers && ((checks_passed++)) || true
    check_resources && ((checks_passed++)) || true
    check_database && ((checks_passed++)) || true
    check_logs && ((checks_passed++)) || true
    check_network && ((checks_passed++)) || true
    
    local health_percentage=$((checks_passed * 100 / total_checks))
    
    if [[ $health_percentage -eq 100 ]]; then
        log "Health check passed: $checks_passed/$total_checks checks OK"
    elif [[ $health_percentage -ge 80 ]]; then
        warn "Health check warning: $checks_passed/$total_checks checks OK"
    else
        error "Health check failed: $checks_passed/$total_checks checks OK"
        send_alert "Health check failed: $checks_passed/$total_checks checks passed" "critical"
    fi
    
    return $((total_checks - checks_passed))
}

# Main function
main() {
    case "${1:-}" in
        --containers)
            check_containers
            ;;
        --resources)
            check_resources
            ;;
        --database)
            check_database
            ;;
        --logs)
            check_logs
            ;;
        --network)
            check_network
            ;;
        --report)
            report_file=$(generate_report)
            echo "Report generated: $report_file"
            cat "$report_file"
            ;;
        --restart)
            auto_restart
            ;;
        --health)
            health_check
            ;;
        --help)
            echo "Usage: $0 [--containers|--resources|--database|--logs|--network|--report|--restart|--health|--help]"
            echo ""
            echo "Options:"
            echo "  --containers  Check container health"
            echo "  --resources   Check system resources"
            echo "  --database    Check database integrity"
            echo "  --logs        Check logs for errors"
            echo "  --network     Check network connectivity"
            echo "  --report      Generate detailed status report"
            echo "  --restart     Auto-restart if needed"
            echo "  --health      Run full health check"
            echo "  --help        Show this help"
            ;;
        *)
            health_check
            ;;
    esac
}

main "$@"
