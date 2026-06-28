from django.db import models
from core.models import TenantModel

class Invoice(TenantModel):
    """
    Tenant-scoped invoice records. Inherits from TenantModel to partition data.
    """
    STATUS_CHOICES = (
        ('paid', 'Paid'),
        ('unpaid', 'Unpaid'),
        ('void', 'Void'),
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    billing_date = models.DateTimeField(auto_now_add=True)
    stripe_invoice_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Invoice #{self.id} - {self.tenant.name} (${self.amount})"

class PaymentHistory(TenantModel):
    """
    Tenant-scoped payment transaction records.
    """
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('failed', 'Failed'),
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')
    payment_date = models.DateTimeField(auto_now_add=True)
    stripe_charge_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Payment #{self.id} - {self.tenant.name} (${self.amount})"
