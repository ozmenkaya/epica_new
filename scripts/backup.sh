#!/bin/bash
#
# Epica Otomatik Yedekleme Scripti
# Çalıştırma: ./backup.sh [daily|weekly|manual]
# Cron örneği: 0 2 * * * /opt/epica/scripts/backup.sh daily >> /var/log/epica_backup.log 2>&1
#

set -e

# Konfigürasyon
APP_DIR="/opt/epica"
BACKUP_DIR="/mnt/HC_Volume_104123408/backups"
MEDIA_DIR="/mnt/HC_Volume_104123408/media"
LOG_FILE="/var/log/epica_backup.log"
DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_TYPE="${1:-daily}"

# Renk kodları (log için)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Log fonksiyonu
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

# Klasör yapısını oluştur
mkdir -p "$BACKUP_DIR"/{daily,weekly,monthly,manual}
mkdir -p "$BACKUP_DIR/db"

log "=== Epica Yedekleme Başladı ($BACKUP_TYPE) ==="

# Yedekleme klasörünü belirle
case $BACKUP_TYPE in
    daily)
        TARGET_DIR="$BACKUP_DIR/daily"
        KEEP_DAYS=7
        ;;
    weekly)
        TARGET_DIR="$BACKUP_DIR/weekly"
        KEEP_DAYS=28
        ;;
    monthly)
        TARGET_DIR="$BACKUP_DIR/monthly"
        KEEP_DAYS=365
        ;;
    manual)
        TARGET_DIR="$BACKUP_DIR/manual"
        KEEP_DAYS=30
        ;;
    *)
        error "Geçersiz yedekleme tipi: $BACKUP_TYPE"
        exit 1
        ;;
esac

# 1. Ana veritabanını yedekle
log "Ana veritabanı yedekleniyor..."
if [ -f "$APP_DIR/db.sqlite3" ]; then
    # SQLite online backup (safe while app is running)
    sqlite3 "$APP_DIR/db.sqlite3" ".backup '$TARGET_DIR/db_main_$DATE.sqlite3'"
    
    # Sıkıştır
    gzip -f "$TARGET_DIR/db_main_$DATE.sqlite3"
    log "Ana veritabanı yedeklendi: db_main_$DATE.sqlite3.gz"
else
    error "Ana veritabanı bulunamadı!"
fi

# 2. Tenant veritabanlarını yedekle
log "Tenant veritabanları yedekleniyor..."
if [ -d "$APP_DIR/tenant_dbs" ]; then
    for db_file in "$APP_DIR/tenant_dbs"/*.sqlite3; do
        if [ -f "$db_file" ]; then
            db_name=$(basename "$db_file" .sqlite3)
            sqlite3 "$db_file" ".backup '$TARGET_DIR/db_${db_name}_$DATE.sqlite3'"
            gzip -f "$TARGET_DIR/db_${db_name}_$DATE.sqlite3"
            log "Tenant yedeklendi: $db_name"
        fi
    done
else
    log "Tenant veritabanı klasörü bulunamadı, atlanıyor..."
fi

# 3. Media dosyalarını yedekle (haftalık ve aylık için)
if [[ "$BACKUP_TYPE" == "weekly" || "$BACKUP_TYPE" == "monthly" || "$BACKUP_TYPE" == "manual" ]]; then
    log "Media dosyaları yedekleniyor..."
    if [ -d "$MEDIA_DIR" ] && [ "$(ls -A $MEDIA_DIR 2>/dev/null)" ]; then
        tar -czf "$TARGET_DIR/media_$DATE.tar.gz" -C "$(dirname $MEDIA_DIR)" "$(basename $MEDIA_DIR)" 2>/dev/null || true
        log "Media yedeklendi: media_$DATE.tar.gz"
    else
        log "Media klasörü boş veya yok, atlanıyor..."
    fi
fi

# 4. Konfigürasyon dosyalarını yedekle
log "Konfigürasyon dosyaları yedekleniyor..."
CONFIG_BACKUP="$TARGET_DIR/config_$DATE.tar.gz"
tar -czf "$CONFIG_BACKUP" \
    -C "$APP_DIR" \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='*.sqlite3' \
    --exclude='media' \
    --exclude='static' \
    --exclude='logs' \
    epica/settings.py \
    requirements.txt \
    2>/dev/null || true
log "Konfigürasyon yedeklendi: config_$DATE.tar.gz"

# 5. Eski yedekleri temizle
log "Eski yedekler temizleniyor ($KEEP_DAYS gün öncesi)..."
find "$TARGET_DIR" -type f -mtime +$KEEP_DAYS -delete 2>/dev/null || true

# 6. Yedekleme özeti
BACKUP_SIZE=$(du -sh "$TARGET_DIR" 2>/dev/null | cut -f1)
TOTAL_BACKUPS=$(find "$BACKUP_DIR" -type f -name "*.gz" | wc -l)
DISK_FREE=$(df -h "$BACKUP_DIR" | tail -1 | awk '{print $4}')

log "=== Yedekleme Tamamlandı ==="
log "Yedekleme klasörü: $TARGET_DIR"
log "Bu tip için toplam boyut: $BACKUP_SIZE"
log "Toplam yedek dosya sayısı: $TOTAL_BACKUPS"
log "Kalan disk alanı: $DISK_FREE"

# 7. Başarı durumunu kaydet (monitoring için)
echo "$DATE|$BACKUP_TYPE|SUCCESS" >> "$BACKUP_DIR/backup_history.log"

# Eğer disk alanı %90 üzerindeyse uyar
DISK_PERCENT=$(df "$BACKUP_DIR" | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$DISK_PERCENT" -gt 90 ]; then
    error "UYARI: Disk alanı kritik! %$DISK_PERCENT dolu."
    # Buraya email/webhook alert eklenebilir
fi

exit 0
