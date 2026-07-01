import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.core.cache import cache

from tenants.models import Tenant, Plan, TenantPlan
from accounts.models import User
from api.models import Project

@pytest.fixture(autouse=True)
def clear_cache():
    """
    Purge Redis throttle cache before and after each test run.
    """
    cache.clear()
    yield
    cache.clear()

@pytest.fixture
def api_client():
    """
    Fixture providing an authenticated/unauthenticated APIClient.
    """
    return APIClient()

@pytest.fixture
def free_plan(db):
    """
    Fixture for standard Free tier plan.
    """
    return Plan.objects.create(
        name='Free',
        price=0.00,
        max_users=5,
        rate_limit_limit=3,
        rate_limit_period='minute',
        features=['projects']
    )

@pytest.fixture
def pro_plan(db):
    """
    Fixture for standard Pro tier plan.
    """
    return Plan.objects.create(
        name='Pro',
        price=49.00,
        max_users=20,
        rate_limit_limit=10,
        rate_limit_period='minute',
        features=['projects', 'analytics']
    )

@pytest.mark.django_db
def test_signup_creates_tenant_and_admin(api_client, free_plan):
    """
    Verify that registering a new tenant dynamically creates the organization,
    assigns the default Free plan subscription, and creates the admin user.
    """
    url = reverse('auth_signup')
    data = {
        'tenant_name': 'Acme Corporation',
        'subdomain': 'acme',
        'email': 'admin@acme.com',
        'password': 'securepassword123',
        'first_name': 'Acme',
        'last_name': 'Admin'
    }
    response = api_client.post(url, data)
    assert response.status_code == status.HTTP_201_CREATED
    assert 'tokens' in response.data
    assert 'user' in response.data
    
    # Check Tenant creation
    tenant = Tenant.objects.filter(subdomain='acme').first()
    assert tenant is not None
    assert tenant.name == 'Acme Corporation'
    
    # Check User creation and role
    user = User.objects.filter(email='admin@acme.com').first()
    assert user is not None
    assert user.tenant == tenant
    assert user.role == 'admin'
    
    # Check Default active subscription plan
    tenant_plan = TenantPlan.objects.filter(tenant=tenant, status='active').first()
    assert tenant_plan is not None
    assert tenant_plan.plan == free_plan

@pytest.mark.django_db
def test_tenant_isolation(api_client, free_plan):
    """
    Verify that database queries are isolated. Tenant B must not see or modify Tenant A's objects.
    """
    # Create Tenant A
    tenant_a = Tenant.objects.create(name='Tenant A', subdomain='tenanta')
    user_a = User.objects.create_user(email='user@tenanta.com', password='password123', tenant=tenant_a)
    TenantPlan.objects.create(tenant=tenant_a, plan=free_plan, status='active')

    # Create Tenant B
    tenant_b = Tenant.objects.create(name='Tenant B', subdomain='tenantb')
    user_b = User.objects.create_user(email='user@tenantb.com', password='password123', tenant=tenant_b)
    TenantPlan.objects.create(tenant=tenant_b, plan=free_plan, status='active')

    # Authenticate User A and create a project in Tenant A context
    api_client.force_authenticate(user=user_a)
    headers_a = {'HTTP_X_TENANT': 'tenanta'}
    
    response = api_client.post(
        reverse('project-list'), 
        {'name': 'Secret Project A', 'description': 'Only for Tenant A'}, 
        **headers_a
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # Confirm creation in DB
    proj_a = Project.unfiltered_objects.filter(name='Secret Project A').first()
    assert proj_a is not None
    assert proj_a.tenant == tenant_a

    # Authenticate User B and request projects list
    api_client.force_authenticate(user=user_b)
    headers_b = {'HTTP_X_TENANT': 'tenantb'}
    
    # User B should list 0 projects
    response = api_client.get(reverse('project-list'), **headers_b)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 0

    # User B tries to view Project A directly by ID: should return 404 Not Found
    response = api_client.get(reverse('project-detail', args=[proj_a.id]), **headers_b)
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_rate_limiting_by_plan(api_client, free_plan):
    """
    Verify that rate limits are enforced dynamically based on the plan.
    Free plan limit is 3 requests per minute.
    """
    tenant = Tenant.objects.create(name='Acme', subdomain='acme')
    user = User.objects.create_user(email='user@acme.com', password='password123', tenant=tenant)
    TenantPlan.objects.create(tenant=tenant, plan=free_plan, status='active')
    
    api_client.force_authenticate(user=user)
    headers = {'HTTP_X_TENANT': 'acme'}

    # Execute 3 successful API requests
    for _ in range(3):
        response = api_client.get(reverse('project-list'), **headers)
        assert response.status_code == status.HTTP_200_OK
        
    # The 4th request must return 429 Too Many Requests
    response = api_client.get(reverse('project-list'), **headers)
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

@pytest.mark.django_db
def test_plan_feature_access(api_client, free_plan, pro_plan):
    """
    Verify plan feature checks. Free plan cannot view analytics; upgraded Pro plan can.
    """
    tenant = Tenant.objects.create(name='Acme', subdomain='acme')
    user = User.objects.create_user(email='user@acme.com', password='password123', tenant=tenant)
    TenantPlan.objects.create(tenant=tenant, plan=free_plan, status='active')
    
    api_client.force_authenticate(user=user)
    headers = {'HTTP_X_TENANT': 'acme'}

    # Attempting premium action under Free subscription returns 403 Forbidden
    response = api_client.get(reverse('project-analytics'), **headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Grant Admin privilege to update subscriptions
    user.role = 'admin'
    user.save()

    # Upgrade plan to 'Pro' via billing endpoint
    upgrade_response = api_client.post(
        reverse('billing_subscribe'), 
        {'plan_id': pro_plan.id}, 
        **headers
    )
    assert upgrade_response.status_code == status.HTTP_200_OK

    # Accessing premium analytics dashboard now succeeds (200 OK)
    response = api_client.get(reverse('project-analytics'), **headers)
    assert response.status_code == status.HTTP_200_OK
    assert 'performance_score' in response.data['data']
