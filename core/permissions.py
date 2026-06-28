from rest_framework import permissions
from core.middleware import get_current_tenant

class IsTenantMember(permissions.BasePermission):
    """
    Allows access only to users who belong to the active tenant.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        current_tenant = get_current_tenant()
        if not current_tenant:
            return False
            
        # Superusers bypass tenant checks
        if request.user.is_superuser:
            return True
            
        return request.user.tenant == current_tenant

class HasPlanFeature(permissions.BasePermission):
    """
    Checks if the active tenant has a specific feature allowed in their plan.
    Usually subclassed or configured via a factory.
    """
    required_feature = None

    def has_permission(self, request, view):
        current_tenant = get_current_tenant()
        if not current_tenant:
            return False
            
        if request.user and request.user.is_superuser:
            return True
            
        # Import dynamically to avoid circular import issues
        from tenants.models import TenantPlan
        
        # Get active tenant plan
        tenant_plan = TenantPlan.objects.filter(
            tenant=current_tenant,
            status='active'
        ).select_related('plan').first()
        
        if not tenant_plan:
            return False
            
        # Standardize features format (usually list of strings in JSONField)
        features = tenant_plan.plan.features or []
        
        # Resolve feature to check
        feature = self.required_feature or getattr(view, 'required_feature', None)
        if not feature:
            return True
            
        return feature in features

def has_feature(feature_name):
    """
    Factory function to easily use in view sets:
    permission_classes = [IsTenantMember, has_feature('analytics')]
    """
    class DynamicHasPlanFeature(HasPlanFeature):
        required_feature = feature_name
    return DynamicHasPlanFeature
