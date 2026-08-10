import factory
from factory.django import DjangoModelFactory

from core.models import ApiKey, Membership, User, Workspace


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")


class WorkspaceFactory(DjangoModelFactory):
    class Meta:
        model = Workspace

    name = factory.Sequence(lambda n: f"Workspace {n}")


class MembershipFactory(DjangoModelFactory):
    class Meta:
        model = Membership

    user = factory.SubFactory(UserFactory)
    workspace = factory.SubFactory(WorkspaceFactory)
    role = Membership.Role.MEMBER


class ApiKeyFactory(DjangoModelFactory):
    class Meta:
        model = ApiKey

    membership = factory.SubFactory(MembershipFactory)
    name = factory.Sequence(lambda n: f"API key {n}")
    # A fixed, obviously-fake hash by default -- tests that care about a
    # real key/hash pair (auth verification) build one explicitly rather
    # than relying on this value.
    key_hash = factory.Sequence(lambda n: f"fake-hash-{n}")
