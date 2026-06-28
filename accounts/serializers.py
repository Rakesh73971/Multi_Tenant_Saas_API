from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import User
from tenants.models import Tenant, Plan, TenantPlan
from tenants.serializers import TenantSerializer

class UserSerializer(serializers.ModelSerializer):
    tenant = TenantSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'tenant', 'created_at']
        read_only_fields = ['id', 'role', 'tenant', 'created_at']

class SignupSerializer(serializers.Serializer):
    tenant_name = serializers.CharField(max_length=100)
    subdomain = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=50, required=False, default="")
    last_name = serializers.CharField(max_length=50, required=False, default="")
    plan_id = serializers.IntegerField(required=False, write_only=True)

    def validate_subdomain(self, value):
        # Subdomains must be alphanumeric and unique
        clean_val = value.strip().lower()
        if not clean_val.isalnum():
            raise serializers.ValidationError("Subdomain must contain only letters and numbers.")
        if Tenant.objects.filter(subdomain=clean_val).exists():
            raise serializers.ValidationError("This subdomain is already taken.")
        return clean_val

    def validate_email(self, value):
        clean_email = value.strip().lower()
        if User.objects.filter(email=clean_email).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return clean_email

    @transaction.atomic
    def create(self, validated_data):
        tenant_name = validated_data['tenant_name']
        subdomain = validated_data['subdomain']
        email = validated_data['email']
        password = validated_data['password']
        first_name = validated_data.get('first_name', '')
        last_name = validated_data.get('last_name', '')
        plan_id = validated_data.get('plan_id', None)

        # 1. Create Tenant
        tenant = Tenant.objects.create(name=tenant_name, subdomain=subdomain)

        # 2. Get Plan & Create TenantPlan
        plan = None
        if plan_id:
            plan = Plan.objects.filter(id=plan_id).first()
        
        # If no plan is specified or found, default to 'Free' plan
        if not plan:
            plan = Plan.objects.filter(name__iexact='Free').first()
            
        # If no 'Free' plan exists in the DB yet, create a default one
        if not plan:
            plan = Plan.objects.create(
                name='Free',
                price=0.00,
                max_users=5,
                rate_limit_limit=100,
                rate_limit_period='minute',
                features=['projects']
            )

        TenantPlan.objects.create(
            tenant=tenant,
            plan=plan,
            status='active'
        )

        # 3. Create Tenant Administrator User
        user = User.objects.create_user(
            email=email,
            password=password,
            tenant=tenant,
            role='admin',
            first_name=first_name,
            last_name=last_name
        )

        return user
