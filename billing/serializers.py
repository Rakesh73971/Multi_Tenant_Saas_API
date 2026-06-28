from rest_framework import serializers
from billing.models import Invoice, PaymentHistory

class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ['id', 'amount', 'status', 'billing_date', 'stripe_invoice_id']
        read_only_fields = ['id', 'billing_date', 'stripe_invoice_id']

class PaymentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentHistory
        fields = ['id', 'amount', 'status', 'payment_date', 'stripe_charge_id']
        read_only_fields = ['id', 'payment_date', 'stripe_charge_id']

class SubscribeSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField(required=True)
