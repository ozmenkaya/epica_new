"""
Email utility functions for Epica
"""
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags


def send_template_email(subject, template_name, context, recipient_list, from_email=None):
    """
    Send an email using a Django template
    
    Args:
        subject: Email subject
        template_name: Path to HTML template (without .html)
        context: Context dict for template
        recipient_list: List of recipient email addresses
        from_email: From email (optional, uses DEFAULT_FROM_EMAIL)
    
    Returns:
        Number of successfully sent emails
    """
    if from_email is None:
        from_email = settings.DEFAULT_FROM_EMAIL
    
    # Render HTML content
    html_content = render_to_string(f'{template_name}.html', context)
    text_content = strip_tags(html_content)
    
    # Create email
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=recipient_list
    )
    email.attach_alternative(html_content, "text/html")
    
    return email.send()


def send_ticket_notification(ticket, recipient_email, notification_type='created'):
    """
    Send notification email about a ticket
    
    Args:
        ticket: Ticket instance
        recipient_email: Recipient email address
        notification_type: Type of notification (created, updated, quote_received)
    """
    subject_map = {
        'created': f'New Ticket #{ticket.id} - {ticket.title}',
        'updated': f'Ticket #{ticket.id} Updated - {ticket.title}',
        'quote_received': f'New Quote for Ticket #{ticket.id}',
    }
    
    context = {
        'ticket': ticket,
        'notification_type': notification_type,
        'site_url': settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'epica.com.tr'
    }
    
    return send_mail(
        subject=subject_map.get(notification_type, f'Ticket #{ticket.id} Notification'),
        message=f'Ticket #{ticket.id}: {ticket.title}\nStatus: {ticket.get_status_display()}\n\nPlease login to view details.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient_email],
        fail_silently=False,
    )


def send_quote_notification(quote, recipient_email):
    """
    Send notification when a new quote is received
    
    Args:
        quote: Quote instance
        recipient_email: Recipient email address
    """
    return send_mail(
        subject=f'New Quote for {quote.ticket.title}',
        message=f'''
A new quote has been received for your request:

Ticket: #{quote.ticket.id} - {quote.ticket.title}
Supplier: {quote.supplier.name}
Total: {quote.total_price} {quote.currency}

Please login to review and approve the quote.
        '''.strip(),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient_email],
        fail_silently=False,
    )


def send_order_confirmation(order, recipient_email):
    """
    Send order confirmation email
    
    Args:
        order: Order instance
        recipient_email: Recipient email address
    """
    return send_mail(
        subject=f'Order Confirmation - Order #{order.id}',
        message=f'''
Your order has been confirmed:

Order ID: #{order.id}
Organization: {order.organization.name}
Total: {order.total_price} {order.currency}
Status: {order.get_status_display()}

Thank you for your order!
        '''.strip(),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient_email],
        fail_silently=False,
    )
