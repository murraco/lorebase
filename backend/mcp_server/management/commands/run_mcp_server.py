from typing import Any

from django.core.management.base import BaseCommand

import mcp_server.tools  # noqa: F401 -- import side effect: registers the 3 @mcp.tool()s
from mcp_server.server import mcp


class Command(BaseCommand):
    help = "Run the Lorebase MCP server over Streamable HTTP."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--port", type=int, default=8001)

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write(
            f"MCP server listening on {options['host']}:{options['port']}, path /mcp"
        )
        mcp.run(transport="streamable-http", host=options["host"], port=options["port"])
