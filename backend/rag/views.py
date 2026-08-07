from rest_framework import mixins, viewsets

from rag.models import Conversation, Message
from rag.serializers import ConversationSerializer, MessageSerializer


class ConversationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
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

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Message.objects.none()
        queryset = (
            Message.objects.filter(conversation__workspace__memberships__user=self.request.user)
            .select_related("conversation")
            .prefetch_related("citations__chunk__document")
        )
        conversation_id = self.request.query_params.get("conversation")
        if conversation_id:
            queryset = queryset.filter(conversation_id=conversation_id)
        return queryset
