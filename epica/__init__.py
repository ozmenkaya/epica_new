# Celery'yi Django ile entegre et
from .celery import app as celery_app

__all__ = ('celery_app',)
