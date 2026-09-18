# Testing

This section documents the local and integration checks for the LibreSprite
patches tracked by issues #8/#9 and #13/#14.

For the current architectural direction and the headless API backlog, see
[Headless-API-Improvement-Plan.md](Headless-API-Improvement-Plan.md). The plan
records community feedback as context; it is not a LibreSprite maintainer
commitment or an assumption that LibreSprite wants to adopt the MCP server.

## Environment

The verified Windows setup is:

- MSYS2 at `C:\msys64`, using the UCRT64 environment
- GCC 16.2.0
- CMake 4.4.3
- Ninja 1.13.2
- Windows SDK 10.0.26100.0
- QuickJS-NG 0.11.0, vendored in `third_party/quickjs-amalgam`

The local LibreSprite executable is built at:

```text
C:\Users\victo\Projects\AI-Projects\Libresprite\build-codex-phase2\bin\libresprite.exe
```

The current LibreSprite source tree uses QuickJS-NG; it does not require a
separate V8 SDK.

## Build LibreSprite

From PowerShell:

```powershell
$env:MSYSTEM = 'UCRT64'
& 'C:\msys64\usr\bin\bash.exe' -lc 'cmake -S /c/Users/victo/Projects/AI-Projects/Libresprite -B /c/Users/victo/Projects/AI-Projects/Libresprite/build-codex-phase2 -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DRELEASE_TAG=ON -DRELEASE_VERSION=1.3.0 -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++'
& 'C:\msys64\usr\bin\bash.exe' -lc 'cmake --build /c/Users/victo/Projects/AI-Projects/Libresprite/build-codex-phase2 --target libresprite --parallel 4'
```

The source submodules must be initialized first:

```powershell
git -C 'C:\Users\victo\Projects\AI-Projects\Libresprite' submodule update --init --recursive
```

## Test the upstream scripting bindings

Run these from the LibreSprite source directory after checking out the merged
`fork/master`. The scripts are now included by the merged fork PRs.

```powershell
$env:MSYSTEM = 'UCRT64'
& 'C:\msys64\usr\bin\bash.exe' -lc 'cd /c/Users/victo/Projects/AI-Projects/Libresprite && /c/Users/victo/Projects/AI-Projects/Libresprite/build-codex-phase2/bin/libresprite.exe -b --script /c/Users/victo/Projects/AI-Projects/Libresprite/tests/scripts/frame_tags.js'
& 'C:\msys64\usr\bin\bash.exe' -lc 'cd /c/Users/victo/Projects/AI-Projects/Libresprite && /c/Users/victo/Projects/AI-Projects/Libresprite/build-codex-phase2/bin/libresprite.exe -b --script /c/Users/victo/Projects/AI-Projects/Libresprite/tests/scripts/document_api.js'
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

Install the project environment and run the unit tests:

```powershell
Set-Location 'C:\Users\victo\Projects\AI-Projects\libresprite-mcp'
& '.\.venv\Scripts\python.exe' -m pytest -q
```

For end-to-end tests against the locally built LibreSprite binary:

```powershell
$env:LIBRESPRITE_BIN = 'C:\Users\victo\Projects\AI-Projects\Libresprite\build-codex-phase2\bin\libresprite.exe'
$env:Path = "C:\msys64\ucrt64\bin;$env:Path"
& '.\.venv\Scripts\python.exe' -m pytest tests/integration/test_smoke.py -q
```

The verified baseline result is `7 passed`.

## Test the Warhex asset batch

The generated production assets live in the sibling Warhex repository under
`assets/art/{ui,terrain,resources,buildings,units,fx}`. The logical-ID manifest
is `assets/art/asset_manifest.json`.

Verify the layered `.ase` sources with the patched local LibreSprite build:

```powershell
$env:APPDATA = 'C:\Users\victo\Projects\AI-Projects\libresprite-mcp\.tmp\appdata'
$env:LOCALAPPDATA = $env:APPDATA
$env:LIBRESPRITE_BIN = 'C:\Users\victo\Projects\AI-Projects\Libresprite\build-codex-phase2\bin\libresprite.exe'
$env:WARHEX_ASSETS_ROOT = 'C:\Users\victo\Projects\AI-Projects\Strategic-War-Game\warhex\assets\art'
$env:Path = "C:\msys64\ucrt64\bin;$env:Path"
& '.\.venv\Scripts\python.exe' 'scripts\verify_layered_sources.py' --assets-root $env:WARHEX_ASSETS_ROOT
```

The asset batch check expects 60 production PNGs, 60 matching `.ase` sources,
52 logical manifest IDs, and no missing manifest references. The PNG audit also
checks the category dimensions and the allowed Sangue e Ferro palette.

On Windows installations where pytest cannot scan the default
`AppData\Local\Temp\pytest-of-<user>` directory, pass a writable repository
temporary directory explicitly:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q --basetemp 'C:\path\to\libresprite-mcp\.tmp\pytest'
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
