import factory
from factory.django import DjangoModelFactory

from core.factories import UserFactory, WorkspaceFactory
from rag.models import Conversation, Message


class ConversationFactory(DjangoModelFactory):
    class Meta:
        model = Conversation

    workspace = factory.SubFactory(WorkspaceFactory)
    user = factory.SubFactory(UserFactory)


class MessageFactory(DjangoModelFactory):
    class Meta:
        model = Message

    conversation = factory.SubFactory(ConversationFactory)
    role = Message.Role.ASSISTANT
    content = factory.Sequence(lambda n: f"Answer {n}")
