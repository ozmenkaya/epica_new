#!/bin/bash
#
# Epica Sistem Monitoring Scripti
# Çalıştırma: ./monitor.sh
# Cron: */5 * * * * /opt/epica/scripts/monitor.sh >> /var/log/epica_monitor.log 2>&1
#

set -e

# Konfigürasyon
APP_DIR="/opt/epica"
LOG_DIR="/var/log"
ALERT_LOG="/var/log/epica_alerts.log"
METRICS_FILE="/tmp/epica_metrics.json"

# Eşik değerleri
CPU_THRESHOLD=90
MEMORY_THRESHOLD=90
DISK_THRESHOLD=90
RESPONSE_THRESHOLD=5000  # ms

# Alert konfigürasyonu (email veya webhook)
ALERT_EMAIL="${ALERT_EMAIL:-}"  # Environment'tan al
WEBHOOK_URL="${WEBHOOK_URL:-}"  # Discord/Slack webhook

# Fonksiyonlar
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

alert() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo "[$timestamp] [$level] $message" >> "$ALERT_LOG"
    
    # Telegram alert
    if [ -f "/opt/epica/scripts/telegram_alert.sh" ]; then
        source /opt/epica/scripts/alert_config.env 2>/dev/null
        if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
            /opt/epica/scripts/telegram_alert.sh "$level" "$message" 2>/dev/null || true
        fi
    fi
    
    # Email alert
    if [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "[Epica $level] Alert" "$ALERT_EMAIL" 2>/dev/null || true
    fi
    
    # Webhook alert (Discord/Slack compatible)
    if [ -n "$WEBHOOK_URL" ]; then
        local color="16776960"  # Yellow for warning
        [ "$level" == "CRITICAL" ] && color="16711680"  # Red
        [ "$level" == "OK" ] && color="65280"  # Green
        
        curl -s -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{
                \"embeds\": [{
                    \"title\": \"Epica Alert: $level\",
                    \"description\": \"$message\",
                    \"color\": $color,
                    \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
                }]
            }" 2>/dev/null || true
    fi
}

# 1. CPU Kullanımı
check_cpu() {
    local cpu=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'.' -f1)
    if [ -z "$cpu" ]; then
        cpu=$(cat /proc/stat | grep '^cpu ' | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print int(usage)}')
    fi
    
    echo "cpu_percent=$cpu"
    
    if [ "$cpu" -gt "$CPU_THRESHOLD" ]; then
        alert "WARNING" "CPU kullanımı yüksek: %$cpu"
        return 1
    fi
    return 0
}

# 2. Bellek Kullanımı
check_memory() {
    local mem_info=$(free | grep Mem)
    local total=$(echo $mem_info | awk '{print $2}')
    local used=$(echo $mem_info | awk '{print $3}')
    local percent=$((used * 100 / total))
    
    echo "memory_percent=$percent"
    echo "memory_total_mb=$((total / 1024))"
    echo "memory_used_mb=$((used / 1024))"
    
    if [ "$percent" -gt "$MEMORY_THRESHOLD" ]; then
        alert "WARNING" "Bellek kullanımı yüksek: %$percent"
        return 1
    fi
    return 0
}

# 3. Disk Kullanımı
check_disk() {
    local status=0
    
    # Root disk
    local root_percent=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
    echo "disk_root_percent=$root_percent"
    
    if [ "$root_percent" -gt "$DISK_THRESHOLD" ]; then
        alert "CRITICAL" "Root disk alanı kritik: %$root_percent"
        status=1
    fi
    
    # Media volume
    if df /mnt/HC_Volume_104123408 >/dev/null 2>&1; then
        local media_percent=$(df /mnt/HC_Volume_104123408 | tail -1 | awk '{print $5}' | tr -d '%')
        echo "disk_media_percent=$media_percent"
        
        if [ "$media_percent" -gt "$DISK_THRESHOLD" ]; then
            alert "WARNING" "Media disk alanı yüksek: %$media_percent"
            status=1
        fi
    fi
    
    return $status
}

# 4. Epica Servisi Durumu
check_service() {
    if systemctl is-active --quiet epica; then
        echo "service_epica=running"
        return 0
    else
        alert "CRITICAL" "Epica servisi çalışmıyor!"
        echo "service_epica=stopped"
        
        # Otomatik restart deneme
        log "Servis restart deneniyor..."
        systemctl restart epica
        sleep 3
        
        if systemctl is-active --quiet epica; then
            alert "OK" "Epica servisi otomatik olarak yeniden başlatıldı"
            return 0
        else
            alert "CRITICAL" "Epica servisi başlatılamadı!"
            return 1
        fi
    fi
}

