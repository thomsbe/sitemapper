#!/bin/bash
#
# Sitemapper Service Installation Script
#
# This script installs and configures the sitemapper as a systemd service
# with proper permissions, logging, and monitoring setup.
#
# Usage:
#   sudo ./install-service.sh [options]
#
# Options:
#   --user USER          - User to run the service as (default: sitemapper)
#   --config-dir DIR     - Configuration directory (default: /etc/sitemapper)
#   --log-dir DIR        - Log directory (default: /var/log/sitemapper)
#   --output-dir DIR     - Sitemap output directory (default: /var/www/html/sitemaps)
#   --install-uvx        - Install uv and uvx if not present
#   --enable-timer       - Enable systemd timer for scheduled runs
#   --help               - Show this help message
#

set -euo pipefail

# Default configuration
DEFAULT_USER="sitemapper"
DEFAULT_CONFIG_DIR="/etc/sitemapper"
DEFAULT_LOG_DIR="/var/log/sitemapper"
DEFAULT_OUTPUT_DIR="/var/www/html/sitemaps"
DEFAULT_INSTALL_UVX=false
DEFAULT_ENABLE_TIMER=false

# Parse command line arguments
USER="$DEFAULT_USER"
CONFIG_DIR="$DEFAULT_CONFIG_DIR"
LOG_DIR="$DEFAULT_LOG_DIR"
OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"
INSTALL_UVX="$DEFAULT_INSTALL_UVX"
ENABLE_TIMER="$DEFAULT_ENABLE_TIMER"

while [[ $# -gt 0 ]]; do
    case $1 in
        --user)
            USER="$2"
            shift 2
            ;;
        --config-dir)
            CONFIG_DIR="$2"
            shift 2
            ;;
        --log-dir)
            LOG_DIR="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --install-uvx)
            INSTALL_UVX=true
            shift
            ;;
        --enable-timer)
            ENABLE_TIMER=true
            shift
            ;;
        --help)
            grep "^#" "$0" | sed 's/^# //' | head -20
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Create system user
create_user() {
    log "Creating system user: $USER"
    
    if id "$USER" &>/dev/null; then
        success "User $USER already exists"
    else
        useradd --system --shell /bin/false --home-dir /nonexistent --no-create-home "$USER"
        success "Created system user: $USER"
    fi
}

# Create directories
create_directories() {
    log "Creating directories..."
    
    # Configuration directory
    mkdir -p "$CONFIG_DIR"
    chown root:root "$CONFIG_DIR"
    chmod 755 "$CONFIG_DIR"
    success "Created configuration directory: $CONFIG_DIR"
    
    # Log directory
    mkdir -p "$LOG_DIR"
    chown "$USER:$USER" "$LOG_DIR"
    chmod 755 "$LOG_DIR"
    success "Created log directory: $LOG_DIR"
    
    # Output directory
    mkdir -p "$OUTPUT_DIR"
    chown "$USER:$USER" "$OUTPUT_DIR"
    chmod 755 "$OUTPUT_DIR"
    success "Created output directory: $OUTPUT_DIR"
    
    # Runtime directory for PID file
    mkdir -p /var/run
    success "Runtime directory ready"
}

# Install uv and uvx if requested
install_uvx() {
    if [[ "$INSTALL_UVX" == "true" ]]; then
        log "Installing uv and uvx..."
        
        if command -v uv &>/dev/null; then
            success "uv is already installed"
        else
            # Install uv using the official installer
            curl -LsSf https://astral.sh/uv/install.sh | sh
            
            # Add to PATH for current session
            export PATH="$HOME/.cargo/bin:$PATH"
            
            if command -v uv &>/dev/null; then
                success "uv installed successfully"
            else
                error "Failed to install uv"
                exit 1
            fi
        fi
        
        if command -v uvx &>/dev/null; then
            success "uvx is available"
        else
            error "uvx is not available after uv installation"
            exit 1
        fi
    else
        # Check if uvx is available
        if ! command -v uvx &>/dev/null; then
            warning "uvx is not installed. The service may not work properly."
            warning "Run with --install-uvx to install uv and uvx automatically."
        else
            success "uvx is available"
        fi
    fi
}

# Install systemd service files
install_service_files() {
    log "Installing systemd service files..."
    
    # Check if template files exist
    if [[ ! -f "templates/systemd/sitemapper.service" ]]; then
        error "Service template not found: templates/systemd/sitemapper.service"
        exit 1
    fi
    
    # Copy and customize service file
    cp "templates/systemd/sitemapper.service" "/etc/systemd/system/sitemapper.service"
    
    # Update paths in service file
    sed -i "s|User=sitemapper|User=$USER|g" "/etc/systemd/system/sitemapper.service"
    sed -i "s|/etc/sitemapper/config.toml|$CONFIG_DIR/config.toml|g" "/etc/systemd/system/sitemapper.service"
    sed -i "s|ReadWritePaths=.*|ReadWritePaths=$LOG_DIR /var/run $OUTPUT_DIR|g" "/etc/systemd/system/sitemapper.service"
    
    success "Installed systemd service file"
    
    # Install timer if requested
    if [[ "$ENABLE_TIMER" == "true" ]]; then
        if [[ -f "templates/systemd/sitemapper.timer" ]]; then
            cp "templates/systemd/sitemapper.timer" "/etc/systemd/system/sitemapper.timer"
            success "Installed systemd timer file"
        else
            warning "Timer template not found, skipping timer installation"
        fi
    fi
    
    # Reload systemd
    systemctl daemon-reload
    success "Reloaded systemd configuration"
}

