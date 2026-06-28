from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import ProjectViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')

urlpatterns = [
    # Sub-apps routers
    path('tenants/', include('tenants.urls')),
    path('', include('accounts.urls')),  # Injects /auth/ and /users/
    path('billing/', include('billing.urls')),
    
    # Projects router
    path('', include(router.urls)),
]
