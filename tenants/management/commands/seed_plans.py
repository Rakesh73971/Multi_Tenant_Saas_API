from django.core.management.base import BaseCommand
from tenants.models import Plan

class Command(BaseCommand):
    help = 'Seeds initial subscription plans: Free, Pro, Enterprise'

    def handle(self, *args, **options):
        plans_data = [
            {
                'name': 'Free',
                'price': 0.00,
                'max_users': 5,
                'rate_limit_limit': 100,
                'rate_limit_period': 'minute',
                'features': ['projects']
            },
            {
                'name': 'Pro',
                'price': 49.00,
                'max_users': 20,
                'rate_limit_limit': 1000,
                'rate_limit_period': 'minute',
                'features': ['projects', 'analytics']
            },
            {
                'name': 'Enterprise',
                'price': 199.00,
                'max_users': 9999,
                'rate_limit_limit': 10000,
                'rate_limit_period': 'minute',
                'features': ['projects', 'analytics', 'custom_branding']
            }
        ]

        for p_data in plans_data:
            plan, created = Plan.objects.update_or_create(
                name=p_data['name'],
                defaults=p_data
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(f"{action} plan: {plan.name}"))
