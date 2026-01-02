"""
Celery Configuration for Epica
"""
import os
from celery import Celery
from celery.schedules import crontab

# Django ayarlarını yükle
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'epica.settings')

app = Celery('epica')

# Django settings'ten configuration oku
# Bu otomatik olarak Django'yu initialize eder
app.config_from_object('django.conf:settings', namespace='CELERY')

# Task'ları otomatik keşfet
app.autodiscover_tasks()

# Periyodik task'lar (beat scheduler)
app.conf.beat_schedule = {
    # Email kuyruğu temizleme
    'cleanup-old-emails': {
        'task': 'core.tasks.cleanup_old_email_logs',
        'schedule': crontab(hour=3, minute=0),  # Her gün 03:00
    },
    # Başarısız email'leri tekrar dene
    'retry-failed-emails': {
        'task': 'core.tasks.retry_failed_emails',
        'schedule': crontab(minute='*/30'),  # Her 30 dakikada
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
