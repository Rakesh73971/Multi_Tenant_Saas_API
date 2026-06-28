import contextvars
from django.utils.deprecation import MiddlewareMixin

# Thread-safe context variable to store the current tenant
_current_tenant = contextvars.ContextVar('current_tenant', default=None)

def get_current_tenant():
    """
    Retrieve the current tenant from context.
    """
    return _current_tenant.get()

def set_current_tenant(tenant):
    """
    Set the current tenant in context.
    """
    _current_tenant.set(tenant)

class TenantMiddleware(MiddlewareMixin):
    """
    Middleware that identifies the tenant from either:
    1. The 'X-Tenant' HTTP header (ID or subdomain).
    2. The subdomain of the request host.
    """
    def process_request(self, request):
        from tenants.models import Tenant
        
        tenant = None
        
        # 1. Check for X-Tenant header
        tenant_header = request.headers.get('X-Tenant')
        if tenant_header:
            if tenant_header.isdigit():
                tenant = Tenant.objects.filter(id=int(tenant_header)).first()
            if not tenant:
                tenant = Tenant.objects.filter(subdomain=tenant_header).first()
                
        # 2. Check for subdomain (e.g. tenant-subdomain.example.com)
        if not tenant:
            host = request.get_host().split(':')[0]  # remove port if present
            host_parts = host.split('.')
            # Handle localhost testing (e.g., tenant1.localhost)
            if len(host_parts) >= 2:
                # If host matches subdomain.localhost or subdomain.domain.com
                subdomain = host_parts[0]
                if subdomain not in ('www', 'localhost', '127'):
                    tenant = Tenant.objects.filter(subdomain=subdomain).first()
        
        # Set on request object and context variable
        request.tenant = tenant
        set_current_tenant(tenant)

    def process_response(self, request, response):
        # Reset context variable to prevent cross-request leakage
        set_current_tenant(None)
        return response
