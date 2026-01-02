"""
Email Tasks for Celery
Bu dosyayı /opt/epica/core/tasks.py olarak kopyalayın
"""
from celery import shared_task
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_email_task(self, subject, message, from_email, recipient_list, 
                    html_message=None, fail_silently=False, **kwargs):
    """
    Asenkron email gönderme task'ı
    
    Args:
        subject: Email konusu
        message: Düz metin mesaj
        from_email: Gönderen email adresi
        recipient_list: Alıcı listesi
        html_message: HTML mesaj (opsiyonel)
        fail_silently: Hata durumunda sessizce devam et
    """
    try:
        if html_message:
            email = EmailMultiAlternatives(
                subject=subject,
                body=message,
                from_email=from_email,
                to=recipient_list,
            )
            email.attach_alternative(html_message, "text/html")
        else:
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=from_email,
                to=recipient_list,
            )
        
        result = email.send(fail_silently=fail_silently)
        
        logger.info(f"Email sent successfully: {subject} to {recipient_list}")
        return {
            'status': 'sent',
            'subject': subject,
            'recipients': recipient_list,
            'sent_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Email sending failed: {subject} - {str(exc)}")
        
        # Retry mekanizması
        if not fail_silently and self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        
        return {
            'status': 'failed',
            'subject': subject,
            'recipients': recipient_list,
            'error': str(exc),
            'failed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_templated_email_task(self, subject, template_name, context, 
                               from_email, recipient_list, **kwargs):
    """
    Template ile asenkron email gönderme
    
    Args:
        subject: Email konusu
        template_name: Django template adı (örn: 'emails/welcome.html')
        context: Template context dict
        from_email: Gönderen email
        recipient_list: Alıcı listesi
    """
    try:
        # HTML ve text versiyonlarını render et
        html_message = render_to_string(template_name, context)
        
        # Text versiyonu için HTML tag'lerini temizle (basit)
        import re
        text_message = re.sub('<[^<]+?>', '', html_message)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=from_email,
            to=recipient_list,
        )
        email.attach_alternative(html_message, "text/html")
        
        result = email.send()
        
        logger.info(f"Templated email sent: {subject} to {recipient_list}")
        return {
            'status': 'sent',
            'template': template_name,
            'subject': subject,
            'recipients': recipient_list,
            'sent_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Templated email failed: {subject} - {str(exc)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        
        return {
            'status': 'failed',
            'template': template_name,
            'error': str(exc),
            'failed_at': timezone.now().isoformat()
        }


@shared_task
def send_bulk_emails_task(email_list):
    """
    Toplu email gönderme (her biri ayrı task olarak)
    
    Args:
        email_list: Email bilgilerini içeren dict listesi
            [{'subject': '...', 'message': '...', 'recipients': [...], ...}, ...]
    """
    results = []
    
    for email_data in email_list:
        task = send_email_task.delay(
            subject=email_data.get('subject'),
            message=email_data.get('message'),
            from_email=email_data.get('from_email'),
            recipient_list=email_data.get('recipient_list'),
            html_message=email_data.get('html_message'),
        )
        results.append({
            'task_id': task.id,
            'subject': email_data.get('subject'),
            'recipients': email_data.get('recipient_list'),
        })
    
    logger.info(f"Bulk email tasks created: {len(results)} emails")
    return results


@shared_task
def cleanup_old_email_logs():
    """
    Eski email loglarını temizle (30 günden eski)
    """
    try:
        from django_celery_results.models import TaskResult
        
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = TaskResult.objects.filter(
            date_done__lt=cutoff_date,
            task_name__icontains='email'
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old email logs")
        return {'deleted': deleted_count}
        
    except Exception as exc:
        logger.error(f"Cleanup failed: {str(exc)}")
        return {'error': str(exc)}


@shared_task
def retry_failed_emails():
    """
    Başarısız email'leri tekrar göndermeyi dene
    """
    try:
        from django_celery_results.models import TaskResult
        
        # Son 24 saatte başarısız olan email task'larını bul
        failed_tasks = TaskResult.objects.filter(
            status='FAILURE',
            task_name__icontains='send_email',
            date_done__gte=timezone.now() - timedelta(hours=24)
        )[:10]  # Maksimum 10 email
        
        retried = []
        for task in failed_tasks:
            # Task argümanlarını al ve tekrar dene
            if task.task_args:
                try:
                    args = eval(task.task_args)  # Dikkat: Production'da daha güvenli bir yöntem kullan
                    send_email_task.delay(*args)
                    retried.append(task.task_id)
                except:
                    pass
        
        logger.info(f"Retried {len(retried)} failed emails")
        return {'retried': len(retried), 'task_ids': retried}
        
    except Exception as exc:
        logger.error(f"Retry failed: {str(exc)}")
        return {'error': str(exc)}


# Utility fonksiyonlar (sync wrapper'lar)
def send_email_async(subject, message, from_email, recipient_list, 
                     html_message=None, fail_silently=False):
    """
    Kolay kullanım için wrapper fonksiyon
    
    Kullanım:
        from core.tasks import send_email_async
        send_email_async(
            subject="Test",
            message="Merhaba",
            from_email="no-reply@epica.com",
            recipient_list=["user@example.com"]
        )
    """
    return send_email_task.delay(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=recipient_list,
        html_message=html_message,
        fail_silently=fail_silently
    )


def send_templated_email_async(subject, template_name, context, 
                                from_email, recipient_list):
    """
    Template ile email için wrapper
    
    Kullanım:
        from core.tasks import send_templated_email_async
        send_templated_email_async(
            subject="Hoşgeldiniz",
            template_name="emails/welcome.html",
            context={'user': user, 'link': activation_link},
            from_email="no-reply@epica.com",
            recipient_list=[user.email]
        )
    """
    return send_templated_email_task.delay(
        subject=subject,
        template_name=template_name,
        context=context,
        from_email=from_email,
        recipient_list=recipient_list
    )
