#!/bin/bash
#
# Deploy updates to all tenant servers (shared + dedicated)
#
# Usage:
#   ./deploy/deploy_all_tenants.sh
#   ./deploy/deploy_all_tenants.sh --rollback  # Rollback on error
#   ./deploy/deploy_all_tenants.sh --tenant helmex  # Deploy to specific tenant only
#
# Configuration:
#   - Shared hosting: Deploy to main server, migrate all tenant DBs
#   - Dedicated hosting: Deploy to each customer's server separately

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$SCRIPT_DIR/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/deploy_${TIMESTAMP}.log"

# Options
ROLLBACK_ON_ERROR=false
SPECIFIC_TENANT=""
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --rollback)
            ROLLBACK_ON_ERROR=true
            shift
            ;;
        --tenant)
            SPECIFIC_TENANT="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create log directory
mkdir -p "$LOG_DIR"

# Logging function
log() {
    echo -e "${2:-$NC}$1${NC}" | tee -a "$LOG_FILE"
}

log_success() {
    log "✅ $1" "$GREEN"
}

log_error() {
    log "❌ $1" "$RED"
}

log_warning() {
    log "⚠️  $1" "$YELLOW"
}

log_info() {
    log "ℹ️  $1" "$BLUE"
}

# Header
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "🚀 Epica Multi-Tenant Deployment Script" "$BLUE"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
log "Git branch: $(git branch --show-current)"
log "Git commit: $(git rev-parse --short HEAD)"
log "Log file: $LOG_FILE"
log ""

# Function: Deploy to shared hosting server
deploy_shared_hosting() {
    local server_ip="$1"
    local ssh_key="$2"
    
    log_info "Deploying to SHARED HOSTING server: $server_ip"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN: Would deploy to $server_ip"
        return 0
    fi
    
    # Deploy commands
    ssh -i "$ssh_key" root@$server_ip << 'ENDSSH'
        set -e
        cd /opt/epica
        
        echo "📥 Pulling latest code..."
        git fetch origin
        CURRENT_COMMIT=$(git rev-parse HEAD)
        git pull origin main
        NEW_COMMIT=$(git rev-parse HEAD)
        
        if [ "$CURRENT_COMMIT" = "$NEW_COMMIT" ]; then
            echo "ℹ️  No new changes to deploy"
            exit 0
        fi
        
        echo "🔄 Activating virtual environment..."
        source venv/bin/activate
        
        echo "📦 Installing dependencies..."
        pip install -r requirements.txt --quiet
        
        echo "🗄️  Running migrations on default database..."
        python manage.py migrate --database=default
        
        echo "🗄️  Running migrations on all tenant databases..."
        python manage.py migrate_all_tenants
        
        echo "📁 Collecting static files..."
        python manage.py collectstatic --noinput
        
        echo "♻️  Restarting service..."
        systemctl restart epica
        
        echo "⏳ Waiting for service to start..."
        sleep 3
        
        echo "🔍 Checking service status..."
        systemctl is-active --quiet epica
ENDSSH
    
    if [ $? -eq 0 ]; then
        log_success "Shared hosting deployed successfully"
        
        # Health check
        sleep 2
        if curl -f -s "http://$server_ip/health/" > /dev/null; then
            log_success "Health check passed"
        else
            log_error "Health check failed"
            return 1
        fi
    else
        log_error "Shared hosting deployment failed"
        return 1
    fi
}

