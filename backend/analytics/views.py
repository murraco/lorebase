from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.metrics import get_dashboard_metrics
from analytics.models import Feedback
from analytics.serializers import DashboardMetricsSerializer, FeedbackSerializer
from rag.models import Message


class DashboardView(APIView):
    """Read-only, same shape as core.api_views.SystemStatusView: a pure
    function computes the data, this just scopes it to the caller's
    workspaces and serializes it.
    """

    @extend_schema(responses=DashboardMetricsSerializer)
    def get(self, request: Request) -> Response:
        workspace_ids = list(request.user.memberships.values_list("workspace_id", flat=True))
        metrics = get_dashboard_metrics(workspace_ids)
        return Response(DashboardMetricsSerializer(metrics).data)


class MessageFeedbackView(APIView):
    """POST is idempotent here by construction, not just by convention:
    the same rating sent twice, or a changed one, always ends with exactly
    one Feedback row for this message — see Feedback.message being a
    OneToOneField, not a ForeignKey.
    """

    @extend_schema(request=FeedbackSerializer, responses=FeedbackSerializer)
    def post(self, request: Request, message_id: str) -> Response:
        message = get_object_or_404(
            Message,
            pk=message_id,
            conversation__workspace__memberships__user=request.user,
            role=Message.Role.ASSISTANT,
        )
        serializer = FeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feedback, _ = Feedback.objects.update_or_create(
            message=message, defaults=serializer.validated_data
        )
        return Response(FeedbackSerializer(feedback).data)
