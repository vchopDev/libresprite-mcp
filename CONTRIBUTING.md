# Contributing

This is a companion tool for the [LibreSprite](https://github.com/LibreSprite/LibreSprite)
community, so PRs are welcome, not just personal use.

## Setup

```
git clone https://github.com/vchopDev/libresprite-mcp
cd libresprite-mcp
pip install -e ".[dev]"
```

You'll also need a LibreSprite binary for integration tests -- either build one from
[the LibreSprite repo](https://github.com/LibreSprite/LibreSprite) (see its `INSTALL.md`) or
grab the latest release AppImage/installer, then set `LIBRESPRITE_BIN`.

## Before opening a PR

```
ruff check .
ruff format --check .
pytest tests --ignore=tests/integration   # unit tests, no binary needed
pytest tests/integration                  # needs LIBRESPRITE_BIN
```

All of the above run in CI; a PR won't merge if any fail.

## Adding a new tool

Each sprite operation lives in `src/libresprite_mcp/tools.py` as a plain function that takes a
`LibreSpriteClient` plus a file path, builds a small JS script, and runs it via
`client.run_script()`. Wire it into `server.py` as a thin `@mcp.tool()` wrapper. Keep the JS
scripts small and inline (readable as part of the Python function, not a separate template
file) -- see `tools.create_sprite` for the pattern.

Before relying on a new part of LibreSprite's scripting API, check whether it goes through
`app.command.*` (routed through `UIContext`, confirmed broken in headless batch mode) or
through the object model / `Transaction` API directly (confirmed working headlessly). See the
README's "Known limits" section. When in doubt, write a throwaway script and run it against a
real binary (`libresprite -b --script test.js`) before building a tool on top of an assumption
about the API's behavior -- the shipped binary has lagged the repo's `src/app/script/api/`
source before.
