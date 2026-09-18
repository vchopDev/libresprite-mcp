# Headless API improvement plan

Status: planning document for `libresprite-mcp` and the public development fork.
This is not an upstream LibreSprite roadmap and does not imply that LibreSprite
maintainers want to adopt the MCP server.

## Community context

The LibreSprite moderator gave the following direction:

- The project is finishing a release and is currently in a feature freeze. New
  feature PRs can be sent, but they may not receive review until after the
  release unless they are urgent bug fixes.
- The project is defining its code, GitHub, and AI contribution policy. The
  admins are considering a simplified version of
  [`llama.cpp`'s `AGENTS.md`](https://github.com/ggml-org/llama.cpp/blob/master/AGENTS.md).
- The project is not categorically opposed to AI-assisted workflows, but wants
  a contribution policy and a practical middle ground.
- For MCP specifically, a future in-process script may become possible if more
  of the missing functionality is moved into LibreSprite first. The immediate
  priority is making headless LibreSprite more useful.

These comments are useful constraints for this repository, not a request to
merge or adopt `libresprite-mcp`.

## Current baseline

`libresprite-mcp` currently uses a conservative path-in/path-out model:

1. Start a fresh `libresprite -b --script` process.
2. Open one document from disk.
3. Apply a mutation through the JavaScript object model.
4. Save the document and return the path or data.

This is slower than a persistent session, but it avoids depending on a shared
GUI document or a long-lived JavaScript process. The current Windows binary
also showed that `--shell` is not a usable persistent transport, so correctness
and API coverage come before performance work.

The important implementation distinction is:

- `app.command.*` is gated by the GUI `UIContext` and is not reliable after a
  headless `app.open()`.
- Direct `Transaction`/`DocumentApi` operations are the safer path for headless
  bindings and already back operations such as sprite resizing.
- The fork contains local bindings for frame tags and layer/frame creation.
  They are not yet available in a tagged upstream LibreSprite release, so the
  corresponding MCP tools remain release-gated.

## Direction

### 1. Improve headless correctness first

Every new binding should be tested in a fresh headless process and then again
after save/reopen. The test must prove both the mutation and the persisted file
state; a JavaScript call returning without an exception is not sufficient.

Required test properties:

- no active GUI document or window is required;
- invalid layer/frame/index inputs fail with a clear script error;
- the result survives save and reopen;
- the test works with the same binary layout used by CI;
- the operation does not depend on state left behind by a previous tool call.

### 2. Prefer existing `DocumentApi` and `Transaction` paths

The next API work should expose existing native operations instead of repairing
the whole command system. Each candidate needs a small binding and a focused
headless persistence test. Do not expose the entire header as a single large
feature; keep changes small, reviewable, and aligned with existing script API
naming.

#### Coverage matrix (2026-09-18, read against `document_api.h` and the current
`src/app/script/api/*.cpp` bindings — not just this plan's earlier summary)

| `DocumentApi` method | Bound in script today? |
| --- | --- |
| `setSpriteSize` | Yes — `sprite.width=` / `.height=` / `.resize()` |
| `cropSprite` | **Yes, as of 2026-09-18** — `sprite.crop()` was a dead-code no-op, now wired to `cropSprite()`. See [[Design-Notes/LibreSprite-Scripting-API]]. |
| `setSpriteTransparentColor`, `trimSprite`, `setPixelFormat` | No |
| `addFrame`, `addEmptyFrame` | Yes — `sprite.addFrame()` / `.addEmptyFrame()` |
| `removeFrame` | **Yes, as of 2026-09-18** — `sprite.removeFrame(index)`, refuses to remove the sprite's last frame |
| `moveFrame` | **Yes, as of 2026-09-18** — `sprite.moveFrame(frame, beforeFrame)`, throws on out-of-range indices instead of the native silent no-op |
| `copyFrame` | **Yes, as of 2026-09-18** — `sprite.copyFrame(fromFrame, newFrame)`, `newFrame` optional (defaults to the end), throws on out-of-range indices |
| `setFrameDuration` | **Yes, as of 2026-09-18** — `sprite.setFrameDuration(frame, msecs)`, throws on an out-of-range frame or a duration outside `[1,65535]` instead of the native silent no-op/clamp |
| `setFrameRangeDuration` | **Yes, as of 2026-09-18** — `sprite.setFrameRangeDuration(from, to, msecs)`, throws instead of relying on native `ASSERT`s (compiled out in release) |
| `addEmptyFramesTo`, `setTotalFrames` | No |
| `setCelPosition` | Yes — `cel.setPosition()` |
| `setCelOpacity` | **Yes, as of 2026-09-18** — `cel.opacity` getter/setter, validated to `[0,255]` |
| `addCel` | **Yes, as of 2026-09-18** — `layer.addCel(frame)`, creates a blank sprite-sized cel; throws if the frame already has one (native only `ASSERT`s this) |
| `clearCel` | **Yes, as of 2026-09-18** — `layer.clearCel(frame)`, no-op if the frame has no cel |
| `copyCel` | **Yes, as of 2026-09-18** — `layer.copyCel(fromFrame, destinationLayer, toFrame)`, duplicates a cel across layers/frames |
| `moveCel`, `swapCel` | No |
| `newLayer` | Yes — `sprite.newLayer()` |
| `removeLayer` | **Yes, as of 2026-09-18** — `sprite.removeLayer(layer)`, refuses to remove the sprite's last layer or a layer from another sprite |
| `newLayerFolder`, `restackLayerAfter`, `restackLayerBefore`, `backgroundFromLayer`, `layerFromBackground`, `flattenLayers`, `duplicateLayerAfter`, `duplicateLayerBefore` | No |
| `replaceImage`, `flipImage`, `flipImageWithMask` | No |
| `copyToCurrentMask`, `setMaskPosition` | No |
| `setPalette` | Partial — only reachable via `sprite.loadPalette(file)` (loads from disk); no direct in-script palette edit, blocked by the read crash above |

**Status 2026-09-18**: the four P1 items above are implemented and tested
(`tests/scripts/document_api_p1.js`, covers both the mutation and save/reopen
persistence, plus the invalid-input error paths) on local branch
`codex-headless-api-p1` in the `vchopDev/LibreSprite` fork. Committed locally
only — not pushed, no PR, per the current no-upstream-interaction direction.
Regression-checked against the existing `frame_tags.js` and `document_api.js`
suites (still pass). `moveFrame`/`copyFrame` were deliberately left out of this
batch — `moveFrame`'s native implementation silently no-ops on invalid input
(mirrors the old `crop()` problem) and needs its own bounds-checked wrapper
plus a closer read before it's safe to add; better as its own small change.

**Status 2026-09-18 (L4, Claude)**: `moveFrame`/`copyFrame` are now bound too,
on the same `codex-headless-api-p1` branch, still local/uncommitted-to-upstream
(no push, no PR). `DocumentApi::copyFrame` turned out to have the same
unguarded-bounds shape as `moveFrame` — no native validation at all on either
`frame_t` argument, confirmed by reading `document_api.cpp` before writing the
wrapper — so both bindings validate frame indices in the script layer and
throw `"Frame index is outside the sprite frame range"` (matching the message
`addEmptyFrame` already uses) rather than letting the native call silently
no-op or grow the frame count with an unpositioned insert. Tested in
`tests/scripts/move_copy_frame.js`: bounds-check throws for both methods, a
real reorder/duplicate that a naive frame-count check wouldn't catch (the
fixture's only real cel is tracked through the move and the copy by pixel
content, since `data/splash.ase` has no background layer and non-background
layers don't get an auto-created cel on new frames), and save/reopen
persistence. Full existing suite (`document_api_p1.js`, `document_api.js`,
`frame_tags.js`, `png_layers_repro.js`) re-run clean, no regressions.
`SCRIPTING.local.md` updated with both signatures.

**Status 2026-09-18 (L6 batch 1, Claude)**: implemented the two items Codex's
C7 report (below) named as actual blockers for animation assembly, ahead of
the rest of the P2 list — frame timing (`sprite.setFrameDuration()`,
`sprite.setFrameRangeDuration()`, plus a `sprite.frameDuration()` read
added for symmetry) and cel content transfer (`layer.addCel()`,
`layer.clearCel()`, `layer.copyCel()`), so a pipeline that renders each
animation frame as a separate image can place that pixel data into an
independent cel on a specific layer/frame. `addCel()` creates a blank image
sized to the sprite (matching pixel format) and hands back the `Cel` so the
caller paints it via the existing `image.putPixel()`/`putImageData()`.
Frame-tag bindings turned out to already be complete from earlier work
(`addTag`/`removeTag`/`fromFrame`/`toFrame`/`setFrameRange`/`name`/`color`/
`aniDir`), so nothing further was needed there. Same branch
(`codex-headless-api-p1`), still local-only. Tested in
`tests/scripts/frame_duration.js` and `tests/scripts/cel_transfer.js`:
bounds-check throws, real mutation, save/reopen persistence. Full existing
suite re-run clean. `SCRIPTING.local.md` updated. Remaining P2 items
(`setPixelFormat`, `trimSprite`, `setSpriteTransparentColor`,
`newLayerFolder`, `restackLayerAfter`/`Before`, `flattenLayers`,
`duplicateLayerAfter`/`Before`, `moveCel`/`swapCel`, `flipImage`) are
authoring conveniences per Codex's own report, not static-batch blockers —
left for a later batch unless something changes their priority.

Prioritization from this matrix:

- **P1 (fix first — same shape as bindings that already work safely)**: fix
  `sprite.crop()` to actually call `cropSprite()` (it's a silent landmine right
  now, worse than an error); add `removeFrame` and `removeLayer` as the natural
  complements to the existing `addFrame`/`addEmptyFrame`/`newLayer`; add
  `setCelOpacity` next to the existing `setPosition`; add `moveFrame`/`copyFrame`
  for frame reordering (useful for any animation-editing pipeline, not MCP-specific).
- **P2 (more design, still native-safe)**: `setPixelFormat`,
  `setSpriteTransparentColor`, `trimSprite`, `newLayerFolder`,
  `restackLayerAfter`/`Before`, `flattenLayers`, `duplicateLayerAfter`/`Before`,
  `addCel`/`clearCel`/`moveCel`/`copyCel`/`swapCel`, `flipImage`.
- **P3 (deferred / blocked)**: anything palette-related beyond the existing
  `loadPalette()` workaround — blocked on the unresolved native crash in
  `sprite.palette` (investigated 2026-09-18, root cause not pinned down within
  the agreed time box; see [[Design-Notes/LibreSprite-Scripting-API]]). Mask API
  (`copyToCurrentMask`, `setMaskPosition`) — low priority, no known consumer yet.

### 3. Stabilize the data-safety edges

Palette access remains a separate native safety issue: reading
`doc.sprite.palette` caused an access violation in the tested Windows binary.
Before adding palette MCP tools, identify a safe native path that works across
fresh processes and indexed/RGB documents. A workaround that only works after
`loadPalette()` in the same process is not enough for the current architecture.

Bindings should also standardize:

- bounds checking and predictable error messages;
- explicit frame/layer identifiers instead of hidden active-document state;
- transaction lifetime and save behavior;
- version/feature detection so the MCP layer can explain when a released
  binary lacks a newer binding.

### 4. Keep the MCP layer thin and optional

The MCP server remains an external experiment and compatibility layer. It should
call stable headless bindings, report unsupported capabilities clearly, and not
define what LibreSprite's public API must become.

An in-process LibreSprite script could be a future direction, but it should only
be evaluated after the headless object model is useful on its own and after the
LibreSprite project has expressed interest in that integration. We should not
assume that a working MCP prototype is automatically wanted upstream.

## Prioritized backlog

| Priority | Area | Direction | Gate |
| --- | --- | --- | --- |
| P0 | Regression harness | Keep one headless script and save/reopen test per binding | Local source build and CI-compatible binary |
| P0 | Frame tags | Preserve the fork implementation and test coverage | Upstream review plus tagged release |
| P0 | Layer/frame creation | Preserve the `DocumentApi` implementation and test coverage | Upstream review plus tagged release |
| P1 | Frame/cel operations | Expose the smallest useful existing `DocumentApi` methods | Native behavior confirmed headlessly |
| P1 | Layer operations | Add folder, duplicate, remove, and restack bindings incrementally | Persistence and ownership tests |
| P1 | Error contract | Normalize bounds, missing-cel, and unsupported-feature errors | Cross-version smoke tests |
| P2 | Palette safety | Find a native safe path before adding tools | Crash-free fresh-process tests |
| P2 | Export metadata | Evaluate frame-tag-aware export and sprite-sheet support | API exists in released binary |
| P3 | Persistent session | Revisit only after API correctness; current `--shell` spike failed | Stable upstream transport |

## Explicit non-goals

- Do not pick up issue #10 unless a required operation has no reasonable
  `DocumentApi`/`Transaction` equivalent. It remains the deferred fallback.
- Do not un-stub frame-tag or layer/frame MCP tools before the bindings exist in
  a tagged LibreSprite release consumed by CI.
- Do not open new upstream feature PRs during the release freeze unless the
  maintainers invite the work or it is an urgent bug fix.
- Do not describe the MCP server as an official LibreSprite feature.

## Proposed workflow after the release

1. Re-read the final LibreSprite contribution and AI policy.
2. Open or update a focused issue describing one headless API gap and its
   persistence test, before preparing a PR.
3. Implement and review the smallest `DocumentApi`/`Transaction` binding in the
   public fork.
4. Build on Windows and at least one non-Windows target where practical.
5. If maintainers are interested, submit a focused upstream contribution that
   follows the project policy and clearly discloses AI assistance where required.
6. After a tagged release contains the binding, add the corresponding MCP tool
   and integration test in this repository.
