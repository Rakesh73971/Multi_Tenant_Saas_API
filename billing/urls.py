from django.urls import path, include
from rest_framework.routers import DefaultRouter
from billing.views import InvoiceViewSet, PaymentHistoryViewSet, SubscribeView, StripeWebhookView

router = DefaultRouter()
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'payments', PaymentHistoryViewSet, basename='payment')

urlpatterns = [
    path('subscribe/', SubscribeView.as_view(), name='billing_subscribe'),
    path('webhook/', StripeWebhookView.as_view(), name='billing_webhook'),
    path('', include(router.urls)),
]
