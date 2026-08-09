import pytest
from django.db import IntegrityError

from analytics.factories import FeedbackFactory
from analytics.models import Feedback
from rag.factories import MessageFactory

pytestmark = pytest.mark.django_db


def test_feedback_defaults_to_no_comment() -> None:
    feedback = FeedbackFactory()

    assert feedback.comment == ""


def test_a_message_can_only_have_one_feedback_row() -> None:
    """The OneToOneField is the actual constraint the "rating is a
    toggle, not a log" design relies on — this is what makes a second
    Feedback.objects.create() for the same message a database error
    rather than something application code has to remember to prevent.
    """
    message = MessageFactory()
    FeedbackFactory(message=message)

    with pytest.raises(IntegrityError):
        FeedbackFactory(message=message)


def test_deleting_a_message_deletes_its_feedback() -> None:
    feedback = FeedbackFactory()
    message = feedback.message

    message.delete()

    assert not Feedback.objects.filter(pk=feedback.pk).exists()