# 5. Nginx Durumu
check_nginx() {
    if systemctl is-active --quiet nginx; then
        echo "service_nginx=running"
        return 0
    else
        alert "CRITICAL" "Nginx servisi çalışmıyor!"
        echo "service_nginx=stopped"
        return 1
    fi
}

# 6. HTTP Response Check
check_http() {
    local url="http://localhost:8000/health/"
    local start=$(date +%s%N)
    local response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")
    local end=$(date +%s%N)
    local duration=$(((end - start) / 1000000))  # ms
    
    echo "http_response_code=$response"
    echo "http_response_time_ms=$duration"
    
    if [ "$response" != "200" ]; then
        alert "CRITICAL" "HTTP endpoint yanıt vermiyor: $url (code: $response)"
        return 1
    fi
    
    if [ "$duration" -gt "$RESPONSE_THRESHOLD" ]; then
        alert "WARNING" "HTTP yanıt süresi yüksek: ${duration}ms"
        return 1
    fi
    
    return 0
}

# 7. Veritabanı Boyutu
check_database() {
    local db_file="$APP_DIR/db.sqlite3"
    if [ -f "$db_file" ]; then
        local size_mb=$(du -m "$db_file" | cut -f1)
        echo "database_size_mb=$size_mb"
        
        # 1GB üzerindeyse uyar
        if [ "$size_mb" -gt 1024 ]; then
            alert "WARNING" "Veritabanı boyutu büyük: ${size_mb}MB"
        fi
    fi
}

# 8. Log Dosyası Boyutları
check_logs() {
    local gunicorn_log="$APP_DIR/logs/gunicorn.log"
    if [ -f "$gunicorn_log" ]; then
        local size_mb=$(du -m "$gunicorn_log" 2>/dev/null | cut -f1 || echo "0")
        echo "log_gunicorn_mb=$size_mb"
        
        # 500MB üzerindeyse rotate et
        if [ "$size_mb" -gt 500 ]; then
            log "Gunicorn log dosyası rotate ediliyor..."
            mv "$gunicorn_log" "${gunicorn_log}.$(date +%Y%m%d)"
            gzip "${gunicorn_log}.$(date +%Y%m%d)"
            systemctl reload epica
        fi
    fi
}

# 9. Aktif Bağlantı Sayısı
check_connections() {
    local conn=$(ss -tuln | grep -c ":8000" || echo "0")
    echo "active_connections=$conn"
}

# 10. Son Hataları Kontrol Et
check_errors() {
    local error_count
    error_count=$(journalctl -u epica --since "5 minutes ago" --no-pager 2>/dev/null | grep -ci "error\|exception\|traceback" 2>/dev/null) || error_count=0
    echo "recent_errors=$error_count"
    
    if [ "$error_count" -gt 10 ]; then
        alert "WARNING" "Son 5 dakikada $error_count hata tespit edildi"
    fi
}

# Ana monitoring döngüsü
main() {
    log "=== Monitoring Check Başladı ==="
    
    local metrics=""
    local has_issues=0
    
    # Tüm kontrolleri çalıştır
    metrics+=$(check_cpu) || has_issues=1
    metrics+="\n"
    metrics+=$(check_memory) || has_issues=1
    metrics+="\n"
    metrics+=$(check_disk) || has_issues=1
    metrics+="\n"
    metrics+=$(check_service) || has_issues=1
    metrics+="\n"
    metrics+=$(check_nginx) || has_issues=1
    metrics+="\n"
    metrics+=$(check_http) || has_issues=1
    metrics+="\n"
    metrics+=$(check_database)
    metrics+="\n"
    metrics+=$(check_logs)
    metrics+="\n"
    metrics+=$(check_connections)
    metrics+="\n"
    metrics+=$(check_errors) || has_issues=1
    
    # Metrikleri kaydet
    echo -e "$metrics" > "$METRICS_FILE"
    echo "timestamp=$(date +%s)" >> "$METRICS_FILE"
    echo "status=$( [ $has_issues -eq 0 ] && echo 'healthy' || echo 'issues' )" >> "$METRICS_FILE"
    
    log "=== Monitoring Check Tamamlandı (status: $( [ $has_issues -eq 0 ] && echo 'OK' || echo 'ISSUES' )) ==="
    
    return $has_issues
}

# Scripti çalıştır
main
