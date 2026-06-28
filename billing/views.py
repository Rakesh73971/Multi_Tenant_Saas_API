import stripe
from django.conf import settings
from rest_framework import views, permissions, status, viewsets, generics
from rest_framework.response import Response

from tenants.models import Plan, TenantPlan
from billing.models import Invoice, PaymentHistory
from billing.serializers import InvoiceSerializer, PaymentHistorySerializer, SubscribeSerializer
from core.permissions import IsTenantMember

class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Retrieve past invoices for the active tenant.
    """
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        # TenantModel handles filtration transparently
        return Invoice.objects.all().order_by('-billing_date')

class PaymentHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Retrieve payment transactions for the active tenant.
    """
    serializer_class = PaymentHistorySerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        # TenantModel handles filtration transparently
        return PaymentHistory.objects.all().order_by('-payment_date')

class SubscribeView(generics.GenericAPIView):
    """
    Subscribe or upgrade to a new subscription plan.
    """
    serializer_class = SubscribeSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]


    def post(self, request):
        # Enforce that only tenant administrators can manage plans
        if request.user.role != 'admin':
            return Response(
                {"detail": "Only tenant administrators can modify subscription plans."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = SubscribeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        plan_id = serializer.validated_data['plan_id']
        plan = Plan.objects.filter(id=plan_id).first()
        if not plan:
            return Response({"detail": "Selected plan does not exist."}, status=status.HTTP_404_NOT_FOUND)

        tenant = request.tenant

        if settings.MOCK_STRIPE:
            # Mock stripe purchase: instantly activate new subscription and create bills
            TenantPlan.objects.filter(tenant=tenant, status='active').update(status='canceled')
            
            tenant_plan = TenantPlan.objects.create(
                tenant=tenant,
                plan=plan,
                status='active',
                stripe_subscription_id='sub_mock_' + str(tenant.id) + '_' + str(plan.id)
            )

            # Record Invoice & Payment success
            Invoice.objects.create(
                tenant=tenant,
                amount=plan.price,
                status='paid',
                stripe_invoice_id='in_mock_' + str(tenant.id)
            )

            PaymentHistory.objects.create(
                tenant=tenant,
                amount=plan.price,
                status='success',
                stripe_charge_id='ch_mock_' + str(tenant.id)
            )

            return Response({
                "detail": "Subscription updated successfully (Mock Mode).",
                "subscription": {
                    "plan": plan.name,
                    "price": float(plan.price),
                    "status": tenant_plan.status
                }
            }, status=status.HTTP_200_OK)

        else:
            # Real Stripe Checkout Session creation
            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': f"SaaS Subscription: {plan.name}",
                            },
                            'unit_amount': int(plan.price * 100),  # In cents
                            'recurring': {'interval': 'month'},
                        },
                        'quantity': 1,
                    }],
                    mode='subscription',
                    success_url=f"http://localhost:8000/api/v1/billing/success/?session_id={{CHECKOUT_SESSION_ID}}",
                    cancel_url="http://localhost:8000/api/v1/billing/cancel/",
                    metadata={
                        'tenant_id': str(tenant.id),
                        'plan_id': str(plan.id),
                    }
                )
                return Response({"checkout_url": session.url}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response(
                    {"detail": f"Stripe integration failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

class StripeWebhookView(views.APIView):
    """
    Endpoint for Stripe events. Supports both mock JSON payloads and verified Stripe signatures.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        payload = request.body
        sig_header = request.headers.get('STRIPE_SIGNATURE')
        event_type = None
        object_data = {}

        if settings.MOCK_STRIPE:
            import json
            try:
                event_data = json.loads(payload)
                event_type = event_data.get('type')
                object_data = event_data.get('data', {}).get('object', {})
            except Exception:
                return Response({"detail": "Invalid JSON mock payload"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
                )
                event_type = event.type
                object_data = event.data.object
            except ValueError:
                return Response({"detail": "Invalid payload format"}, status=status.HTTP_400_BAD_REQUEST)
            except stripe.error.SignatureVerificationError:
                return Response({"detail": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        # Process the billing events
        if event_type == 'checkout.session.completed':
            metadata = object_data.get('metadata', {})
            tenant_id = metadata.get('tenant_id')
            plan_id = metadata.get('plan_id')
            subscription_id = object_data.get('subscription')
            
            if tenant_id and plan_id:
                from tenants.models import Tenant
                tenant = Tenant.objects.filter(id=int(tenant_id)).first()
                plan = Plan.objects.filter(id=int(plan_id)).first()
                
                if tenant and plan:
                    # Deactivate old subscription
                    TenantPlan.objects.filter(tenant=tenant, status='active').update(status='canceled')
                    
                    # Create new subscription
                    TenantPlan.objects.create(
                        tenant=tenant,
                        plan=plan,
                        status='active',
                        stripe_subscription_id=subscription_id
                    )

                    # Store records
                    Invoice.objects.create(
                        tenant=tenant,
                        amount=plan.price,
                        status='paid',
                        stripe_invoice_id=object_data.get('invoice', 'in_stripe_webhook')
                    )

                    PaymentHistory.objects.create(
                        tenant=tenant,
                        amount=plan.price,
                        status='success',
                        stripe_charge_id=object_data.get('payment_intent', 'ch_stripe_webhook')
                    )

        elif event_type == 'customer.subscription.deleted':
            subscription_id = object_data.get('id')
            TenantPlan.objects.filter(stripe_subscription_id=subscription_id).update(status='canceled')

        return Response({"status": "processed"}, status=status.HTTP_200_OK)
