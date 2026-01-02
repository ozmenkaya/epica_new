# Epica Email Queue System (Celery + Redis)

## 📋 Kurulum Özeti

### Kurulu Bileşenler
- **Redis Server**: Message broker
- **Celery Worker**: 4 concurrent worker (celery, emails, bulk_emails queues)
- **Celery Beat**: Periyodik task scheduler
- **django-celery-results**: Task sonuçlarını DB'de sakla
- **django-celery-beat**: Periyodik task yönetimi (admin panel'den)

### Servisler
```bash
systemctl status redis-server      # Redis durumu
systemctl status celery-worker     # Celery worker durumu
systemctl status celery-beat       # Beat scheduler durumu

# Yeniden başlatma
systemctl restart celery-worker
systemctl restart celery-beat
```

## 🚀 Kullanım

### 1. Basit Email Gönderme (Async)
```python
from core.tasks import send_email_async

# Background'da email gönder
task = send_email_async(
    subject="Hoşgeldiniz",
    message="Sisteme başarıyla kaydoldunuz.",
    from_email="no-reply@epica.com",
    recipient_list=["user@example.com"]
)

print(f"Task ID: {task.id}")
```

### 2. HTML Email Gönderme
```python
from core.tasks import send_email_async

html_content = "<h1>Hoşgeldiniz!</h1><p>Sisteme kaydoldunuz.</p>"

task = send_email_async(
    subject="Hoşgeldiniz",
    message="Sisteme kaydoldunuz.",  # Plain text fallback
    from_email="no-reply@epica.com",
    recipient_list=["user@example.com"],
    html_message=html_content
)
```

### 3. Template ile Email Gönderme
```python
from core.tasks import send_templated_email_async

task = send_templated_email_async(
    subject="Şifre Sıfırlama",
    template_name="emails/password_reset.html",
    context={
        'user': user,
        'reset_link': 'https://example.com/reset/...',
        'expires_in': '24 saat'
    },
    from_email="no-reply@epica.com",
    recipient_list=[user.email]
)
```

### 4. Toplu Email Gönderme
```python
from core.tasks import send_bulk_emails_task

emails = [
    {
        'subject': 'Newsletter',
        'message': 'Bu ayın haberleri...',
        'from_email': 'newsletter@epica.com',
        'recipient_list': ['user1@example.com'],
    },
    {
        'subject': 'Newsletter',
        'message': 'Bu ayın haberleri...',
        'from_email': 'newsletter@epica.com',
        'recipient_list': ['user2@example.com'],
    },
    # ... daha fazla
]

# Her email ayrı task olarak kuyruğa eklenir
results = send_bulk_emails_task.delay(emails)
```

### 5. Task Durumu Kontrolü
```python
from celery.result import AsyncResult

task_id = "5cdb9670-a75a-4058-8f86-dc93aad51b9f"
result = AsyncResult(task_id)

print(f"Status: {result.status}")  # PENDING, STARTED, SUCCESS, FAILURE
print(f"Result: {result.result}")  # Task'ın dönüş değeri

# Task tamamlanana kadar bekle
result.get(timeout=10)  # 10 saniye timeout
```

### 6. Django Admin'den Periyodik Task Ekleme
1. Admin panele gir: `/admin/`
2. `Django Celery Beat` > `Periodic tasks`
3. "Add periodic task" tıkla
4. Task seç, zamanlama ayarla

## 🔄 Mevcut Kodları Güncelleme

### Eski (Senkron):
```python
from django.core.mail import send_mail

send_mail(
    subject="Test",
    message="Mesaj",
    from_email="no-reply@epica.com",
    recipient_list=["user@example.com"]
)
```

### Yeni (Asenkron):
```python
from core.tasks import send_email_async

send_email_async(
    subject="Test",
    message="Mesaj",
    from_email="no-reply@epica.com",
    recipient_list=["user@example.com"]
)
```

## 📊 Monitoring & Debugging

### Celery İstatistikleri
```bash
# Worker'ları listele
celery -A epica inspect active

# Aktif task'lar
celery -A epica inspect active_queues

# İstatistikler
celery -A epica inspect stats
```

### Task Geçmişi (Django Admin)
- `/admin/django_celery_results/taskresult/`
- Son task'lar, başarılı/başarısız durumlar
- Her task'ın detaylı sonucu

### Loglar
```bash
tail -f /var/log/celery/worker.log   # Worker log
tail -f /var/log/celery/beat.log     # Beat scheduler log
```

### Redis Monitoring
```bash
redis-cli info stats        # Redis istatistikleri
redis-cli llen celery       # Celery queue uzunluğu
redis-cli monitor           # Real-time komutları izle
```

## ⚙️ Konfigürasyon

### Queue Önceliklendirme
```python
# settings.py
CELERY_TASK_ROUTES = {
    'core.tasks.send_email_task': {'queue': 'emails', 'priority': 9},
    'core.tasks.send_bulk_emails_task': {'queue': 'bulk_emails', 'priority': 5},
}
```

### Retry Ayarları
```python
@shared_task(bind=True, max_retries=5, default_retry_delay=600)
def my_task(self):
    try:
        # Task işlemleri
        pass
    except Exception as exc:
        # 10 dakika sonra tekrar dene
        raise self.retry(exc=exc, countdown=600)
```

### Worker Concurrency
```bash
# Daha fazla worker
celery -A epica worker --concurrency=8

# Auto-scale (min-max)
celery -A epica worker --autoscale=10,3
```

## 🛠️ Otomatik Task'lar

### Periyodik Task'lar (Celery Beat)
- **cleanup_old_email_logs**: Her gün 03:00'da eski logları temizle (30+ gün)
- **retry_failed_emails**: Her 30 dakikada başarısız email'leri tekrar dene

### Custom Periyodik Task Ekleme
```python
# epica/celery.py
app.conf.beat_schedule = {
    'send-daily-report': {
        'task': 'core.tasks.send_daily_report',
        'schedule': crontab(hour=8, minute=0),  # Her gün 08:00
    },
}
```

## 📈 Performance Tips

1. **Email'leri Batch'le**: Toplu gönderimi `send_bulk_emails_task` ile yap
2. **Rate Limiting**: `@shared_task(rate_limit='100/m')` - dakikada max 100
3. **Task Timeout**: Uzun süren işler için timeout ayarla
4. **Result Backend**: Gereksiz result storage'ı kapat: `ignore_result=True`

## 🔧 Troubleshooting

### Worker Çalışmıyor
```bash
systemctl status celery-worker
journalctl -u celery-worker -n 50
```

### Task Kuyruğa Girmiyor
```bash
# Redis bağlantısını test et
redis-cli ping

# Celery'nin Redis'e bağlanıp bağlanmadığını kontrol et
celery -A epica inspect ping
```

### Email Gönderilmiyor
```python
# Django settings'te EMAIL ayarlarını kontrol et
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Test', 'from@example.com', ['to@example.com'])
```

## 📝 Notlar

- Task'lar otomatik 3 kez retry edilir (5 dakika arayla)
- Task sonuçları DB'de 30 gün saklanır (otomatik temizleme)
- Worker restart olsa bile pending task'lar kaybolmaz (Redis'te saklanır)
- Production'da `--uid deploy` ile worker çalıştırın (security)

## 🎯 Sonraki Adımlar

- [ ] Mevcut `send_mail()` çağrılarını `send_email_async()` ile değiştir
- [ ] Email template'leri oluştur (`templates/emails/`)
- [ ] Monitoring dashboard ekle (Flower: `pip install flower`)
- [ ] Email tracking (açılma, tıklama) ekle
- [ ] SES/SendGrid gibi email provider entegrasyonu
