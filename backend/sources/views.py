from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from sources.models import Document, Source
from sources.serializers import DocumentSerializer, SourceSerializer, SyncQueuedSerializer
from sources.tasks import sync_source_task


class SourceViewSet(viewsets.ModelViewSet):
    serializer_class = SourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Source.objects.none()
        return Source.objects.filter(workspace__memberships__user=self.request.user).order_by(
            "name"
        )

    # Without this, drf-spectacular falls back to inferring the request
    # body from the viewset's serializer_class (Source) — wrong, since
    # this action takes no body at all.
    @extend_schema(request=None, responses={202: SyncQueuedSerializer})
    @action(detail=True, methods=["post"])
    def sync(self, request: Request, pk: str | None = None) -> Response:
        source = self.get_object()
        sync_source_task.delay(str(source.id))
        return Response({"status": "queued"}, status=202)


class DocumentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DocumentSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "source", OpenApiTypes.UUID, description="Filter documents down to a single source."
            )
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Document.objects.none()
        queryset = Document.objects.filter(
            source__workspace__memberships__user=self.request.user
        ).order_by("-updated_at")
        source_id = self.request.query_params.get("source")
        if source_id:
            queryset = queryset.filter(source_id=source_id)
        return queryset
