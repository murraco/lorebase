from django.db import models

from core.models import BaseModel
from rag.models import Message


class Feedback(BaseModel):
    class Rating(models.TextChoices):
        UP = "up", "Up"
        DOWN = "down", "Down"

    # One-to-one, not a foreign key: rating a message is a toggle (you
    # either think an answer was good or you don't), not a log of every
    # time you clicked. Giving the other thumb updates this row instead
    # of adding a second one — otherwise "% positive feedback" would need
    # to decide whether to count every click or only the latest, and
    # someone flip-flopping once would silently double-count.
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name="feedback")
    rating = models.CharField(max_length=10, choices=Rating.choices)
    # Optional context for a 👎 (or a 👍, if there's something specific
    # worth remembering) — not required, so the buttons stay a one-click
    # action and don't force a text box open every time.
    comment = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return f"{self.rating} on {self.message_id}"
