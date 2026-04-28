from django.conf import settings
from django.core.mail import send_mail

from .models import QuoteRequest


def send_quote_request_notifications(quote_request: QuoteRequest) -> None:
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com')
    notification_email = getattr(settings, 'QUOTE_NOTIFICATION_EMAIL', '')

    product_name = quote_request.product.name if quote_request.product else 'Sin producto asociado'
    subject_admin = f"Nueva cotización #{quote_request.pk}"
    admin_message = (
        f"Se recibió una nueva solicitud de cotización.\n\n"
        f"Cliente: {quote_request.customer_name}\n"
        f"Teléfono: {quote_request.customer_phone}\n"
        f"Email: {quote_request.customer_email or '-'}\n"
        f"Empresa: {quote_request.company_name or '-'}\n"
        f"Ciudad: {quote_request.city or '-'}\n"
        f"Método preferido: {quote_request.preferred_contact_method or '-'}\n"
        f"Producto: {product_name}\n"
        f"Mensaje: {quote_request.message}\n"
    )

    if notification_email:
        send_mail(subject_admin, admin_message, from_email, [notification_email], fail_silently=True)

    if quote_request.customer_email:
        customer_message = (
            'Hola, recibimos tu solicitud de cotización. '\
            'Nuestro equipo comercial te contactará pronto por el medio que indicaste.\n\n'
            f'Referencia: #{quote_request.pk}'
        )
        send_mail(
            'Recibimos tu solicitud de cotización',
            customer_message,
            from_email,
            [quote_request.customer_email],
            fail_silently=True,
        )
