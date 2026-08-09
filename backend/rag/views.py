from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets

from rag.models import Conversation, Message
from rag.serializers import ConversationSerializer, MessageSerializer


class ConversationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Destroy is a real delete, not a soft one: a conversation carries no
    value once discarded, and its Messages and Citations cascade away with
    it. Nothing indexed is touched — Citation points at a Chunk, not the
    other way around, so the notes themselves are unaffected.
    """

    serializer_class = ConversationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Conversation.objects.none()
        return Conversation.objects.filter(workspace__memberships__user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class MessageViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Read-only: assistant messages are only ever created by the chat
    orchestration in rag.chat.service.ask() (retrieval, LLM call, citation
    validation), never via a plain CRUD POST here.
    """

    serializer_class = MessageSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "conversation",
                OpenApiTypes.UUID,
                description="Filter messages down to a single conversation.",
            )
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Message.objects.none()
        queryset = (
            Message.objects.filter(conversation__workspace__memberships__user=self.request.user)
            .select_related("conversation", "feedback")
            .prefetch_related("citations__chunk__document")
        )
        conversation_id = self.request.query_params.get("conversation")
        if conversation_id:
            queryset = queryset.filter(conversation_id=conversation_id)
        return queryset