# Install configuration file
install_config() {
    log "Installing configuration file..."
    
    local config_file="$CONFIG_DIR/config.toml"
    
    if [[ -f "$config_file" ]]; then
        warning "Configuration file already exists: $config_file"
        warning "Creating backup and installing new example config"
        cp "$config_file" "$config_file.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    if [[ -f "templates/config/sitemapper-example.toml" ]]; then
        cp "templates/config/sitemapper-example.toml" "$config_file"
        
        # Update paths in config file
        sed -i "s|output_dir = \".*\"|output_dir = \"$OUTPUT_DIR\"|g" "$config_file"
        
        chown root:root "$config_file"
        chmod 644 "$config_file"
        success "Installed configuration file: $config_file"
        
        warning "Please edit $config_file to configure your Solr cores"
    else
        error "Configuration template not found: templates/config/sitemapper-example.toml"
        exit 1
    fi
}

# Install monitoring script
install_monitoring() {
    log "Installing monitoring script..."
    
    if [[ -f "scripts/monitor-sitemapper.sh" ]]; then
        cp "scripts/monitor-sitemapper.sh" "/usr/local/bin/monitor-sitemapper"
        chmod +x "/usr/local/bin/monitor-sitemapper"
        
        # Update paths in monitoring script
        sed -i "s|LOG_FILE=\".*\"|LOG_FILE=\"$LOG_DIR/sitemapper.log\"|g" "/usr/local/bin/monitor-sitemapper"
        sed -i "s|CONFIG_FILE=\".*\"|CONFIG_FILE=\"$CONFIG_DIR/config.toml\"|g" "/usr/local/bin/monitor-sitemapper"
        sed -i "s|OUTPUT_DIR=\".*\"|OUTPUT_DIR=\"$OUTPUT_DIR\"|g" "/usr/local/bin/monitor-sitemapper"
        
        success "Installed monitoring script: /usr/local/bin/monitor-sitemapper"
    else
        warning "Monitoring script not found, skipping installation"
    fi
}

# Configure logrotate
configure_logrotate() {
    log "Configuring log rotation..."
    
    cat > "/etc/logrotate.d/sitemapper" << EOF
$LOG_DIR/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 $USER $USER
    postrotate
        systemctl reload-or-restart sitemapper.service 2>/dev/null || true
    endscript
}
EOF
    
    success "Configured log rotation"
}

# Enable and start service
enable_service() {
    log "Enabling and starting service..."
    
    # Enable service
    systemctl enable sitemapper.service
    success "Enabled sitemapper service"
    
    # Enable timer if installed
    if [[ "$ENABLE_TIMER" == "true" ]] && [[ -f "/etc/systemd/system/sitemapper.timer" ]]; then
        systemctl enable sitemapper.timer
        systemctl start sitemapper.timer
        success "Enabled and started sitemapper timer"
    fi
    
    # Test configuration
    log "Testing configuration..."
    if uvx sitemapper --config "$CONFIG_DIR/config.toml" --dry-run; then
        success "Configuration test passed"
    else
        error "Configuration test failed"
        warning "Please check and update $CONFIG_DIR/config.toml"
    fi
}

# Print installation summary
print_summary() {
    echo ""
    success "Sitemapper service installation completed!"
    echo ""
    echo "Configuration:"
    echo "  User: $USER"
    echo "  Config: $CONFIG_DIR/config.toml"
    echo "  Logs: $LOG_DIR/"
    echo "  Output: $OUTPUT_DIR/"
    echo ""
    echo "Next steps:"
    echo "  1. Edit the configuration file: $CONFIG_DIR/config.toml"
    echo "  2. Configure your Solr cores and URL patterns"
    echo "  3. Test the configuration: uvx sitemapper --config $CONFIG_DIR/config.toml --dry-run"
    echo "  4. Run manually: systemctl start sitemapper.service"
    echo "  5. Check status: systemctl status sitemapper.service"
    echo "  6. Monitor: /usr/local/bin/monitor-sitemapper status"
    echo ""
    
    if [[ "$ENABLE_TIMER" == "true" ]]; then
        echo "Timer is enabled and will run daily at 2:00 AM"
        echo "Check timer status: systemctl status sitemapper.timer"
        echo ""
    fi
}

# Main installation function
main() {
    log "Starting sitemapper service installation..."
    
    check_root
    create_user
    create_directories
    install_uvx
    install_service_files
    install_config
    install_monitoring
    configure_logrotate
    enable_service
    print_summary
}

# Run main function
main "$@"