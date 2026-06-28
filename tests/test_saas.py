from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.cache import cache

from tenants.models import Tenant, Plan, TenantPlan
from accounts.models import User
from api.models import Project

class MultiTenantSaaSTests(APITestCase):
    def setUp(self):
        # Purge Redis throttle cache before each test run
        cache.clear()
        
        # Seed test plans
        self.free_plan = Plan.objects.create(
            name='Free',
            price=0.00,
            max_users=5,
            rate_limit_limit=3,
            rate_limit_period='minute',
            features=['projects']
        )
        self.pro_plan = Plan.objects.create(
            name='Pro',
            price=49.00,
            max_users=20,
            rate_limit_limit=10,
            rate_limit_period='minute',
            features=['projects', 'analytics']
        )

    def test_signup_creates_tenant_and_admin(self):
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
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('tokens', response.data)
        self.assertIn('user', response.data)
        
        # Check Tenant creation
        tenant = Tenant.objects.filter(subdomain='acme').first()
        self.assertIsNotNone(tenant)
        self.assertEqual(tenant.name, 'Acme Corporation')
        
        # Check User creation and role
        user = User.objects.filter(email='admin@acme.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.tenant, tenant)
        self.assertEqual(user.role, 'admin')
        
        # Check Default active subscription plan
        tenant_plan = TenantPlan.objects.filter(tenant=tenant, status='active').first()
        self.assertIsNotNone(tenant_plan)
        self.assertEqual(tenant_plan.plan, self.free_plan)

    def test_tenant_isolation(self):
        """
        Verify that database queries are isolated. Tenant B must not see or modify Tenant A's objects.
        """
        # Create Tenant A
        tenant_a = Tenant.objects.create(name='Tenant A', subdomain='tenanta')
        user_a = User.objects.create_user(email='user@tenanta.com', password='password123', tenant=tenant_a)
        TenantPlan.objects.create(tenant=tenant_a, plan=self.free_plan, status='active')

        # Create Tenant B
        tenant_b = Tenant.objects.create(name='Tenant B', subdomain='tenantb')
        user_b = User.objects.create_user(email='user@tenantb.com', password='password123', tenant=tenant_b)
        TenantPlan.objects.create(tenant=tenant_b, plan=self.free_plan, status='active')

        # Authenticate User A and create a project in Tenant A context
        self.client.force_authenticate(user=user_a)
        headers_a = {'HTTP_X_TENANT': 'tenanta'}
        
        response = self.client.post(
            reverse('project-list'), 
            {'name': 'Secret Project A', 'description': 'Only for Tenant A'}, 
            **headers_a
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Confirm creation in DB
        proj_a = Project.unfiltered_objects.filter(name='Secret Project A').first()
        self.assertIsNotNone(proj_a)
        self.assertEqual(proj_a.tenant, tenant_a)

        # Authenticate User B and request projects list
        self.client.force_authenticate(user=user_b)
        headers_b = {'HTTP_X_TENANT': 'tenantb'}
        
        # User B should list 0 projects
        response = self.client.get(reverse('project-list'), **headers_b)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

        # User B tries to view Project A directly by ID: should return 404 Not Found due to queryset isolation
        response = self.client.get(reverse('project-detail', args=[proj_a.id]), **headers_b)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_rate_limiting_by_plan(self):
        """
        Verify that rate limits are enforced dynamically based on the plan.
        Free plan limit is 3 requests per minute.
        """
        tenant = Tenant.objects.create(name='Acme', subdomain='acme')
        user = User.objects.create_user(email='user@acme.com', password='password123', tenant=tenant)
        TenantPlan.objects.create(tenant=tenant, plan=self.free_plan, status='active')
        
        self.client.force_authenticate(user=user)
        headers = {'HTTP_X_TENANT': 'acme'}

        # Execute 3 successful API requests
        for _ in range(3):
            response = self.client.get(reverse('project-list'), **headers)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
        # The 4th request must return 429 Too Many Requests
        response = self.client.get(reverse('project-list'), **headers)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_plan_feature_access(self):
        """
        Verify plan feature checks. Free plan cannot view analytics; upgraded Pro plan can.
        """
        tenant = Tenant.objects.create(name='Acme', subdomain='acme')
        user = User.objects.create_user(email='user@acme.com', password='password123', tenant=tenant)
        TenantPlan.objects.create(tenant=tenant, plan=self.free_plan, status='active')
        
        self.client.force_authenticate(user=user)
        headers = {'HTTP_X_TENANT': 'acme'}

        # Attempting premium action under Free subscription returns 403 Forbidden
        response = self.client.get(reverse('project-analytics'), **headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Grant Admin privilege to update subscriptions
        user.role = 'admin'
        user.save()

        # Upgrade plan to 'Pro' via billing endpoint
        upgrade_response = self.client.post(
            reverse('billing_subscribe'), 
            {'plan_id': self.pro_plan.id}, 
            **headers
        )
        self.assertEqual(upgrade_response.status_code, status.HTTP_200_OK)

        # Accessing premium analytics dashboard now succeeds (200 OK)
        response = self.client.get(reverse('project-analytics'), **headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('performance_score', response.data['data'])
