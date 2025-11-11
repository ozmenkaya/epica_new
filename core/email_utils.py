"""
Email utility functions for Epica
"""
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from io import BytesIO
import tempfile
import os

# Import WeasyPrint only when needed (requires system dependencies)
try:
	from weasyprint import HTML
	WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
	WEASYPRINT_AVAILABLE = False


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


def generate_ticket_pdf(ticket):
    """
    Generate PDF for ticket details
    
    Args:
        ticket: Ticket instance
    
    Returns:
        BytesIO object containing PDF data
    """
    if not WEASYPRINT_AVAILABLE:
        raise RuntimeError("WeasyPrint is not available. Please install system dependencies.")
    
    from .models import CategoryFormField
    
    # Prepare extra fields with labels
    extra_fields = []
    if ticket.extra_data:
        try:
            specs = (
                CategoryFormField.objects
                .filter(organization=ticket.organization, category=ticket.category)
                .order_by("order", "id")
            )
            for f in specs:
                if f.name in ticket.extra_data:
                    val = ticket.extra_data.get(f.name)
                    if isinstance(val, list):
                        val = ", ".join([str(v) for v in val])
                    extra_fields.append({"label": f.label, "value": val})
        except Exception:
            for k, v in (ticket.extra_data or {}).items():
                extra_fields.append({"label": k, "value": v})
    
    context = {
        'ticket': ticket,
        'extra_fields': extra_fields,
        'organization': ticket.organization,
    }
    
    # Render HTML template
    html_content = render_to_string('core/ticket_pdf.html', context)
    
    # Generate PDF
    pdf_file = BytesIO()
    HTML(string=html_content, base_url=settings.BASE_DIR).write_pdf(pdf_file)
    pdf_file.seek(0)
    
    return pdf_file


def send_ticket_to_suppliers(ticket, supplier_list):
    """
    Send ticket notification email to suppliers with PDF attachment and unique access link.
    Each supplier gets a separate email (BCC not used, each email is individual).
    
    Args:
        ticket: Ticket instance
        supplier_list: List of Supplier instances
    
    Returns:
        Number of successfully sent emails
    """
    if not supplier_list:
        return 0
    
    # Generate PDF once
    pdf_file = generate_ticket_pdf(ticket)
    pdf_data = pdf_file.read()
    
    site_url = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'epica.com.tr'
    if not site_url.startswith('http'):
        site_url = f'https://{site_url}'
    
    sent_count = 0
    for supplier in supplier_list:
        if not supplier.email:
            continue
        
        # Generate unique supplier link
        supplier_link = f"{site_url}/tr/supplier-access/{ticket.supplier_token}/"
        
        context = {
            'ticket': ticket,
            'supplier': supplier,
            'supplier_link': supplier_link,
            'organization': ticket.organization,
        }
        
        # Render email template
        html_content = render_to_string('core/email/ticket_notification.html', context)
        text_content = strip_tags(html_content)
        
        # Create email
        email = EmailMultiAlternatives(
            subject=f'Yeni Talep #{ticket.id} - {ticket.title}',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[supplier.email],
            reply_to=[settings.DEFAULT_FROM_EMAIL],  # Suppliers can reply to this
        )
        email.attach_alternative(html_content, "text/html")
        
        # Attach PDF
        email.attach(f'Talep_{ticket.id}.pdf', pdf_data, 'application/pdf')
        
        try:
            email.send()
            sent_count += 1
        except Exception as e:
            print(f"Failed to send email to {supplier.email}: {e}")
            continue
    
    return sent_count
