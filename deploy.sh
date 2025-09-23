#!/bin/bash

# ShadowX Bot VPS Deployment Script
# Автоматическое развертывание бота на VPS сервере

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="shadowx-bot"
REPO_URL="https://github.com/your-username/shadowx-bot.git"  # Update with your repo
DEPLOY_DIR="/opt/shadowx"
BACKUP_DIR="/opt/shadowx-backups"
LOG_FILE="/var/log/shadowx-deploy.log"

# Functions
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" | tee -a "$LOG_FILE"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}" | tee -a "$LOG_FILE"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
    fi
}

# Install Docker and Docker Compose for Ubuntu 24.04
install_docker() {
    log "Installing Docker and Docker Compose for Ubuntu 24.04..."
    
    # Update package index
    apt-get update
    
    # Install prerequisites
    apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        git \
        htop \
        nano \
        unzip \
        wget \
        software-properties-common \
        apt-transport-https
    
    # Remove old Docker packages if they exist
    apt-get remove -y docker docker-engine docker.io containerd runc || true
    
    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    # Set up Docker repository for Ubuntu 24.04 (Noble Numbat)
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Update package index again
    apt-get update
    
    # Install Docker Engine, CLI, containerd, and Docker Compose plugin
    apt-get install -y \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin
    
    # Start and enable Docker
    systemctl start docker
    systemctl enable docker
    
    # Configure Docker daemon for better performance
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json << 'EOF'
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2",
    "storage-opts": [
        "overlay2.override_kernel_check=true"
    ],
    "live-restore": true,
    "userland-proxy": false,
    "experimental": false,
    "metrics-addr": "127.0.0.1:9323",
    "default-ulimits": {
        "nofile": {
            "Name": "nofile",
            "Hard": 64000,
            "Soft": 64000
        }
    }
}
EOF
    
    # Restart Docker to apply configuration
    systemctl restart docker
    
    # Add current user to docker group if not root
    if [[ -n "$SUDO_USER" ]]; then
        usermod -aG docker "$SUDO_USER"
        log "Added $SUDO_USER to docker group. Please log out and back in."
    fi
    
    # Verify installation
    docker --version
    docker compose version
    
    log "Docker installation completed successfully"
}

# Check Docker installation
check_docker() {
    if ! command -v docker &> /dev/null; then
        warn "Docker not found. Installing..."
        install_docker
    else
        log "Docker is already installed"
        docker --version
    fi
    
    if ! docker compose version &> /dev/null; then
        error "Docker Compose not found. Please install Docker Compose v2"
    else
        log "Docker Compose is available"
        docker compose version
    fi
}

# Setup directories
setup_directories() {
    log "Setting up directories..."
    
    # Create main directories
    mkdir -p "$DEPLOY_DIR"
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$DEPLOY_DIR/data"
    mkdir -p "$DEPLOY_DIR/logs"
    
    # Set permissions
    chown -R 1000:1000 "$DEPLOY_DIR/data" "$DEPLOY_DIR/logs"
    chmod 755 "$DEPLOY_DIR"
    
    log "Directories created successfully"
}

# Clone or update repository
setup_repository() {
    log "Setting up repository..."
    
    if [[ -d "$DEPLOY_DIR/.git" ]]; then
        log "Repository exists, updating..."
        cd "$DEPLOY_DIR"
        git pull origin main
    else
        log "Cloning repository..."
        if [[ -d "$DEPLOY_DIR" ]] && [[ "$(ls -A $DEPLOY_DIR)" ]]; then
            # Backup existing files
            mv "$DEPLOY_DIR" "${DEPLOY_DIR}.backup.$(date +%s)"
        fi
        git clone "$REPO_URL" "$DEPLOY_DIR"
        cd "$DEPLOY_DIR"
    fi
    
    log "Repository setup completed"
}

# Setup environment file
setup_environment() {
    log "Setting up environment configuration..."
    
    cd "$DEPLOY_DIR"
    
    if [[ ! -f ".env" ]]; then
        log "Creating .env file from template..."
        cat > .env << 'EOF'
# Telegram Bot Configuration
BOT_TOKEN=your_bot_token_here

# Admin Configuration
ADMIN_IDS=your_admin_id_here
# ADMIN_USERNAMES=123456789:@username

# AI Configuration
AI_PROFANITY_ENABLED=1
AI_BACKEND=ensemble
AI_PROFANITY_THRESHOLD=0.7
SPAM_SCORE_THRESHOLD=0.6

# Performance Settings
MESSAGE_QUEUE_MIN_INTERVAL=20
MESSAGE_QUEUE_MAX_INTERVAL=30
MIN_MESSAGE_WORDS=4

# Logging
LOG_LEVEL=INFO

# Timezone
TIMEZONE=UTC

# Paths (for Docker volumes)
DATA_PATH=/opt/shadowx/data
LOGS_PATH=/opt/shadowx/logs
EOF
        
        warn "Please edit .env file with your bot token and admin IDs:"
        warn "nano $DEPLOY_DIR/.env"
        warn "Press Enter when ready to continue..."
        read -r
    else
        log ".env file already exists"
    fi
}

