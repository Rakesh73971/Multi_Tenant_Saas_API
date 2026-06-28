from django.db import models
from core.models import TenantModel

class Project(TenantModel):
    """
    Tenant-scoped Project model used to verify data isolation
    and plan feature checks.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
