import time
from rest_framework.throttling import BaseThrottle
from django.core.cache import cache
from core.middleware import get_current_tenant

class TenantPlanRateThrottle(BaseThrottle):
    """
    Rate limiting throttle that dynamically fetches limits from the tenant's plan.
    Saves and reads throttling data from Django Cache (Redis).
    """
    def allow_request(self, request, view):
        # 1. Superusers have unlimited access
        if request.user and request.user.is_superuser:
            return True

        current_tenant = get_current_tenant()
        
        # 2. Resolve rate limits based on active plan
        if not current_tenant:
            # Fallback for tenant-less requests (e.g., login, signup)
            self.limit = 60  # 60 requests
            self.period = 60 # per minute
            self.key = f"throttle:public:{self.get_ident(request)}"
        else:
            from tenants.models import TenantPlan
            
            # Fetch tenant's active plan
            tenant_plan = TenantPlan.objects.filter(
                tenant=current_tenant,
                status='active'
            ).select_related('plan').first()
            
            if tenant_plan:
                plan = tenant_plan.plan
                self.limit = plan.rate_limit_limit
                period_name = plan.rate_limit_period
            else:
                # Default safe limit if no active plan is found
                self.limit = 100
                period_name = 'minute'
            
            # Map duration name to seconds
            duration_map = {
                'second': 1,
                'minute': 60,
                'hour': 3600,
                'day': 86400
            }
            self.period = duration_map.get(period_name.lower(), 60)
            
            # Throttling scope: tenant + user ID or IP
            user_ident = request.user.id if (request.user and request.user.is_authenticated) else self.get_ident(request)
            self.key = f"throttle:tenant:{current_tenant.id}:{user_ident}"

        # 3. Sliding window logic in cache
        self.now = time.time()
        try:
            self.history = cache.get(self.key, [])
            
            # Remove keys older than the current window
            while self.history and self.history[-1] <= self.now - self.period:
                self.history.pop()

            # Reject if request limit is exceeded
            if len(self.history) >= self.limit:
                return False

            # Add current request and update cache
            self.history.insert(0, self.now)
            cache.set(self.key, self.history, self.period)
        except Exception as e:
            # Fallback when Redis cache is offline/unavailable (fail open to prevent 500 crashes)
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Throttling cache connection failed: {e}. Allowing request as fallback.")
            self.history = []
        return True


    def wait(self):
        """
        Estimate duration before next successful request is allowed.
        """
        if self.history:
            return self.period - (self.now - self.history[-1])
        return self.period
