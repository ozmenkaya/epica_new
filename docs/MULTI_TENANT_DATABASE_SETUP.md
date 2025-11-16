# Multi-Tenant Database Isolation Setup Guide

## Mimari

Epica, aynı sunucuda farklı müşteriler için **ayrı database'ler** kullanarak çalışır:

```
┌─────────────────────────────────────────────────┐
│  Server: 78.46.162.116                          │
│                                                  │
│  helmex.epica.com.tr → DB: epica_helmex         │
│  acme.epica.com.tr   → DB: epica_acme           │
│  demo.epica.com.tr   → DB: epica_demo           │
│                                                  │
│  ✅ Tek codebase, farklı databases              │
│  ✅ Tam veri izolasyonu                         │
│  ✅ Subdomain otomatik routing                  │
└─────────────────────────────────────────────────┘
```

## Avantajları

- ✅ **Veri izolasyonu**: Her müşteri kendi database'inde
- ✅ **Güvenlik**: Bir müşterinin verisi diğerlerini etkilemez
- ✅ **Kolay yedekleme**: Müşteri bazlı backup/restore
- ✅ **Performance**: Database contention yok
- ✅ **Ölçeklenebilir**: İhtiyaç olunca DB'yi ayrı sunucuya taşıyabilirsiniz

## DNS Gereksinimi

**HAYIR**, ayrı DNS server'a ihtiyacınız yok!

Normal DNS provider'ınızda (Cloudflare, Route53, vs.) wildcard record tanımlayın:

```
Tip: A
Ad:  *.epica.com.tr
IP:  78.46.162.116
```

Bu sayede:
- `helmex.epica.com.tr` → Otomatik çalışır
- `acme.epica.com.tr` → Otomatik çalışır
- `yeni-firma.epica.com.tr` → Otomatik çalışır

## Kurulum Adımları

### 1. Yeni Müşteri Database Oluştur

```bash
# Development/Local
python manage.py create_tenant_db helmex

# Production
ssh root@78.46.162.116
cd /opt/epica
source venv/bin/activate
python manage.py create_tenant_db helmex
```

Bu komut:
1. PostgreSQL database oluşturur (`epica_helmex`)
2. Database user oluşturur
3. Migrations çalıştırır
4. `.env` için config üretir

### 2. .env Dosyasına Ekle

Komut size şöyle bir output verecek:

```bash
Add this to your .env file:
TENANT_DB_HELMEX=postgresql://epica_helmex:password123@localhost/epica_helmex
```

Bu satırı `.env` dosyanıza ekleyin:

```bash
# Production
ssh root@78.46.162.116
nano /opt/epica/.env

# En alta ekle:
TENANT_DB_HELMEX=postgresql://epica_helmex:password123@localhost/epica_helmex
```

### 3. Django'yu Restart Et

```bash
sudo systemctl restart epica
```

### 4. Subdomain DNS'i Ayarla (İlk Sefer İçin)

**Sadece ilk müşteri için** wildcard DNS ekleyin:

Cloudflare/DNS provider'ınızda:
```
Tip: A
Ad:  *
Subdomain: epica.com.tr
IP:  78.46.162.116
TTL: Auto
```

### 5. SSL Sertifikası (Wildcard)

```bash
# Let's Encrypt wildcard sertifika
sudo certbot certonly --manual --preferred-challenges dns \
  -d epica.com.tr -d *.epica.com.tr

# DNS TXT kaydı eklemeniz istenecek
# Cloudflare'de TXT record ekleyin:
# Ad: _acme-challenge
# İçerik: (certbot'un verdiği değer)
```

### 6. Nginx Config Güncelle

```bash
# Production
ssh root@78.46.162.116

# Config dosyasını kopyala
sudo cp /opt/epica/deploy/nginx/epica-multi-tenant /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/epica-multi-tenant /etc/nginx/sites-enabled/epica

# Eski config'i devre dışı bırak (varsa)
sudo rm /etc/nginx/sites-enabled/default

# Test ve reload
sudo nginx -t
sudo systemctl reload nginx
```

### 7. Test Et

```bash
# Subdomain ile test
curl https://helmex.epica.com.tr/health/

# veya tarayıcıda:
https://helmex.epica.com.tr/
```

## Yeni Müşteri Ekleme (Hızlı)

```bash
# 1. Database oluştur
ssh root@78.46.162.116
cd /opt/epica
source venv/bin/activate
python manage.py create_tenant_db acme

# 2. .env'e ekle
nano .env
# TENANT_DB_ACME=postgresql://epica_acme:pass@localhost/epica_acme

# 3. Restart
sudo systemctl restart epica

# 4. Kullanıma hazır!
# https://acme.epica.com.tr/
```

**DNS eklemeye gerek yok!** Wildcard zaten tüm subdomain'leri kapsıyor.

## Update Yönetimi

### Shared Hosting (Aynı Server, Farklı DB'ler)

```bash
# Tüm tenant'ları güncelle
./deploy/deploy_all_tenants.sh

# Sadece bir tenant'ı güncelle
./deploy/deploy_all_tenants.sh --tenant helmex

# Dry run (sadece göster)
./deploy/deploy_all_tenants.sh --dry-run
```

