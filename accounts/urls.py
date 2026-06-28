from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import SignupView, CustomTokenObtainPairView, MeView, TenantUserViewSet

router = DefaultRouter()
router.register(r'users', TenantUserViewSet, basename='user')

urlpatterns = [
    path('auth/signup/', SignupView.as_view(), name='auth_signup'),
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='auth_login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', MeView.as_view(), name='auth_me'),
    path('', include(router.urls)),
]
