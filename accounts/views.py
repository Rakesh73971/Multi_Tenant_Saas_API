from rest_framework import status, views, permissions, viewsets, generics
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from accounts.serializers import SignupSerializer, UserSerializer
from core.permissions import IsTenantMember

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer that embeds tenant context directly into the JWT claims
    and returns user details in the login response payload.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Inject custom claims
        token['tenant_id'] = user.tenant_id if user.tenant else None
        token['tenant_subdomain'] = user.tenant.subdomain if user.tenant else None
        token['role'] = user.role
        token['email'] = user.email

        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        
        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'role': self.user.role,
            'tenant_id': self.user.tenant_id if self.user.tenant else None,
            'tenant_subdomain': self.user.tenant.subdomain if self.user.tenant else None,
        }
        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class SignupView(generics.GenericAPIView):
    """
    Public registration endpoint. Creates the Tenant and sets up the Admin User.
    """
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]


    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            refresh['tenant_id'] = user.tenant_id
            refresh['tenant_subdomain'] = user.tenant.subdomain if user.tenant else None
            refresh['role'] = user.role
            
            return Response({
                "user": UserSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token)
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MeView(views.APIView):
    """
    Retrieve authenticated user profile.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

class TenantUserViewSet(viewsets.ModelViewSet):
    """
    Manage users belonging to the current tenant.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        if not self.request.tenant:
            return User.objects.none()
        # Return only users within the current tenant scope
        return User.objects.filter(tenant=self.request.tenant).order_by('id')

    def perform_create(self, serializer):
        # Auto-associate the new user with the active tenant
        serializer.save(tenant=self.request.tenant)
