#!/bin/bash

# ShadowX Bot Quick Deploy Script for Ubuntu 24.04 VPS
# Быстрое развертывание на Ubuntu 24.04

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
PROJECT_NAME="shadowx-bot"
DEPLOY_DIR="/opt/shadowx"
REPO_URL="https://github.com/your-username/shadowx-bot.git"

# Banner
show_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    ShadowX Bot Deploy                        ║"
    echo "║                  Ubuntu 24.04 LTS VPS                       ║"
    echo "║                                                              ║"
    echo "║  🚀 Automated deployment with Docker & AI moderation        ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')] ✅ $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] ❌ $1${NC}"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] ⚠️ $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] ℹ️ $1${NC}"
}

# Check Ubuntu version
check_ubuntu() {
    if [[ ! -f /etc/os-release ]]; then
        error "Cannot detect OS version"
    fi
    
    source /etc/os-release
    
    if [[ "$ID" != "ubuntu" ]]; then
        error "This script is designed for Ubuntu. Detected: $ID"
    fi
    
    if [[ "$VERSION_ID" != "24.04" ]]; then
        warn "This script is optimized for Ubuntu 24.04. Detected: $VERSION_ID"
        echo -e "${YELLOW}Continue anyway? (y/N): ${NC}"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    log "Ubuntu $VERSION_ID detected"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root. Use: sudo $0"
    fi
}

# System optimization for VPS
optimize_system() {
    log "Optimizing system for VPS deployment..."
    
    # Update system
    apt-get update && apt-get upgrade -y
    
    # Install essential packages
    apt-get install -y \
        curl \
        wget \
        git \
        htop \
        nano \
        unzip \
        zip \
        ca-certificates \
        gnupg \
        lsb-release \
        software-properties-common \
        apt-transport-https \
        fail2ban \
        ufw \
        logrotate \
        cron
    
    # Configure swap if not exists (for low-memory VPS)
    if [[ ! -f /swapfile ]]; then
        log "Creating swap file (1GB)..."
        fallocate -l 1G /swapfile
        chmod 600 /swapfile
        mkswap /swapfile
        swapon /swapfile
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
        
        # Optimize swap usage
        echo 'vm.swappiness=10' >> /etc/sysctl.conf
        echo 'vm.vfs_cache_pressure=50' >> /etc/sysctl.conf
    fi
    
    # Configure timezone
    timedatectl set-timezone UTC
    
    log "System optimization completed"
}

# Install Docker optimized for Ubuntu 24.04
install_docker() {
    log "Installing Docker for Ubuntu 24.04..."
    
    # Remove old Docker packages
    apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
    
    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    # Add Docker repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    apt-get update
    
    # Install Docker
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Start and enable Docker
    systemctl start docker
    systemctl enable docker
    
    # Configure Docker for production
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json << 'EOF'
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2",
    "live-restore": true,
    "userland-proxy": false,
    "default-ulimits": {
        "nofile": {
            "Name": "nofile",
            "Hard": 64000,
            "Soft": 64000
        }
    }
}
EOF
    
    systemctl restart docker
    
    # Verify installation
    docker --version
    docker compose version
    
    log "Docker installed successfully"
}

# Setup project directory
setup_project() {
    log "Setting up project directory..."
    
    # Create directories
    mkdir -p "$DEPLOY_DIR"
    mkdir -p "$DEPLOY_DIR/data"
    mkdir -p "$DEPLOY_DIR/logs"
    mkdir -p "$DEPLOY_DIR/scripts"
    mkdir -p "/opt/shadowx-backups"
    
    # Set permissions
    chown -R root:root "$DEPLOY_DIR"
    chmod 755 "$DEPLOY_DIR"
    
    log "Project directory created"
}

# Setup configuration
setup_config() {
    log "Setting up configuration..."
    
    cd "$DEPLOY_DIR"
    
    # Create environment file
    if [[ ! -f ".env" ]]; then
        cat > .env << 'EOF'
# ShadowX Bot Configuration
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=your_admin_id_here

# AI Configuration
AI_PROFANITY_ENABLED=1
AI_BACKEND=ensemble
AI_PROFANITY_THRESHOLD=0.7
SPAM_SCORE_THRESHOLD=0.6

# Performance
MESSAGE_QUEUE_MIN_INTERVAL=20
MESSAGE_QUEUE_MAX_INTERVAL=30
MIN_MESSAGE_WORDS=4

# System
LOG_LEVEL=INFO
TIMEZONE=UTC
DATA_PATH=/opt/shadowx/data
LOGS_PATH=/opt/shadowx/logs
EOF
        
        warn "Please edit the .env file with your bot token and admin IDs:"
        warn "nano $DEPLOY_DIR/.env"
        echo ""
        info "Required fields:"
        info "  - BOT_TOKEN: Get from @BotFather on Telegram"
        info "  - ADMIN_IDS: Your Telegram user ID (comma-separated for multiple)"
        echo ""
        echo -e "${YELLOW}Press Enter when you've configured the .env file...${NC}"
        read -r
    else
        log "Configuration file already exists"
    fi
}

