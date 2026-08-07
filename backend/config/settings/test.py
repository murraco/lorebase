from .base import *  # noqa: F403

DEBUG = False

# Fast, insecure hasher — tests create/authenticate many users and don't
# need production-grade hashing cost.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# .delay()/.apply_async() run the task inline, synchronously, in the same
# process — no broker or worker needed for tests.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Deterministic, no network — CI has no Voyage/Anthropic API keys and
# shouldn't need any.
EMBEDDING_PROVIDER = "fake"
RERANK_PROVIDER = "fake"
LLM_PROVIDER = "fake"

# Throttle state lives in the cache (Redis), not the DB transaction each
# test rolls back — without this, unrelated tests sharing a throttle scope
# could fail depending on run order/count. Nothing about the API layer's
# throttling behavior is under test here.
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}  # noqa: F405
