from .base import *  # noqa: F403

DEBUG = False

# Fast, insecure hasher — tests create/authenticate many users and don't
# need production-grade hashing cost.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# .delay()/.apply_async() run the task inline, synchronously, in the same
# process — no broker or worker needed for tests.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Deterministic, no network — CI has no Voyage API key and shouldn't need one.
EMBEDDING_PROVIDER = "fake"
RERANK_PROVIDER = "fake"
