import factory
from factory.django import DjangoModelFactory

from analytics.models import Feedback
from rag.factories import MessageFactory


class FeedbackFactory(DjangoModelFactory):
    class Meta:
        model = Feedback

    message = factory.SubFactory(MessageFactory)
    rating = Feedback.Rating.UP
