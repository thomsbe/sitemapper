#!/bin/bash
#
# Sitemapper Service Monitor Script
#
# This script provides monitoring capabilities for the sitemapper service,
# including health checks, log analysis, and alerting functionality.
#
# Usage:
#   ./monitor-sitemapper.sh [command]
#
# Commands:
#   status      - Check service status
#   health      - Perform health check
#   logs        - Show recent logs
#   errors      - Show recent errors
#   stats       - Show processing statistics
#   alert       - Check for alert conditions
#

set -euo pipefail

# Configuration
SITEMAPPER_SERVICE="sitemapper.service"
SITEMAPPER_TIMER="sitemapper.timer"
LOG_FILE="/var/log/sitemapper/sitemapper.log"
PID_FILE="/var/run/sitemapper.pid"
CONFIG_FILE="/etc/sitemapper/config.toml"
OUTPUT_DIR="/var/www/html/sitemaps"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
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

# Check if running as root or with sudo
check_permissions() {
    if [[ $EUID -ne 0 ]] && ! groups | grep -q sudo; then
        error "This script requires root privileges or sudo access for some operations"
        return 1
    fi
}

# Check service status
check_service_status() {
    log "Checking sitemapper service status..."
    
    if systemctl is-active --quiet "$SITEMAPPER_SERVICE"; then
        success "Service is active"
    else
        warning "Service is not active"
        systemctl status "$SITEMAPPER_SERVICE" --no-pager -l
    fi
    
    if systemctl is-enabled --quiet "$SITEMAPPER_SERVICE"; then
        success "Service is enabled"
    else
        warning "Service is not enabled"
    fi
    
    # Check timer if it exists
    if systemctl list-unit-files | grep -q "$SITEMAPPER_TIMER"; then
        if systemctl is-active --quiet "$SITEMAPPER_TIMER"; then
            success "Timer is active"
        else
            warning "Timer is not active"
        fi
        
        log "Next scheduled run:"
        systemctl list-timers "$SITEMAPPER_TIMER" --no-pager
    fi
}

# Perform health check
perform_health_check() {
    log "Performing sitemapper health check..."
    
    local exit_code=0
    
    # Check configuration file
    if [[ -f "$CONFIG_FILE" ]]; then
        success "Configuration file exists: $CONFIG_FILE"
        
        # Validate configuration
        if uvx sitemapper --config "$CONFIG_FILE" --dry-run >/dev/null 2>&1; then
            success "Configuration is valid"
        else
            error "Configuration validation failed"
            exit_code=1
        fi
    else
        error "Configuration file not found: $CONFIG_FILE"
        exit_code=1
    fi
    
    # Check output directory
    if [[ -d "$OUTPUT_DIR" ]]; then
        success "Output directory exists: $OUTPUT_DIR"
        
        # Check write permissions
        if [[ -w "$OUTPUT_DIR" ]]; then
            success "Output directory is writable"
        else
            error "Output directory is not writable"
            exit_code=1
        fi
    else
        error "Output directory not found: $OUTPUT_DIR"
        exit_code=1
    fi
    
    # Check log file
    if [[ -f "$LOG_FILE" ]]; then
        success "Log file exists: $LOG_FILE"
        
        # Check for recent activity (last 24 hours)
        if find "$LOG_FILE" -mtime -1 | grep -q .; then
            success "Log file has recent activity"
        else
            warning "Log file has no recent activity (older than 24 hours)"
        fi
    else
        warning "Log file not found: $LOG_FILE"
    fi
    
    # Check PID file if service is supposed to be running
    if systemctl is-active --quiet "$SITEMAPPER_SERVICE"; then
        if [[ -f "$PID_FILE" ]]; then
            local pid=$(cat "$PID_FILE")
            if kill -0 "$pid" 2>/dev/null; then
                success "Process is running (PID: $pid)"
            else
                error "PID file exists but process is not running"
                exit_code=1
            fi
        else
            warning "Service is active but PID file not found"
        fi
    fi
    
    return $exit_code
}

# Show recent logs
show_logs() {
    local lines=${1:-50}
    
    log "Showing last $lines lines from sitemapper logs..."
    
    if [[ -f "$LOG_FILE" ]]; then
        tail -n "$lines" "$LOG_FILE"
    else
        # Try journalctl if log file doesn't exist
        log "Log file not found, checking systemd journal..."
        journalctl -u "$SITEMAPPER_SERVICE" -n "$lines" --no-pager
    fi
}

