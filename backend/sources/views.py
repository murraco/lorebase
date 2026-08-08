from django.db.models import Count, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from sources.filesystem import BrowsePathError, list_directory
from sources.models import Document, Source
from sources.serializers import (
    DirectoryListingSerializer,
    DocumentSerializer,
    SourceSerializer,
    SyncQueuedSerializer,
)
from sources.tasks import sync_source_task


class SourceViewSet(viewsets.ModelViewSet):
    serializer_class = SourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Source.objects.none()
        return (
            Source.objects.filter(workspace__memberships__user=self.request.user)
            # distinct=True on both: documents__chunks fans out the row per
            # chunk, so without it the two counts multiply each other.
            .annotate(
                chunk_count=Count("documents__chunks", distinct=True),
                embedded_chunk_count=Count(
                    "documents__chunks",
                    filter=Q(documents__chunks__embedding__isnull=False),
                    distinct=True,
                ),
            )
            .order_by("name")
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

    # Powers the "add a local folder source" picker: lets the frontend
    # navigate the backend's own filesystem instead of asking the user to
    # type a container-internal path blind. Not workspace-scoped — this
    # is server filesystem structure under a fixed root, not tenant data
    # — but it does require authentication, same as every other endpoint.
    @extend_schema(
        parameters=[OpenApiParameter("path", OpenApiTypes.STR, required=False)],
        responses=DirectoryListingSerializer,
    )
    @action(detail=False, methods=["get"])
    def browse(self, request: Request) -> Response:
        try:
            listing = list_directory(request.query_params.get("path", ""))
        except BrowsePathError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(DirectoryListingSerializer(listing).data)


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
