#!/bin/bash
#
# Telegram Alert Gönderici
# Kullanım: ./telegram_alert.sh "LEVEL" "Mesaj"
# Örnek: ./telegram_alert.sh "CRITICAL" "Disk alanı doldu!"
#

# Konfigürasyonu yükle
CONFIG_FILE="/opt/epica/scripts/alert_config.env"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Telegram ayarları
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${TELEGRAM_CHAT_ID:-}"

if [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "Telegram ayarları yapılandırılmamış. alert_config.env dosyasını kontrol edin."
    exit 1
fi

LEVEL="${1:-INFO}"
MESSAGE="${2:-Test mesajı}"

# Emoji seç
case $LEVEL in
    "CRITICAL")
        EMOJI="🔴"
        ;;
    "WARNING")
        EMOJI="🟡"
        ;;
    "OK")
        EMOJI="🟢"
        ;;
    *)
        EMOJI="ℹ️"
        ;;
esac

# Mesaj formatla
FORMATTED_MESSAGE="$EMOJI *Epica Alert: $LEVEL*

$MESSAGE

_$(date '+%Y-%m-%d %H:%M:%S')_
_Server: $(hostname)_"

# Telegram'a gönder
curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
    -d chat_id="$CHAT_ID" \
    -d text="$FORMATTED_MESSAGE" \
    -d parse_mode="Markdown" \
    > /dev/null

echo "Telegram alert gönderildi: $LEVEL"
