from django.db import models

class Tenant(models.Model):
    """
    Represents an organization / tenant workspace.
    """
    name = models.CharField(max_length=100)
    subdomain = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Plan(models.Model):
    """
    Subscription tiers that dictate features, users, and rate limits.
    """
    name = models.CharField(max_length=50, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    max_users = models.IntegerField(default=5)
    rate_limit_limit = models.IntegerField(default=60)
    rate_limit_period = models.CharField(max_length=20, default='minute')  # second, minute, hour, day
    features = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.name

class TenantPlan(models.Model):
    """
    Subscription state linking a Tenant to a specific Plan.
    """
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('trialing', 'Trialing'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
    )

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='tenant_subscriptions')
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Enforce that each tenant can only have one active subscription at a time
            models.UniqueConstraint(
                fields=['tenant'],
                condition=models.Q(status='active'),
                name='unique_active_tenant_plan'
            )
        ]

    def __str__(self):
        return f"{self.tenant.name} - {self.plan.name} ({self.status})"