# Create Docker Compose file
create_compose() {
    log "Creating Docker Compose configuration..."
    
    cd "$DEPLOY_DIR"
    
    cat > docker-compose.yml << 'EOF'
version: "3.8"

services:
  shadowx-bot:
    build: 
      context: .
      dockerfile: Dockerfile
      args:
        PREFETCH_MODELS: 1
    image: shadowx-bot:latest
    container_name: shadowx-bot
    restart: unless-stopped
    
    env_file:
      - .env
    environment:
      - DB_PATH=/data/bot_database.db
      - TZ=${TIMEZONE:-UTC}
    
    volumes:
      - ./data:/data
      - ./logs:/app/logs
      - shadowx_cache:/app/cache
    
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.25'
          memory: 256M
    
    healthcheck:
      test: ["CMD", "python", "-c", "import sqlite3; sqlite3.connect('/data/bot_database.db').close()"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    
    security_opt:
      - no-new-privileges:true
    
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  shadowx_cache:
    driver: local
EOF
    
    log "Docker Compose file created"
}

# Setup firewall
setup_firewall() {
    log "Configuring UFW firewall..."
    
    # Reset UFW to defaults
    ufw --force reset
    
    # Default policies
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow SSH (be careful not to lock yourself out)
    ufw allow ssh
    
    # Allow HTTP/HTTPS if needed for webhooks
    # ufw allow 80
    # ufw allow 443
    
    # Enable firewall
    ufw --force enable
    
    log "Firewall configured"
}

# Setup monitoring
setup_monitoring() {
    log "Setting up monitoring..."
    
    # Create monitoring script
    cat > "$DEPLOY_DIR/scripts/health-check.sh" << 'EOF'
#!/bin/bash
cd /opt/shadowx
if ! docker compose ps | grep -q "Up"; then
    echo "$(date): Container down, restarting..." >> /var/log/shadowx-monitor.log
    docker compose up -d
fi
EOF
    
    chmod +x "$DEPLOY_DIR/scripts/health-check.sh"
    
    # Add to crontab (check every 5 minutes)
    (crontab -l 2>/dev/null; echo "*/5 * * * * /opt/shadowx/scripts/health-check.sh") | crontab -
    
    log "Monitoring configured"
}

# Setup systemd service
setup_systemd() {
    log "Setting up systemd service..."
    
    cat > /etc/systemd/system/shadowx-bot.service << EOF
[Unit]
Description=ShadowX Telegram Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$DEPLOY_DIR
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable shadowx-bot.service
    
    log "Systemd service created"
}

# Deploy application
deploy_application() {
    log "Deploying application..."
    
    cd "$DEPLOY_DIR"
    
    # Copy current directory files (assuming script is run from project directory)
    if [[ -f "$(dirname "$0")/bot.py" ]]; then
        log "Copying project files..."
        cp -r "$(dirname "$0")"/* "$DEPLOY_DIR/"
    else
        warn "Project files not found in current directory"
        info "Please copy your project files to $DEPLOY_DIR manually"
        echo -e "${YELLOW}Press Enter when files are ready...${NC}"
        read -r
    fi
    
    # Build and start
    log "Building Docker image..."
    docker compose build --no-cache
    
    log "Starting containers..."
    docker compose up -d
    
    # Wait for startup
    log "Waiting for application to start..."
    sleep 30
    
    # Check status
    if docker compose ps | grep -q "Up"; then
        log "Application deployed successfully!"
    else
        error "Deployment failed. Check logs: docker compose logs"
    fi
}

# Show final status
show_status() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                    DEPLOYMENT COMPLETE!                     ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    log "ShadowX Bot is now running!"
    echo ""
    
    info "Container Status:"
    cd "$DEPLOY_DIR"
    docker compose ps
    echo ""
    
    info "Useful Commands:"
    echo "  📊 Check status:    cd $DEPLOY_DIR && docker compose ps"
    echo "  📋 View logs:       cd $DEPLOY_DIR && docker compose logs -f"
    echo "  🔄 Restart:         cd $DEPLOY_DIR && docker compose restart"
    echo "  🛑 Stop:            cd $DEPLOY_DIR && docker compose down"
    echo "  🔧 Update:          cd $DEPLOY_DIR && docker compose pull && docker compose up -d"
    echo ""
    
    info "Files and Directories:"
    echo "  📁 Project:         $DEPLOY_DIR"
    echo "  💾 Database:        $DEPLOY_DIR/data/bot_database.db"
    echo "  📝 Logs:            $DEPLOY_DIR/logs/"
    echo "  ⚙️  Config:          $DEPLOY_DIR/.env"
    echo ""
    
    info "System Services:"
    echo "  🚀 Auto-start:      systemctl status shadowx-bot"
    echo "  🔍 Monitoring:      tail -f /var/log/shadowx-monitor.log"
    echo "  🔥 Firewall:        ufw status"
    echo ""
    
    warn "Next Steps:"
    echo "  1. Make sure your bot token and admin IDs are correct in .env"
    echo "  2. Test the bot by sending a message"
    echo "  3. Monitor logs for any issues"
    echo "  4. Set up regular backups"
    echo ""
}

# Main function
main() {
    show_banner
    
    log "Starting ShadowX Bot deployment on Ubuntu 24.04..."
    
    check_ubuntu
    check_root
    optimize_system
    install_docker
    setup_project
    setup_config
    create_compose
    setup_firewall
    setup_monitoring
    setup_systemd
    deploy_application
    show_status
    
    log "Deployment completed successfully! 🎉"
}

# Handle arguments
case "${1:-}" in
    --help)
        echo "Ubuntu 24.04 VPS Deployment Script for ShadowX Bot"
        echo ""
        echo "Usage: sudo $0"
        echo ""
        echo "This script will:"
        echo "  - Install Docker and Docker Compose"
        echo "  - Optimize system for VPS"
        echo "  - Deploy ShadowX Bot with AI moderation"
        echo "  - Configure firewall and monitoring"
        echo "  - Set up auto-start service"
        exit 0
        ;;
    *)
        main
        ;;
esac