Script şunları yapar:
1. Git pull (tek sefer)
2. Pip install requirements
3. Migrate default database
4. Migrate ALL tenant databases (otomatik)
5. Collectstatic
6. Restart service
7. Health check

### Dedicated Server (Farklı Sunucu)

Büyük müşteri için ayrı sunucu:

1. `deploy/servers.conf` dosyasına ekle:
```
dedicated,bigcorp,1.2.3.4,~/.ssh/id_ed25519_lethe_epica
```

2. Deploy:
```bash
./deploy/deploy_all_tenants.sh
```

Script hem shared hem dedicated sunucuları güncelleyecek!

## Migration Yönetimi

### Tüm Tenant'ları Migrate Et

```bash
# Tüm tenant database'lerini migrate et
python manage.py migrate_all_tenants

# Sadece bir tenant'ı migrate et
python manage.py migrate_all_tenants --tenant helmex

# Fake migrations (test için)
python manage.py migrate_all_tenants --fake-initial
```

### Yeni Migration Oluştur

```bash
# Normal Django migration
python manage.py makemigrations

# Deploy sırasında otomatik olarak tüm tenant'lara uygulanır
./deploy/deploy_all_tenants.sh
```

## Veri Yönetimi

### Backup (Tenant Bazlı)

```bash
# Tek tenant backup
pg_dump -U postgres epica_helmex > backup_helmex_20231116.sql

# Tüm tenant'ları backup
for db in $(psql -U postgres -t -c "SELECT datname FROM pg_database WHERE datname LIKE 'epica_%'"); do
    pg_dump -U postgres $db > backup_${db}_$(date +%Y%m%d).sql
done
```

### Restore

```bash
# Tenant restore
psql -U postgres epica_helmex < backup_helmex_20231116.sql
```

### Tenant Silme

```bash
# Database'i sil
psql -U postgres -c "DROP DATABASE epica_helmex;"

# .env'den kaldır
nano .env
# TENANT_DB_HELMEX satırını sil

# Restart
sudo systemctl restart epica
```

## Monitoring

### Tenant Listesi

```python
# Django shell
python manage.py shell

from django.conf import settings
for db_alias, config in settings.DATABASES.items():
    if db_alias.startswith('tenant_'):
        print(f"{db_alias}: {config['NAME']}")
```

### Database Boyutları

```bash
# PostgreSQL
psql -U postgres -c "
SELECT 
    datname as database,
    pg_size_pretty(pg_database_size(datname)) as size
FROM pg_database
WHERE datname LIKE 'epica_%'
ORDER BY pg_database_size(datname) DESC;
"
```

## Troubleshooting

### Subdomain Çalışmıyor

1. DNS kontrolü:
```bash
nslookup helmex.epica.com.tr
# 78.46.162.116 göstermeli
```

2. Nginx log:
```bash
tail -f /var/log/nginx/epica-subdomains.error.log
```

3. Django log:
```bash
tail -f /opt/epica/logs/errors.log
```

### Database Bağlanamıyor

1. Database var mı:
```bash
psql -U postgres -l | grep epica_helmex
```

2. .env doğru mu:
```bash
grep TENANT_DB_ /opt/epica/.env
```

3. Django ayarları:
```python
python manage.py shell
from django.conf import settings
print(settings.DATABASES)
```

### Migration Hatası

```bash
# Fake initial migration (tablolar zaten varsa)
python manage.py migrate_all_tenants --fake-initial

# Manuel migrate (bir tenant için)
python manage.py migrate --database=tenant_helmex
```

## Performans İyileştirmeleri

### Connection Pooling

```python
# settings.py
DATABASES = {
    'default': {
        # ...
        'CONN_MAX_AGE': 600,  # 10 dakika
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000'  # 30 saniye
        }
    }
}
```

### Database Indexes

```bash
# Her tenant için indexes
python manage.py migrate_all_tenants
```

### Monitoring

```bash
# Active connections per database
psql -U postgres -c "
SELECT 
    datname,
    count(*) as connections
FROM pg_stat_activity
WHERE datname LIKE 'epica_%'
GROUP BY datname;
"
```

## Maliyet Analizi

### Shared Hosting (Şu Anki)

```
Server: €20/month (Hetzner CX11)
Database: Dahil (PostgreSQL)
Toplam: €20/month
Per tenant: €20 / N müşteri
```

**10 müşteri** = €2/müşteri/ay
**20 müşteri** = €1/müşteri/ay

### Dedicated Server

```
Server: €40-100/month
Database: Dahil
Toplam: €40-100/month per müşteri
```

## Sonraki Adımlar

1. ✅ Multi-database routing kuruldu
2. ✅ Subdomain routing hazır
3. ✅ Deployment scripts hazır
4. ⏳ İlk tenant database'i oluştur
5. ⏳ Wildcard DNS ekle
6. ⏳ Wildcard SSL al
7. ⏳ Nginx config güncelle
8. ⏳ Test et!

## Sorular?

- Yeni tenant eklerken DNS eklemem gerekir mi? **HAYIR** (wildcard zaten var)
- Her tenant için ayrı server gerekir mi? **HAYIR** (aynı server, farklı DB)
- Update nasıl yapılır? `./deploy/deploy_all_tenants.sh` (otomatik tüm tenant'ları günceller)
- Backup nasıl alınır? `pg_dump epica_helmex` (tenant bazlı)
