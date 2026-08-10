import pytest
from django.db import IntegrityError

from core.factories import ApiKeyFactory, MembershipFactory, UserFactory, WorkspaceFactory
from core.models import Membership

pytestmark = pytest.mark.django_db


def test_membership_default_role_is_member() -> None:
    membership = MembershipFactory()

    assert membership.role == Membership.Role.MEMBER


def test_user_can_belong_to_multiple_workspaces() -> None:
    """The whole point of Membership existing instead of a direct
    Workspace -> User foreign key: one user, several workspaces."""
    user = UserFactory()
    workspace_a = WorkspaceFactory()
    workspace_b = WorkspaceFactory()

    MembershipFactory(user=user, workspace=workspace_a)
    MembershipFactory(user=user, workspace=workspace_b)

    assert user.memberships.count() == 2


def test_workspace_can_have_multiple_members() -> None:
    workspace = WorkspaceFactory()
    user_a = UserFactory()
    user_b = UserFactory()

    MembershipFactory(user=user_a, workspace=workspace)
    MembershipFactory(user=user_b, workspace=workspace)

    assert workspace.memberships.count() == 2


def test_duplicate_membership_is_rejected() -> None:
    user = UserFactory()
    workspace = WorkspaceFactory()
    MembershipFactory(user=user, workspace=workspace)

    with pytest.raises(IntegrityError):
        MembershipFactory(user=user, workspace=workspace)


def test_api_key_belongs_to_a_membership() -> None:
    membership = MembershipFactory()

    api_key = ApiKeyFactory(membership=membership)

    assert api_key in membership.api_keys.all()


def test_duplicate_key_hash_is_rejected() -> None:
    """The actual security property key_hash's uniqueness buys: two keys
    can never hash to the same value and silently authenticate as each
    other's owner."""
    ApiKeyFactory(key_hash="same-hash")

    with pytest.raises(IntegrityError):
        ApiKeyFactory(key_hash="same-hash")
