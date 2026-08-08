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


class SyncQueuedSerializer(serializers.Serializer):
    status = serializers.CharField()


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
