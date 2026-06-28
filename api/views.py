from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from api.models import Project
from api.serializers import ProjectSerializer
from core.permissions import IsTenantMember, has_feature

class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant-scoped Projects.
    Requires:
    - User Authentication
    - Tenant Membership
    - The 'projects' plan feature (all standard plans).
    """
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantMember, has_feature('projects')]

    def get_queryset(self):
        # TenantModel automatically filters to the current tenant context
        return Project.objects.all().order_by('-created_at')

    @action(
        detail=False, 
        methods=['get'], 
        url_path='analytics', 
        url_name='analytics',
        permission_classes=[permissions.IsAuthenticated, IsTenantMember, has_feature('analytics')]
    )

    def analytics_dashboard(self, request):
        """
        Premium analytics dashboard action. Requires the premium 'analytics' plan feature.
        """
        return Response({
            "status": "success",
            "message": "Welcome to the premium Analytics Dashboard! Access granted because your subscription supports analytics.",
            "data": {
                "active_projects": self.get_queryset().count(),
                "performance_score": 98.4
            }
        })
