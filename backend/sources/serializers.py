import re

from rest_framework import serializers

from sources.models import Document, Source


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = [
            "id",
            "workspace",
            "name",
            "type",
            "config",
            "status",
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
