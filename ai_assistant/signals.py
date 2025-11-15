"""
Signals for auto-learning: automatically embed new content
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from core.models import Ticket, Quote, Supplier
from ai_assistant.models import EmbeddedDocument
from ai_assistant.services.embedder import EmbeddingService

logger = logging.getLogger(__name__)


# Auto-embed on ticket create/update
@receiver(post_save, sender=Ticket)
def embed_ticket(sender, instance, created, **kwargs):
    """Automatically embed ticket when created or updated"""
    if not settings.OPENAI_API_KEY:
        return
    
    try:
        embedder = EmbeddingService()
        text = embedder.prepare_ticket_text(instance)
        embedding = embedder.embed_text(text)
        
        if embedding:
            EmbeddedDocument.objects.update_or_create(
                organization=instance.organization,
                content_type='ticket',
                object_id=instance.id,
                defaults={
                    'content': text,
                    'embedding': embedding,
                    'metadata': {
                        'title': instance.title,
                        'status': instance.status,
                        'category': instance.category.name,
                        'created_at': instance.created_at.isoformat()
                    }
                }
            )
            logger.info(f"Embedded ticket #{instance.id}")
    except Exception as e:
        logger.error(f"Error embedding ticket #{instance.id}: {e}")


# Auto-embed on quote create/update
@receiver(post_save, sender=Quote)
def embed_quote(sender, instance, created, **kwargs):
    """Automatically embed quote when created or updated"""
    if not settings.OPENAI_API_KEY:
        return
    
    try:
        embedder = EmbeddingService()
        text = embedder.prepare_quote_text(instance)
        embedding = embedder.embed_text(text)
        
        if embedding:
            EmbeddedDocument.objects.update_or_create(
                organization=instance.ticket.organization,
                content_type='quote',
                object_id=instance.id,
                defaults={
                    'content': text,
                    'embedding': embedding,
                    'metadata': {
                        'ticket_id': instance.ticket.id,
                        'supplier': instance.supplier.name,
                        'total': float(instance.total_price),
                        'currency': instance.currency,
                        'created_at': instance.created_at.isoformat()
                    }
                }
            )
            logger.info(f"Embedded quote #{instance.id}")
    except Exception as e:
        logger.error(f"Error embedding quote #{instance.id}: {e}")


# Auto-embed on supplier create/update
@receiver(post_save, sender=Supplier)
def embed_supplier(sender, instance, created, **kwargs):
    """Automatically embed supplier when created or updated"""
    if not settings.OPENAI_API_KEY:
        return
    
    try:
        embedder = EmbeddingService()
        text = embedder.prepare_supplier_text(instance)
        embedding = embedder.embed_text(text)
        
        if embedding:
            EmbeddedDocument.objects.update_or_create(
                organization=instance.organization,
                content_type='supplier',
                object_id=instance.id,
                defaults={
                    'content': text,
                    'embedding': embedding,
                    'metadata': {
                        'name': instance.name,
                        'email': instance.email,
                        'is_active': instance.is_active,
                        'created_at': instance.created_at.isoformat()
                    }
                }
            )
            logger.info(f"Embedded supplier #{instance.id}")
    except Exception as e:
        logger.error(f"Error embedding supplier #{instance.id}: {e}")


# Delete embeddings when objects are deleted
@receiver(post_delete, sender=Ticket)
def delete_ticket_embedding(sender, instance, **kwargs):
    """Delete embedding when ticket is deleted"""
    try:
        EmbeddedDocument.objects.filter(
            organization=instance.organization,
            content_type='ticket',
            object_id=instance.id
        ).delete()
        logger.info(f"Deleted embedding for ticket #{instance.id}")
    except Exception as e:
        logger.error(f"Error deleting ticket embedding: {e}")


@receiver(post_delete, sender=Quote)
def delete_quote_embedding(sender, instance, **kwargs):
    """Delete embedding when quote is deleted"""
    try:
        EmbeddedDocument.objects.filter(
            organization=instance.ticket.organization,
            content_type='quote',
            object_id=instance.id
        ).delete()
        logger.info(f"Deleted embedding for quote #{instance.id}")
    except Exception as e:
        logger.error(f"Error deleting quote embedding: {e}")


@receiver(post_delete, sender=Supplier)
def delete_supplier_embedding(sender, instance, **kwargs):
    """Delete embedding when supplier is deleted"""
    try:
        EmbeddedDocument.objects.filter(
            organization=instance.organization,
            content_type='supplier',
            object_id=instance.id
        ).delete()
        logger.info(f"Deleted embedding for supplier #{instance.id}")
    except Exception as e:
        logger.error(f"Error deleting supplier embedding: {e}")