# Show recent errors
show_errors() {
    local hours=${1:-24}
    
    log "Showing errors from last $hours hours..."
    
    if [[ -f "$LOG_FILE" ]]; then
        # Show errors from log file
        grep -i "error\|exception\|failed" "$LOG_FILE" | tail -20
    else
        # Try journalctl
        journalctl -u "$SITEMAPPER_SERVICE" --since "${hours} hours ago" --no-pager | grep -i "error\|exception\|failed"
    fi
}

# Show processing statistics
show_stats() {
    log "Analyzing sitemapper processing statistics..."
    
    if [[ ! -f "$LOG_FILE" ]]; then
        error "Log file not found: $LOG_FILE"
        return 1
    fi
    
    # Extract statistics from logs
    local total_runs=$(grep -c "Sitemapper service starting" "$LOG_FILE" 2>/dev/null || echo "0")
    local successful_runs=$(grep -c "exit_code.*SUCCESS" "$LOG_FILE" 2>/dev/null || echo "0")
    local failed_runs=$(grep -c "exit_code.*ERROR" "$LOG_FILE" 2>/dev/null || echo "0")
    
    echo "Processing Statistics:"
    echo "  Total runs: $total_runs"
    echo "  Successful runs: $successful_runs"
    echo "  Failed runs: $failed_runs"
    
    if [[ $total_runs -gt 0 ]]; then
        local success_rate=$((successful_runs * 100 / total_runs))
        echo "  Success rate: ${success_rate}%"
    fi
    
    # Show recent sitemap files
    if [[ -d "$OUTPUT_DIR" ]]; then
        local file_count=$(find "$OUTPUT_DIR" -name "*.xml*" -type f | wc -l)
        echo "  Sitemap files: $file_count"
        
        if [[ $file_count -gt 0 ]]; then
            echo "  Most recent files:"
            find "$OUTPUT_DIR" -name "*.xml*" -type f -printf "%T@ %p\n" | sort -n | tail -5 | while read timestamp file; do
                local date=$(date -d "@$timestamp" '+%Y-%m-%d %H:%M:%S')
                echo "    $date - $(basename "$file")"
            done
        fi
    fi
}

# Check for alert conditions
check_alerts() {
    log "Checking for alert conditions..."
    
    local alerts=0
    
    # Check if service failed recently
    if systemctl is-failed --quiet "$SITEMAPPER_SERVICE"; then
        error "Service is in failed state"
        alerts=$((alerts + 1))
    fi
    
    # Check for recent errors in logs
    if [[ -f "$LOG_FILE" ]]; then
        local recent_errors=$(grep -c "ERROR" "$LOG_FILE" 2>/dev/null || echo "0")
        if [[ $recent_errors -gt 10 ]]; then
            error "High number of recent errors: $recent_errors"
            alerts=$((alerts + 1))
        fi
    fi
    
    # Check disk space in output directory
    if [[ -d "$OUTPUT_DIR" ]]; then
        local disk_usage=$(df "$OUTPUT_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
        if [[ $disk_usage -gt 90 ]]; then
            error "Disk usage is high: ${disk_usage}%"
            alerts=$((alerts + 1))
        fi
    fi
    
    # Check if sitemaps are outdated (older than 2 days)
    if [[ -d "$OUTPUT_DIR" ]]; then
        local old_files=$(find "$OUTPUT_DIR" -name "*.xml*" -type f -mtime +2 | wc -l)
        if [[ $old_files -gt 0 ]]; then
            warning "Found $old_files sitemap files older than 2 days"
        fi
    fi
    
    if [[ $alerts -eq 0 ]]; then
        success "No alert conditions detected"
    else
        error "Found $alerts alert conditions"
    fi
    
    return $alerts
}

# Main function
main() {
    local command=${1:-status}
    
    case "$command" in
        status)
            check_service_status
            ;;
        health)
            perform_health_check
            ;;
        logs)
            show_logs "${2:-50}"
            ;;
        errors)
            show_errors "${2:-24}"
            ;;
        stats)
            show_stats
            ;;
        alerts)
            check_alerts
            ;;
        *)
            echo "Usage: $0 {status|health|logs|errors|stats|alerts}"
            echo ""
            echo "Commands:"
            echo "  status      - Check service status"
            echo "  health      - Perform health check"
            echo "  logs [n]    - Show last n lines of logs (default: 50)"
            echo "  errors [h]  - Show errors from last h hours (default: 24)"
            echo "  stats       - Show processing statistics"
            echo "  alerts      - Check for alert conditions"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"