import hashlib

from django.utils import timezone
from mcp.server.auth.provider import AccessToken, TokenVerifier

from core.models import ApiKey


class LorebaseTokenVerifier(TokenVerifier):
    """The whole of Etapa 17's auth, despite the OAuth-shaped interface
    the SDK expects (AccessToken has client_id/scopes/subject like a JWT
    would): under the hood this is a flat API key lookup, same as
    core/management/commands/create_mcp_api_key.py hashes on the way in.
    workspace_id/membership_id ride in `claims` -- it's the only field on
    AccessToken meant for whatever extra context a real deployment needs,
    and it's how the tools in mcp_server/tools.py know which workspace to
    scope every query to.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        api_key = (
            await ApiKey.objects.select_related("membership")
            .filter(key_hash=key_hash)
            .afirst()
        )
        if api_key is None:
            return None

        api_key.last_used_at = timezone.now()
        await api_key.asave(update_fields=["last_used_at"])

        membership = api_key.membership
        return AccessToken(
            token=token,
            client_id=str(api_key.id),
            scopes=[],
            subject=str(membership.user_id),
            claims={
                "workspace_id": str(membership.workspace_id),
                "membership_id": str(membership.id),
            },
        )
