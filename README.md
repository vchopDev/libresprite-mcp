# libresprite-mcp

An MCP server that drives [LibreSprite](https://libresprite.github.io/) headlessly, so an AI
agent can generate and edit pixel art via tool-calling instead of a human using the GUI.

This exists because every "Aseprite MCP" server on GitHub generates **Lua** and shells out to
real Aseprite -- LibreSprite forked before Aseprite switched to Lua and has its own JavaScript
scripting API instead, so none of those servers work against it. This one is written directly
against LibreSprite's JS API and CLI batch flags.

## Requirements

- Python 3.10+
- A [LibreSprite](https://github.com/LibreSprite/LibreSprite) binary on `PATH`, or point
  `LIBRESPRITE_BIN` at one. CI downloads the latest release AppImage; there's no bundled binary.

## Usage

```
pip install -e .
LIBRESPRITE_BIN=/path/to/libresprite libresprite-mcp
```

Point an MCP client (Claude Code, Codex, etc.) at the `libresprite-mcp` command over stdio. See
your client's MCP server configuration docs for how to register a local command-based server.

## Project layout

```
src/libresprite_mcp/
  client.py     Subprocess wrapper around `libresprite -b --script <file>`
  seed.py       Blank PNG generation (stdlib-only, no image library)
  tools.py      Sprite operations -- pure functions, one JS script per call
  server.py     FastMCP wiring: exposes tools.py functions as MCP tools
tests/
  test_seed.py         Unit tests, no LibreSprite binary needed
  integration/          Requires LIBRESPRITE_BIN; skipped otherwise
```

## Architecture in one paragraph

Every LibreSprite invocation is a fresh subprocess -- there's no persistent "active document"
across tool calls, so every tool is path-in/path-out: open a file, mutate it, save it, return
the path. A sprite is a file on disk, not a session handle. LibreSprite has no headless "new
sprite" command (like every `app.command.*` call, `NewFile` is a no-op in batch mode -- see
Known limits), so `create_sprite` writes a minimal blank PNG itself and hands it to
`app.open()`, which does work headlessly.

## Known limits

LibreSprite's scripting API runs against a `UIContext` that batch mode never marks as having
an "active document." Anything routed through the command system (`app.command.*`) is
therefore disabled headlessly, confirmed empirically for `NewLayer`, `NewFrame`, and
`CanvasSize`-via-command. This blocks, in this version:

- **Creating new layers or frames on an existing sprite.** Only pre-authored multi-frame/
  multi-layer files (built once in the GUI) can be edited per-layer/per-frame; new ones can't
  be added from a script.
- **Frame tags** (naming an animation range like "walk" or "idle"): no scripting binding exists
  for these at all, independent of the command-system issue above.

Mutations that go through LibreSprite's `Transaction` API directly instead of the command
system (`sprite.resize()`, the `sprite.width`/`height` setters) are unaffected and confirmed
working headlessly. Fixing the two limits above requires patching LibreSprite itself --
tracked separately, not in this repo's v0.1 scope.

## Status

Early scaffold. `create_sprite`, `resize_canvas`, `export_png`, and `get_png_data` are
implemented and covered by integration tests. `get_pixel`/`set_pixel` are stubbed
(`NotImplementedError`) pending a spike into LibreSprite's `pixelColor` packing API -- see the
open issues on this repo for the current task backlog.
