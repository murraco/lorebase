from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from rag.models import Citation, Conversation, Message


class MessageFeedbackSerializer(serializers.Serializer):
    """Describes the *shape* of MessageSerializer.feedback for the OpenAPI
    schema only — never instantiated to validate or save anything (that's
    analytics.serializers.FeedbackSerializer's job). Defined here, not
    imported from there, so the generated TS type is `{ rating; comment }
    | null` instead of a generic string-keyed object, without giving `rag`
    an import from `analytics`.
    """

    rating = serializers.ChoiceField(choices=["up", "down"])
    comment = serializers.CharField()


class CitationSerializer(serializers.ModelSerializer):
    path = serializers.CharField(source="chunk.document.path", read_only=True)
    # The chunk's heading breadcrumb ("2025-07-21 > Work") — far more
    # legible in a citation chip than "notes/journal.md:412-438" alone,
    # and already computed at ingestion time.
    heading_path = serializers.CharField(source="chunk.heading_path", read_only=True)
    # Retrieval provenance, so the evidence panel can show where a
    # chunk placed and what it scored rather than just naming it.
    source_name = serializers.CharField(source="chunk.document.source.name", read_only=True)
    start_line = serializers.IntegerField(source="chunk.start_line", read_only=True)
    end_line = serializers.IntegerField(source="chunk.end_line", read_only=True)
    # The cited passage itself — lets a citation chip show the fragment it
    # actually points to without a separate request or a dedicated Chunk
    # read endpoint that nothing else needs yet.
    content = serializers.CharField(source="chunk.content", read_only=True)

    class Meta:
        model = Citation
        fields = [
            "id",
            "chunk",
            "path",
            "heading_path",
            "source_name",
            "rank",
            "score",
            "start_line",
            "end_line",
            "content",
        ]


class MessageSerializer(serializers.ModelSerializer):
    citations = CitationSerializer(many=True, read_only=True)
    # Read via the reverse accessor Django installs from analytics.Feedback's
    # OneToOneField (message.feedback), not analytics.serializers — importing
    # that here would make `rag` depend on `analytics`, backwards from every
    # other dependency between them (analytics observes rag's messages, not
    # the other way around). hasattr() is the standard way to probe a
    # reverse one-to-one: unlike a plain FK, accessing a missing one raises
    # rather than returning None.
    feedback = serializers.SerializerMethodField()

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
            "retrieved_count",
            "citations",
            "feedback",
            "created_at",
        ]

    @extend_schema_field(MessageFeedbackSerializer(allow_null=True))
    def get_feedback(self, message: Message) -> dict[str, str] | None:
        if not hasattr(message, "feedback"):
            return None
        feedback = message.feedback  # type: ignore[attr-defined]
        return {"rating": feedback.rating, "comment": feedback.comment}


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
