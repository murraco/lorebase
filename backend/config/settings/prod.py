from .base import *  # noqa: F403
from .base import env

DEBUG = False

# No default here on purpose: production must set this explicitly rather
# than silently falling back to an empty/permissive list.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# nginx (frontend/nginx.conf) terminates TLS and proxies to backend over
# plain HTTP on the Docker network, setting X-Forwarded-Proto. Without
# this, Django never sees the proxy hop as HTTPS -- SECURE_SSL_REDIRECT
# would redirect-loop forever, since every request looks like plain HTTP
# to it even after nginx already redirected it once.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS: tells the browser to only ever use HTTPS for this host, even from
# a stale http:// link or bookmark. Started at one day, not the commonly
# recommended one year -- HSTS is hard to undo (browsers cache it, and a
# misconfiguration locks users out over plain HTTP until it expires), so
# a conservative value for the first real rollout is the right default;
# raise it once this has run in production without issues.
SECURE_HSTS_SECONDS = 86400
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# django-cors-headers is deliberately NOT added, despite the roadmap task
# naming CORS explicitly: frontend/nginx.conf proxies /api/* same-origin
# (see its own comment on why -- it's also what makes the session cookie
# and CSRF work without any cross-origin cookie configuration at all).
# There is no cross-origin request in this deployment shape for CORS
# headers to govern. Revisit only if a client starts calling the API from
# a different origin than the one nginx serves the SPA from.

# One JSON object per line, not Django's default human-readable format --
# dev keeps the default (nicer to read in a raw terminal, no aggregator to
# feed locally). django.server carries the access log (uvicorn's own
# access logging is disabled in infra/docker-compose.prod.yml so this is
# the only copy, not a second one in a different format).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "config.logging.JSONFormatter"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
