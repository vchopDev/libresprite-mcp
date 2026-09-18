# Testing

This section documents the local and integration checks for the LibreSprite
patches tracked by issues #8/#9 and #13/#14.

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
C:\Users\victo\Projects\AI-Projects\Libresprite\build-codex-ucrt\bin\libresprite.exe
```

The current LibreSprite source tree uses QuickJS-NG; it does not require a
separate V8 SDK.

## Build LibreSprite

From PowerShell:

```powershell
$env:MSYSTEM = 'UCRT64'
& 'C:\msys64\usr\bin\bash.exe' -lc 'cmake -S /c/Users/victo/Projects/AI-Projects/Libresprite -B /c/Users/victo/Projects/AI-Projects/Libresprite/build-codex-ucrt -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++'
& 'C:\msys64\usr\bin\bash.exe' -lc 'cmake --build /c/Users/victo/Projects/AI-Projects/Libresprite/build-codex-ucrt --target libresprite --parallel 4'
```

The source submodules must be initialized first:

```powershell
git -C 'C:\Users\victo\Projects\AI-Projects\Libresprite' submodule update --init --recursive
```

## Test the upstream scripting bindings

Run these from the LibreSprite source directory. The scripts are part of the
corresponding feature branches/PRs.

```powershell
$env:MSYSTEM = 'UCRT64'
& 'C:\msys64\usr\bin\bash.exe' -lc 'cd /c/Users/victo/Projects/AI-Projects/Libresprite && /c/Users/victo/Projects/AI-Projects/Libresprite/build-codex-ucrt/bin/libresprite.exe -b --script /c/Users/victo/Projects/AI-Projects/Libresprite/tests/scripts/frame_tags.js'
& 'C:\msys64\usr\bin\bash.exe' -lc 'cd /c/Users/victo/Projects/AI-Projects/Libresprite && /c/Users/victo/Projects/AI-Projects/Libresprite/build-codex-ucrt/bin/libresprite.exe -b --script /c/Users/victo/Projects/AI-Projects/Libresprite/tests/scripts/document_api.js'
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
$env:LIBRESPRITE_BIN = 'C:\Users\victo\Projects\AI-Projects\Libresprite\build-codex-ucrt\bin\libresprite.exe'
$env:Path = "C:\msys64\ucrt64\bin;$env:Path"
& '.\.venv\Scripts\python.exe' -m pytest tests/integration/test_smoke.py -q
```

The verified baseline result is `7 passed`.

## Release gate for MCP feature tools

The upstream PRs are:

- Frame tags: https://github.com/LibreSprite/LibreSprite/pull/663
- Layer/frame creation: https://github.com/LibreSprite/LibreSprite/pull/664

Do not add or un-stub the corresponding MCP tools until each PR has been
merged and its changes are present in a tagged LibreSprite release. CI fetches
the latest release, not `master`; testing only against a local PR build would
not verify the binary used by CI.

After a release contains a patch, set `LIBRESPRITE_BIN` to that release,
rerun the integration suite, add the feature-specific MCP integration tests,
and only then remove the matching Known Limits entry from the main README.

Issue #10 remains a deferred fallback and is intentionally not part of this
test plan.
