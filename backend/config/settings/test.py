from .base import *  # noqa: F403

DEBUG = False

# Fast, insecure hasher — tests create/authenticate many users and don't
# need production-grade hashing cost.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
