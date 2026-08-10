from django.conf import settings
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

from mcp_server.auth import LorebaseTokenVerifier

# issuer_url/resource_server_url point at this same server, not a separate
# OAuth provider -- see the comment on settings.MCP_SERVER_URL for why.
mcp = MCPServer(
    "Lorebase",
    instructions="Search and read notes from the user's personal knowledge base.",
    token_verifier=LorebaseTokenVerifier(),
    auth=AuthSettings(
        issuer_url=settings.MCP_SERVER_URL,
        resource_server_url=settings.MCP_SERVER_URL,
    ),
)
