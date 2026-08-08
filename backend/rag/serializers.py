from rest_framework import serializers

from rag.models import Citation, Conversation, Message


class CitationSerializer(serializers.ModelSerializer):
    path = serializers.CharField(source="chunk.document.path", read_only=True)
    start_line = serializers.IntegerField(source="chunk.start_line", read_only=True)
    end_line = serializers.IntegerField(source="chunk.end_line", read_only=True)
    # The cited passage itself — lets a citation chip show the fragment it
    # actually points to without a separate request or a dedicated Chunk
    # read endpoint that nothing else needs yet.
    content = serializers.CharField(source="chunk.content", read_only=True)

    class Meta:
        model = Citation
        fields = ["id", "chunk", "path", "start_line", "end_line", "content"]


class MessageSerializer(serializers.ModelSerializer):
    citations = CitationSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "role",
            "content",
            "latency_ms",
            "input_tokens",
            "output_tokens",
            "cost",
            "citations",
            "created_at",
        ]


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "workspace", "user", "title", "created_at"]
        read_only_fields = ["user"]

    def validate_workspace(self, workspace):
        request = self.context["request"]
        if not workspace.memberships.filter(user=request.user).exists():
            raise serializers.ValidationError("You are not a member of this workspace.")
        return workspace
