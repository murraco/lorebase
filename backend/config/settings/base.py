"""Settings shared by every environment.

Environment-specific files (dev/test/prod) import everything from here with
``from .base import *`` and override only what differs.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# Local development reads a .env file; in Docker/CI the real environment
# variables are already set by the orchestrator, so this is a no-op there.
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "drf_spectacular",
    "core",
    "sources",
    "ingestion",
    "rag",
    "analytics",
]

# Fixed at column-creation time since VectorField's dimension is baked into
# the Postgres column. Cheap to change now (the column is empty); expensive
# once real embeddings are populated (needs a full re-embed). 1024 is
# voyage-4's default output dimension (Matryoshka learning also supports
# 2048/512/256) — verified against https://docs.voyageai.com/docs/embeddings.
EMBEDDING_DIMENSIONS = env.int("EMBEDDING_DIMENSIONS", default=1024)

# "local" (default), "voyage", or "fake". "local" runs a bi-encoder
# in-process via sentence-transformers — no API key, no rate limit — and
# is the default precisely because "voyage" was: a fresh clone with no
# .env then starts on a free-tier account whose 3 RPM ceiling broke real
# usage repeatedly here. The trade-off of the local default is a
# multi-hundred-MB model download on first use instead of an immediate
# failure nobody expects.
EMBEDDING_PROVIDER = env("EMBEDDING_PROVIDER", default="local")
EMBEDDING_MODEL = env("EMBEDDING_MODEL", default="voyage-4")
VOYAGE_API_KEY = env("VOYAGE_API_KEY", default="")
# Multilingual, MIT licensed, and — the deciding factor — 1024-dimensional
# natively, matching EMBEDDING_DIMENSIONS above exactly (no schema
# migration needed to switch providers). See rag/embeddings/local.py.
LOCAL_EMBEDDING_MODEL = env("LOCAL_EMBEDDING_MODEL", default="intfloat/multilingual-e5-large")
# $/million tokens, for cost logging only — not wired into any billing
# path. None by default rather than a guessed number: verified once
# against https://docs.voyageai.com/docs/pricing (voyage-4: $0.06/M as of
# 2026-08), but pricing pages change, so this stays override-only instead
# of silently going stale as a hardcoded default.
EMBEDDING_COST_PER_MILLION_TOKENS_USD = env.float(
    "EMBEDDING_COST_PER_MILLION_TOKENS_USD", default=0.0
)

# "local" (default), "voyage", or "fake". Same reasoning as
# EMBEDDING_PROVIDER above — here the rate limit surfaced as either a
# real 500 or silently degraded retrieval quality once RerankingRetriever
# fell back to unreranked results.
RERANK_PROVIDER = env("RERANK_PROVIDER", default="local")
# Verified against https://docs.voyageai.com/docs/pricing: rerank-2.5 is
# current (rerank-2 is legacy), $0.05/M tokens, 200M free.
RERANK_MODEL = env("RERANK_MODEL", default="rerank-2.5")
# Multilingual (14 languages via MMARCO, including English and Spanish),
# not the smaller English-only ms-marco-MiniLM default — the real notes
# here mix both. Standard architecture, no trust_remote_code needed —
# see rag/reranking/local.py for why that mattered in practice.
LOCAL_RERANK_MODEL = env("LOCAL_RERANK_MODEL", default="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")

# "lexical", "dense", "hybrid", or "hybrid_reranked".
RETRIEVAL_STRATEGY = env("RETRIEVAL_STRATEGY", default="hybrid_reranked")

# "anthropic" or "fake" (deterministic, no network — used in tests/CI).
LLM_PROVIDER = env("LLM_PROVIDER", default="anthropic")
# Haiku, not Sonnet: a deliberate cost choice for this project, not a
# capability default.
LLM_MODEL = env("LLM_MODEL", default="claude-haiku-4-5-20251001")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
# $/million tokens, logging only, same reasoning as EMBEDDING_COST above:
# no default rather than a guessed number. Verified once against
# https://platform.claude.com/docs/en/about-claude/pricing (Haiku 4.5:
# $1/MTok input, $5/MTok output, as of 2026-08).
LLM_COST_PER_MILLION_INPUT_TOKENS_USD = env.float(
    "LLM_COST_PER_MILLION_INPUT_TOKENS_USD", default=0.0
)
LLM_COST_PER_MILLION_OUTPUT_TOKENS_USD = env.float(
    "LLM_COST_PER_MILLION_OUTPUT_TOKENS_USD", default=0.0
)

# Safety net: parsing and chunking work entirely in memory, not streaming,
# so a pathologically large single file could exhaust memory. Connectors
# skip (and log) anything past this size rather than trying to process it.
MAX_DOCUMENT_SIZE_BYTES = env.int("MAX_DOCUMENT_SIZE_BYTES", default=10 * 1024 * 1024)  # 10 MB

# A classic personal access token (repo scope for private repos, none
# needed for public ones), not an OAuth app: this connector reads the
# owner's own repos, so there's no second party to authorize on behalf
# of. Optional — an empty token still works against public repos, just
# at GitHub's much lower unauthenticated rate limit (60/hour vs 5000/hour).
GITHUB_TOKEN = env("GITHUB_TOKEN", default="")

AUTH_USER_MODEL = "core.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://lorebase:lorebase@localhost:5434/lorebase",
    ),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Local filesystem storage for uploaded originals (PDFs cached for citation
# purposes). Django's own pluggable storage API, not a custom interface —
# swapping to S3/Garage later is a settings change (a new STORAGES backend
# and, typically, django-storages), not a rewrite of any calling code.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "storage"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "120/minute",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Lorebase API",
    "DESCRIPTION": "Personal knowledge base with RAG, hybrid search, and verifiable citations.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Without this, request and response bodies share one schema (e.g.
    # "Source") that includes read-only fields like `status`/`created_at`
    # as required properties — technically correct for responses, but it
    # makes every generated TS type for a POST/PATCH body demand fields
    # the client can't and shouldn't send. This splits them into e.g.
    # "Source" (response) and "SourceRequest" (request, read-only fields
    # dropped).
    "COMPONENT_SPLIT_REQUEST": True,
}

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# Native Redis cache backend (built into Django since 4.0, no extra package
# needed). Used for the per-source sync lock — cache.add() is an atomic
# "set if not already set", exactly Redis's SET NX under the hood.
# A different Redis DB index than the Celery broker/backend, not because
# anything would break sharing one (key names don't collide), but to keep
# "queue data" and "cache data" cleanly separated.
REDIS_CACHE_URL = env("REDIS_CACHE_URL", default="redis://localhost:6379/1")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_CACHE_URL,
    }
}