# Function: Deploy to dedicated server
deploy_dedicated_server() {
    local tenant_name="$1"
    local server_ip="$2"
    local ssh_key="$3"
    
    log_info "Deploying to DEDICATED server: $tenant_name ($server_ip)"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN: Would deploy to $tenant_name"
        return 0
    fi
    
    # Deploy commands (similar to shared, but single tenant)
    ssh -i "$ssh_key" root@$server_ip << 'ENDSSH'
        set -e
        cd /opt/epica
        
        echo "📥 Pulling latest code..."
        git fetch origin
        CURRENT_COMMIT=$(git rev-parse HEAD)
        git pull origin main
        NEW_COMMIT=$(git rev-parse HEAD)
        
        if [ "$CURRENT_COMMIT" = "$NEW_COMMIT" ]; then
            echo "ℹ️  No new changes to deploy"
            exit 0
        fi
        
        echo "🔄 Activating virtual environment..."
        source venv/bin/activate
        
        echo "📦 Installing dependencies..."
        pip install -r requirements.txt --quiet
        
        echo "🗄️  Running migrations..."
        python manage.py migrate
        
        echo "📁 Collecting static files..."
        python manage.py collectstatic --noinput
        
        echo "♻️  Restarting service..."
        systemctl restart epica
        
        echo "⏳ Waiting for service to start..."
        sleep 3
        
        echo "🔍 Checking service status..."
        systemctl is-active --quiet epica
ENDSSH
    
    if [ $? -eq 0 ]; then
        log_success "$tenant_name deployed successfully"
        
        # Health check
        sleep 2
        if curl -f -s "http://$server_ip/health/" > /dev/null; then
            log_success "Health check passed"
        else
            log_error "Health check failed"
            return 1
        fi
    else
        log_error "$tenant_name deployment failed"
        
        if [ "$ROLLBACK_ON_ERROR" = true ]; then
            log_warning "Rolling back $tenant_name..."
            ssh -i "$ssh_key" root@$server_ip << 'ENDSSH'
                cd /opt/epica
                git checkout HEAD~1
                systemctl restart epica
ENDSSH
        fi
        
        return 1
    fi
}

# Main deployment logic
main() {
    # Load server configuration
    CONFIG_FILE="$SCRIPT_DIR/servers.conf"
    
    if [ ! -f "$CONFIG_FILE" ]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        log_info "Create $CONFIG_FILE with format:"
        log "# type,name,ip,ssh_key"
        log "shared,main,78.46.162.116,~/.ssh/id_ed25519_lethe_epica"
        log "dedicated,bigcorp,1.2.3.4,~/.ssh/id_ed25519_lethe_epica"
        exit 1
    fi
    
    # Statistics
    local total=0
    local success=0
    local failed=0
    local skipped=0
    
    # Read server configuration
    while IFS=',' read -r type name ip ssh_key; do
        # Skip comments and empty lines
        [[ "$type" =~ ^#.*$ ]] && continue
        [[ -z "$type" ]] && continue
        
        # Skip if specific tenant requested and this isn't it
        if [ -n "$SPECIFIC_TENANT" ] && [ "$name" != "$SPECIFIC_TENANT" ]; then
            skipped=$((skipped + 1))
            continue
        fi
        
        total=$((total + 1))
        
        # Expand tilde in ssh_key path
        ssh_key="${ssh_key/#\~/$HOME}"
        
        # Deploy based on type
        if [ "$type" = "shared" ]; then
            if deploy_shared_hosting "$ip" "$ssh_key"; then
                success=$((success + 1))
            else
                failed=$((failed + 1))
                
                if [ "$ROLLBACK_ON_ERROR" = true ]; then
                    log_error "Stopping deployment due to error (rollback enabled)"
                    break
                fi
            fi
        elif [ "$type" = "dedicated" ]; then
            if deploy_dedicated_server "$name" "$ip" "$ssh_key"; then
                success=$((success + 1))
            else
                failed=$((failed + 1))
                
                if [ "$ROLLBACK_ON_ERROR" = true ]; then
                    log_error "Stopping deployment due to error (rollback enabled)"
                    break
                fi
            fi
        else
            log_warning "Unknown server type: $type"
            skipped=$((skipped + 1))
        fi
        
        log ""
        
    done < "$CONFIG_FILE"
    
    # Summary
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "📊 Deployment Summary" "$BLUE"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Total servers: $total"
    log_success "Successful: $success"
    
    if [ $failed -gt 0 ]; then
        log_error "Failed: $failed"
    fi
    
    if [ $skipped -gt 0 ]; then
        log_warning "Skipped: $skipped"
    fi
    
    log ""
    log "Detailed log: $LOG_FILE"
    
    # Exit code
    if [ $failed -gt 0 ]; then
        exit 1
    else
        exit 0
    fi
}

# Run main
main
