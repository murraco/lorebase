from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from sources.models import Document, Source
from sources.serializers import DocumentSerializer, SourceSerializer
from sources.tasks import sync_source_task


class SourceViewSet(viewsets.ModelViewSet):
    serializer_class = SourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Source.objects.none()
        return Source.objects.filter(workspace__memberships__user=self.request.user).order_by(
            "name"
        )

    @action(detail=True, methods=["post"])
    def sync(self, request: Request, pk: str | None = None) -> Response:
        source = self.get_object()
        sync_source_task.delay(str(source.id))
        return Response({"status": "queued"}, status=202)


class DocumentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DocumentSerializer

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
