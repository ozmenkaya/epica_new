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
    Uses organization's email settings if configured, otherwise uses default settings.
    
    Args:
        ticket: Ticket instance
        supplier_list: List of Supplier instances
    
    Returns:
        Number of successfully sent emails
    """
    if not supplier_list:
        return 0
    
    # Check if organization has custom email settings
    org = ticket.organization
    use_org_settings = (
        org.email_host and 
        org.email_port and 
        org.email_host_user and 
        org.email_host_password
    )
    
    # Configure email connection
    if use_org_settings:
        from django.core.mail import get_connection
        connection = get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=org.email_host,
            port=org.email_port,
            username=org.email_host_user,
            password=org.email_host_password,
            use_tls=org.email_use_tls,
            use_ssl=org.email_use_ssl,
            fail_silently=False,
        )
        from_email = org.email_from_address or org.email_host_user
    else:
        connection = None  # Use default connection
        from_email = settings.DEFAULT_FROM_EMAIL
    
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
        
        # Generate unique supplier link with email parameter for auto-fill
        supplier_link = f"{site_url}/tr/supplier-access/{ticket.supplier_token}/?email={supplier.email}"
        
        context = {
            'ticket': ticket,
            'supplier': supplier,
            'supplier_link': supplier_link,
            'organization': ticket.organization,
        }
        
        # Render email template
        html_content = render_to_string('core/email/ticket_notification.html', context)
        text_content = strip_tags(html_content)
        
        # Create email with organization's connection
        email = EmailMultiAlternatives(
            subject=f'Yeni Talep #{ticket.id} - {ticket.title}',
            body=text_content,
            from_email=from_email,
            to=[supplier.email],
            reply_to=[from_email],
            connection=connection,
        )
        email.attach_alternative(html_content, "text/html")
        
        # Attach PDF
        email.attach(f'Talep_{ticket.id}.pdf', pdf_data, 'application/pdf')
        
        try:
            email.send()
            sent_count += 1
        except Exception as e:
            print(f"Failed to send email to {supplier.email}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    return sent_count


def send_order_completed_survey_email(order):
    """
    Send customer feedback survey email when order is completed.
    Uses organization's email settings if configured, otherwise uses default settings.
    
    Args:
        order: Order instance (billing.Order)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    # Get customer email from ticket's created_by user
    ticket = order.ticket
    if not ticket or not ticket.customer.user:
        return False
    
    customer_email = ticket.customer.user.email
    if not customer_email:
        return False
    
    # Build survey URL using feedback token
    site_url = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'epica.com.tr'
    if not site_url.startswith('http'):
        site_url = f'https://{site_url}'
    survey_url = f"{site_url}/feedback/{order.feedback_token}/"
    
    # Check if organization has custom email settings
    org = order.organization
    use_org_settings = (
        org.email_host and 
        org.email_port and 
        org.email_host_user and 
        org.email_host_password
    )
    
    # Configure email connection
    if use_org_settings:
        from django.core.mail import get_connection
        connection = get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=org.email_host,
            port=org.email_port,
            username=org.email_host_user,
            password=org.email_host_password,
            use_tls=org.email_use_tls,
            use_ssl=org.email_use_ssl,
            fail_silently=False,
        )
        from_email = org.email_from_address or org.email_host_user
    else:
        connection = None  # Use default connection
        from_email = settings.DEFAULT_FROM_EMAIL
    
    # Prepare email context
    context = {
        'order_id': order.id,
        'customer_name': ticket.created_by.get_full_name() or ticket.created_by.username,
        'supplier_name': order.supplier.name if order.supplier else 'Tedarikçi',
        'delivery_date': order.actual_delivery_date or order.created_at.date(),
        'survey_url': survey_url,
        'organization_name': org.name,
    }
    
    # Render email template
    html_content = render_to_string('emails/order_completed_survey.html', context)
    text_content = f"""
Merhaba {context['customer_name']},

#{context['order_id']} numaralı siparişiniz başarıyla tamamlandı ve tedarikçimiz {context['supplier_name']} tarafından teslim edildi.

Lütfen 2 dakikanızı ayırarak siparişinizi değerlendirin:
{survey_url}

Geri bildirimleriniz hizmet kalitemizi artırmamıza yardımcı oluyor.

Teşekkürler,
{context['organization_name']} Ekibi
    """.strip()
    
    # Create email
    email = EmailMultiAlternatives(
        subject=f'Siparişiniz Tamamlandı - Değerlendirin #{order.id}',
        body=text_content,
        from_email=from_email,
        to=[customer_email],
        reply_to=[from_email],
        connection=connection,
    )
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Failed to send survey email to {customer_email}: {e}")
        import traceback
        traceback.print_exc()
        return False
