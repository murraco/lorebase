import pytest
from django.db import IntegrityError

from core.factories import MembershipFactory, UserFactory, WorkspaceFactory
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
