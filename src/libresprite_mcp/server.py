"""MCP server entrypoint: exposes libresprite_mcp.tools as MCP tools."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from libresprite_mcp import tools
from libresprite_mcp.client import LibreSpriteClient

mcp = MCPServer("libresprite-mcp")
_client: LibreSpriteClient | None = None


def _get_client() -> LibreSpriteClient:
    global _client
    if _client is None:
        _client = LibreSpriteClient()
    return _client


@mcp.tool()
def create_sprite(path: str, width: int, height: int) -> str:
    """Create a new blank sprite file. `path` should end in .ase or .png."""
    return tools.create_sprite(_get_client(), path, width, height)


@mcp.tool()
def resize_canvas(path: str, width: int, height: int) -> str:
    """Resize an existing sprite's canvas in place."""
    return tools.resize_canvas(_get_client(), path, width, height)


@mcp.tool()
def export_png(path: str, out_path: str) -> str:
    """Flatten and export a sprite to a PNG file."""
    return tools.export_png(_get_client(), path, out_path)


@mcp.tool()
def get_png_data(path: str, layer: int = 0, frame: int = 0) -> str:
    """Return base64-encoded PNG data for one layer/frame's image."""
    return tools.get_png_data_b64(_get_client(), path, layer=layer, frame=frame)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
