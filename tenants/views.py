from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from tenants.models import Tenant, Plan, TenantPlan
from tenants.serializers import TenantSerializer, PlanSerializer, TenantPlanSerializer
from core.permissions import IsTenantMember

class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public endpoint to view available subscription plans.
    """
    queryset = Plan.objects.all().order_by('price')
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]

class TenantViewSet(viewsets.ViewSet):
    """
    Endpoint to view the current tenant details and active subscription.
    """
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    
    @action(detail=False, methods=['get'], url_path='my-tenant')
    def my_tenant(self, request):
        tenant = request.tenant
        if not tenant:
            return Response(
                {"detail": "No active tenant context found. Please supply a valid X-Tenant header or subdomain."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        tenant_serializer = TenantSerializer(tenant)
        
        # Fetch current active subscription plan
        active_plan = TenantPlan.objects.filter(
            tenant=tenant, 
            status='active'
        ).select_related('plan').first()
        
        plan_serializer = TenantPlanSerializer(active_plan) if active_plan else None
        
        return Response({
            "tenant": tenant_serializer.data,
            "subscription": plan_serializer.data if plan_serializer else None
        })
