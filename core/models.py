from django.db import models
from core.middleware import get_current_tenant

class TenantQuerySet(models.QuerySet):
    def for_current_tenant(self):
        tenant = get_current_tenant()
        if tenant:
            return self.filter(tenant=tenant)
        return self

class TenantManager(models.Manager):
    def get_queryset(self):
        # Filter querysets to the active tenant in context by default
        return TenantQuerySet(self.model, using=self._db).for_current_tenant()

class TenantModel(models.Model):
    """
    Abstract base model that enforces tenant isolation.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='%(class)ss'
    )

    objects = TenantManager()
    unfiltered_objects = models.Manager()  # Escape hatch to query across all tenants

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Auto-assign tenant if not set and a tenant context is active
        if not hasattr(self, 'tenant') or self.tenant_id is None:
            tenant = get_current_tenant()
            if tenant:
                self.tenant = tenant
        super().save(*args, **kwargs)
