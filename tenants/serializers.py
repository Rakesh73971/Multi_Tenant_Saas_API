from rest_framework import serializers
from tenants.models import Tenant, Plan, TenantPlan

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'price', 'max_users', 'rate_limit_limit', 'rate_limit_period', 'features']

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'subdomain', 'created_at']

class TenantPlanSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    
    class Meta:
        model = TenantPlan
        fields = ['id', 'plan', 'stripe_subscription_id', 'status', 'expires_at', 'created_at']
