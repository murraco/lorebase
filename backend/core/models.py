import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser, BaseModel):  # noqa: DJ008 -- __str__ comes from AbstractUser
    pass


class Workspace(BaseModel):
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


class Membership(BaseModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MEMBER = "member", "Member"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "workspace"], name="unique_membership_per_user_workspace"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.workspace} ({self.role})"


class ApiKey(BaseModel):
    """Ties an MCP client to a Membership, so it inherits exactly the same
    workspace/user permission boundary a person already has -- no separate
    permission model to keep in sync. Only `key_hash` is ever stored; the
    real key is shown once, at creation, and is unrecoverable after that
    (same pattern as Stripe/GitHub tokens).
    """

    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=100)
    key_hash = models.CharField(max_length=64, unique=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.membership})"
