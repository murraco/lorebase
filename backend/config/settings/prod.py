from .base import *  # noqa: F403
from .base import env

DEBUG = False

# No default here on purpose: production must set this explicitly rather
# than silently falling back to an empty/permissive list.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Full production hardening (HSTS, proxy headers, rate limiting, etc.) is
# addressed together as part of the deploy-readiness milestone.