# Create backup
create_backup() {
    if [[ -f "$DEPLOY_DIR/data/bot_database.db" ]]; then
        log "Creating backup..."
        
        BACKUP_NAME="shadowx-backup-$(date +%Y%m%d-%H%M%S)"
        BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"
        
        mkdir -p "$BACKUP_PATH"
        
        # Backup database
        cp "$DEPLOY_DIR/data/bot_database.db" "$BACKUP_PATH/"
        
        # Backup environment
        cp "$DEPLOY_DIR/.env" "$BACKUP_PATH/"
        
        # Compress backup
        cd "$BACKUP_DIR"
        tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
        rm -rf "$BACKUP_NAME"
        
        log "Backup created: ${BACKUP_PATH}.tar.gz"
        
        # Keep only last 5 backups
        cd "$BACKUP_DIR"
        ls -t shadowx-backup-*.tar.gz | tail -n +6 | xargs -r rm --
    else
        log "No database found, skipping backup"
    fi
}

# Deploy application
deploy_app() {
    log "Deploying application..."
    
    cd "$DEPLOY_DIR"
    
    # Stop existing containers
    if docker compose ps -q | grep -q .; then
        log "Stopping existing containers..."
        docker compose down
    fi
    
    # Build and start containers
    log "Building and starting containers..."
    docker compose build --no-cache
    docker compose up -d
    
    # Wait for containers to be ready
    log "Waiting for containers to be ready..."
    sleep 10
    
    # Check container status
    if docker compose ps | grep -q "Up"; then
        log "Deployment successful!"
        docker compose ps
    else
        error "Deployment failed. Check logs with: docker compose logs"
    fi
}

# Setup systemd service for auto-start
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
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable shadowx-bot.service
    
    log "Systemd service created and enabled"
}

# Setup log rotation
setup_logrotate() {
    log "Setting up log rotation..."
    
    cat > /etc/logrotate.d/shadowx-bot << EOF
$DEPLOY_DIR/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF
    
    log "Log rotation configured"
}

# Setup firewall
setup_firewall() {
    log "Configuring firewall..."
    
    if command -v ufw &> /dev/null; then
        # Allow SSH
        ufw allow ssh
        
        # Allow HTTP/HTTPS if needed
        # ufw allow 80
        # ufw allow 443
        
        # Enable firewall
        ufw --force enable
        
        log "Firewall configured"
    else
        warn "UFW not found, skipping firewall configuration"
    fi
}

# Show status
show_status() {
    log "Deployment Status:"
    echo ""
    
    info "Container Status:"
    docker compose ps
    echo ""
    
    info "Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
    echo ""
    
    info "Recent Logs:"
    docker compose logs --tail=10
    echo ""
    
    info "Useful Commands:"
    echo "  View logs:     cd $DEPLOY_DIR && docker compose logs -f"
    echo "  Restart bot:   cd $DEPLOY_DIR && docker compose restart"
    echo "  Update bot:    cd $DEPLOY_DIR && ./deploy.sh --update"
    echo "  Stop bot:      cd $DEPLOY_DIR && docker compose down"
    echo "  Backup:        cd $DEPLOY_DIR && ./deploy.sh --backup"
    echo ""
}

# Main deployment function
main() {
    log "Starting ShadowX Bot deployment..."
    
    # Parse arguments
    case "${1:-}" in
        --update)
            log "Performing update..."
            create_backup
            setup_repository
            deploy_app
            show_status
            exit 0
            ;;
        --backup)
            create_backup
            exit 0
            ;;
        --status)
            show_status
            exit 0
            ;;
        --help)
            echo "Usage: $0 [--update|--backup|--status|--help]"
            echo ""
            echo "Options:"
            echo "  --update    Update and redeploy the bot"
            echo "  --backup    Create a backup of data and config"
            echo "  --status    Show current deployment status"
            echo "  --help      Show this help message"
            exit 0
            ;;
    esac
    
    # Full deployment
    check_root
    check_docker
    setup_directories
    setup_repository
    setup_environment
    create_backup
    deploy_app
    setup_systemd
    setup_logrotate
    setup_firewall
    show_status
    
    log "Deployment completed successfully!"
    log "Please make sure to configure your .env file with proper values."
}

# Run main function
main "$@"
