import re

from rest_framework import serializers

from sources.models import Document, Source


class SourceSerializer(serializers.ModelSerializer):
    # Populated by SourceViewSet.get_queryset()'s annotations rather than
    # computed per instance — as SerializerMethodFields these would be two
    # extra COUNT queries per source on every list response.
    #
    # `status` alone is not enough to tell a client whether a source is
    # actually queryable: it flips to "ready" when the sync finishes, but
    # embedding runs afterwards in a separate task, so there's a real
    # window where a source reads "ready" while dense retrieval still
    # can't find anything in it. These two counts are what makes that
    # window visible.
    chunk_count = serializers.IntegerField(read_only=True)
    embedded_chunk_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Source
        fields = [
            "id",
            "workspace",
            "name",
            "type",
            "config",
            "status",
            "chunk_count",
            "embedded_chunk_count",
            "last_synced_at",
            "last_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "last_synced_at", "last_error"]

    def validate_workspace(self, workspace):
        request = self.context["request"]
        if not workspace.memberships.filter(user=request.user).exists():
            raise serializers.ValidationError("You are not a member of this workspace.")
        return workspace

    def validate_config(self, config):
        pattern = config.get("section_boundary_pattern") if isinstance(config, dict) else None
        if pattern:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise serializers.ValidationError(
                    {"section_boundary_pattern": f"Not a valid regular expression: {exc}"}
                ) from exc
        return config


class SyncQueuedSerializer(serializers.Serializer):
    status = serializers.CharField()


class DirectoryEntrySerializer(serializers.Serializer):
    name = serializers.CharField()
    path = serializers.CharField()
    absolute_path = serializers.CharField()


class DirectoryListingSerializer(serializers.Serializer):
    path = serializers.CharField()
    parent = serializers.CharField(allow_null=True)
    absolute_path = serializers.CharField()
    entries = DirectoryEntrySerializer(many=True)


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "source",
            "external_id",
            "path",
            "title",
            "version",
            "deleted",
            "metadata",
            "created_at",
            "updated_at",
        ]
