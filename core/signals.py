from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Ticket
from .email_utils import send_ticket_to_suppliers
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Ticket)
def ticket_created_notify_suppliers(sender, instance: Ticket, created: bool, **kwargs):
    """
    Send email notifications to assigned suppliers when a new ticket is created.
    Each supplier gets an individual email with PDF attachment and unique access link.
    """
    if not created:
        return
    
    if not instance.category_id:
        return
    
    # Get assigned suppliers via rules or fallback to category suppliers
    try:
        suppliers = list(instance.assigned_suppliers.all())
    except Exception:
        suppliers = list(instance.category.suppliers.all())
    
    if not suppliers:
        logger.warning(
            "No suppliers assigned to ticket #%s (org=%s, category=%s)",
            instance.id,
            instance.organization_id,
            instance.category_id,
        )
        return
    
    # Send emails to all suppliers
    try:
        sent_count = send_ticket_to_suppliers(instance, suppliers)
        logger.info(
            "Sent ticket #%s notification to %s/%s suppliers (org=%s)",
            instance.id,
            sent_count,
            len(suppliers),
            instance.organization_id,
        )
    except Exception as e:
        logger.error(
            "Failed to send emails for ticket #%s: %s",
            instance.id,
            str(e),
            exc_info=True,
        )
