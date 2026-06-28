import logging
from celery import shared_task
from django.utils import timezone
from tenants.models import TenantPlan

logger = logging.getLogger(__name__)

@shared_task
def check_subscription_expirations():
    """
    Periodic task that checks for active/trialing subscriptions that have passed
    their expiry date and transitions them to 'canceled'.
    """
    now = timezone.now()
    
    # We query using Django standard models or managers. 
    # Because Celery tasks run globally (without TenantMiddleware context),
    # accessing objects of standard models that don't inherit from TenantModel
    # is standard. TenantPlan doesn't inherit from TenantModel (as it's a global tenant link).
    expired_plans = TenantPlan.objects.filter(
        status__in=['active', 'trialing'],
        expires_at__lt=now
    )
    
    count = expired_plans.count()
    for tenant_plan in expired_plans:
        tenant_plan.status = 'canceled'
        tenant_plan.save()
        logger.info(f"Subscription expired: Tenant {tenant_plan.tenant.name} plan {tenant_plan.plan.name} has been set to canceled.")
    
    return f"Checked expirations. Deactivated {count} plans."

@shared_task
def send_invoice_email_task(invoice_id):
    """
    Async task to mock sending an invoice payment confirmation email to the tenant.
    Uses 'unfiltered_objects' to bypass the active-tenant ContextVar check since Celery runs out-of-context.
    """
    from billing.models import Invoice
    
    # Bypass tenant middleware filters
    invoice = Invoice.unfiltered_objects.filter(id=invoice_id).select_related('tenant').first()
    if not invoice:
        logger.warning(f"Could not dispatch email: Invoice #{invoice_id} not found.")
        return f"Invoice {invoice_id} not found."

    tenant_name = invoice.tenant.name
    logger.info(f"Email Dispatch: Sending invoice PDF receipt to billing contact of '{tenant_name}' for Invoice #{invoice.id} (${invoice.amount})")
    
    return f"Dispatched invoice email receipt for invoice #{invoice_id}"
