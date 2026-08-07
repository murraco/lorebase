import factory
from factory.django import DjangoModelFactory

from core.factories import UserFactory, WorkspaceFactory
from rag.models import Conversation


class ConversationFactory(DjangoModelFactory):
    class Meta:
        model = Conversation

    workspace = factory.SubFactory(WorkspaceFactory)
    user = factory.SubFactory(UserFactory)
