from django.urls import path, include
from rest_framework.routers import DefaultRouter
from tenants.views import PlanViewSet, TenantViewSet

router = DefaultRouter()
router.register(r'plans', PlanViewSet, basename='plan')
router.register(r'info', TenantViewSet, basename='tenant')

urlpatterns = [
    path('', include(router.urls)),
]
