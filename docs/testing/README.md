# Testing

This section documents the local and integration checks for the LibreSprite
patches tracked by issues #8/#9 and #13/#14.

For the current architectural direction and the headless API backlog, see
[Headless-API-Improvement-Plan.md](Headless-API-Improvement-Plan.md). The plan
records community feedback as context; it is not a LibreSprite maintainer
commitment or an assumption that LibreSprite wants to adopt the MCP server.

## Local paths

This repo does not assume where you keep your checkouts. Set these once per
shell before running any command below:

```powershell
$env:LIBRESPRITE_SRC = 'path\to\your\LibreSprite\checkout'
$env:LIBRESPRITE_BIN = "$env:LIBRESPRITE_SRC\build-codex-phase2\bin\libresprite.exe"
```

Commands under "Test this MCP repository" assume your shell is already at this
repo's root (`libresprite-mcp\`).

## Environment

The verified Windows setup is:

- MSYS2 at `C:\msys64`, using the UCRT64 environment
- GCC 16.2.0
- CMake 4.4.3
- Ninja 1.13.2
- Windows SDK 10.0.26100.0
- QuickJS-NG 0.11.0, vendored in `third_party/quickjs-amalgam`

The current LibreSprite source tree uses QuickJS-NG; it does not require a
separate V8 SDK.

## Build LibreSprite

From PowerShell (with `LIBRESPRITE_SRC` set, see "Local paths" above):

```powershell
$env:MSYSTEM = 'UCRT64'
& 'C:\msys64\usr\bin\bash.exe' -lc "cmake -S '$env:LIBRESPRITE_SRC' -B '$env:LIBRESPRITE_SRC/build-codex-phase2' -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DRELEASE_TAG=ON -DRELEASE_VERSION=1.3.0 -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++"
& 'C:\msys64\usr\bin\bash.exe' -lc "cmake --build '$env:LIBRESPRITE_SRC/build-codex-phase2' --target libresprite --parallel 4"
```

(cmake accepts a Windows-style path here; forward slashes avoid backslash-escaping
issues when the string crosses from PowerShell into the bash -lc argument.)

The source submodules must be initialized first:

```powershell
git -C $env:LIBRESPRITE_SRC submodule update --init --recursive
```

If the build links against MSYS2 runtime DLLs (an MSYS2/UCRT64 build does),
the resulting `libresprite.exe` will fail to start outside a shell that has
`C:\msys64\ucrt64\bin` on `PATH` — see the exit-code notes in
[Design-Notes/LibreSprite-Scripting-API.md](../Design-Notes/LibreSprite-Scripting-API.md)
("Native exit codes: do not conflate them") if you hit an unexplained large
exit code with empty stderr.

## Test the upstream scripting bindings

Run these from the LibreSprite source directory after checking out the merged
`fork/master`. The scripts are now included by the merged fork PRs.

```powershell
$env:MSYSTEM = 'UCRT64'
& 'C:\msys64\usr\bin\bash.exe' -lc "cd '$env:LIBRESPRITE_SRC' && '$env:LIBRESPRITE_BIN' -b --script tests/scripts/frame_tags.js"
& 'C:\msys64\usr\bin\bash.exe' -lc "cd '$env:LIBRESPRITE_SRC' && '$env:LIBRESPRITE_BIN' -b --script tests/scripts/document_api.js"
```

Expected output:

```text
frame tag bindings: PASS
DocumentApi layer/frame bindings: PASS
```

The frame-tag test covers creation, rename, recolor, range changes, animation
direction, save/reopen persistence, and removal. The DocumentApi test covers
new-layer creation, copied and empty frame creation, save/reopen persistence,
and layer/frame counts.

## Test this MCP repository

Install the project environment and run the unit tests (from this repo's root):

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q
```

For end-to-end tests against the locally built LibreSprite binary:

```powershell
$env:Path = "C:\msys64\ucrt64\bin;$env:Path"
& '.\.venv\Scripts\python.exe' -m pytest tests/integration/test_smoke.py -q
```

The verified baseline result is `7 passed`.

## Native process exit diagnostics

The Python client decodes native Windows status values before reporting a
LibreSprite failure. These values must not be treated as JavaScript errors:

| Exit code (unsigned) | Hex | Meaning | First action |
| --- | --- | --- | --- |
| `3221225781` | `0xC0000135` | `STATUS_DLL_NOT_FOUND`: the process never started because Windows could not load a required DLL. | Deploy the runtime DLLs beside `libresprite.exe`. |
| `3221225477` | `0xC0000005` | `STATUS_ACCESS_VIOLATION`: LibreSprite reached native code and crashed. | Inspect the binding/operation and reproduce with a minimal script. |
| `3221225493` | `0xC0000015` | `STATUS_NONEXISTENT_SECTOR`: the executable is broken or incomplete. | Replace or rebuild the binary. |

If the exit is one of these NTSTATUS values and `stderr` is empty, the
failure happened before the script could run. The client also passes one
explicit environment to both its `--version` preflight and every script
process; `APPDATA` and `LOCALAPPDATA` should point at a writable isolated
profile for headless runs.

## Testing against a downstream asset pipeline (e.g. Warhex)

`libresprite-mcp` itself has no built-in assumption about which project
consumes it — `scripts/create_layered_sources.py` and
`scripts/verify_layered_sources.py` take an explicit `--assets-root` (or
`WARHEX_ASSETS_ROOT` env var); there is no default that assumes a specific
sibling repo exists. Point it at any project's asset tree laid out as
`assets/art/{ui,terrain,resources,buildings,units,fx}` with a
`assets/art/asset_manifest.json` logical-ID manifest.

Example, verifying the layered `.ase` sources against a downstream project:

```powershell
$env:APPDATA = "$PWD\.tmp\appdata"
$env:LOCALAPPDATA = $env:APPDATA
$env:Path = "C:\msys64\ucrt64\bin;$env:Path"
$env:DOWNSTREAM_ASSETS_ROOT = 'path\to\your\game\assets\art'
& '.\.venv\Scripts\python.exe' 'scripts\verify_layered_sources.py' --assets-root $env:DOWNSTREAM_ASSETS_ROOT
```

The asset batch check reports PNG/`.ase` pair counts, manifest ID coverage,
category dimensions, and (if the consuming project defines one) an allowed
palette. The specific counts and palette in any given run depend entirely on
the target project's own asset tree, not on anything in this repo.

On Windows installations where pytest cannot scan the default
`AppData\Local\Temp\pytest-of-<user>` directory, pass a writable repository
temporary directory explicitly:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q --basetemp '.\.tmp\pytest'
```

## Release gate for MCP feature tools

The public `vchopDev/LibreSprite` fork contains the development patches for
frame tags and layer/frame creation. They are not yet present in a tagged
`LibreSprite/LibreSprite` release, so the corresponding MCP tools must remain
behind the release gate. The local release-like build verifies the combined
code, but CI currently fetches the latest release from
`LibreSprite/LibreSprite`, not from the fork; a fork-only build will not
automatically become the CI binary.

After a release consumed by CI contains the patches, set `LIBRESPRITE_BIN` to
that release,
rerun the integration suite, add the feature-specific MCP integration tests,
and only then remove the matching Known Limits entry from the main README.

Issue #10 remains a deferred fallback and is intentionally not part of this
test plan.
