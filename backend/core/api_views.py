from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serializers import SystemStatusSerializer
from core.status import get_system_status


class SystemStatusView(APIView):
    """Read-only. Kept in DRF (unlike the plain Django auth views next
    door in core/views.py) so it lands in the OpenAPI schema and the SPA
    gets a generated type for it like every other endpoint.
    """

    @extend_schema(responses=SystemStatusSerializer)
    def get(self, request: Request) -> Response:
        workspace_ids = list(request.user.memberships.values_list("workspace_id", flat=True))
        status = get_system_status(workspace_ids)
        return Response(SystemStatusSerializer(status).data)
