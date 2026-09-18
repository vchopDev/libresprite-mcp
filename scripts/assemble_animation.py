"""Assemble a rendered PNG sequence into a verified multi-frame .ase file."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from uuid import uuid4

from libresprite_mcp.client import LibreSpriteClient


def _js_string(value: str) -> str:
    return json.dumps(value)


def parse_durations(value: str | None, count: int, default: int) -> list[int]:
    """Parse either one duration or a comma-separated per-frame sequence."""
    if not 1 <= default <= 65535:
        raise ValueError("default duration must be between 1 and 65535 milliseconds")
    if value is None:
        return [default] * count

    try:
        durations = [int(item.strip()) for item in value.split(",")]
    except ValueError as exc:
        raise ValueError("durations must be comma-separated integers") from exc
    if len(durations) != count:
        raise ValueError(f"expected {count} durations, got {len(durations)}")
    if any(not 1 <= duration <= 65535 for duration in durations):
        raise ValueError("every duration must be between 1 and 65535 milliseconds")
    return durations


def _alpha_token(value: int) -> str:
    """Return a letters-only token so LibreSprite cannot infer a frame suffix."""
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    token = ""
    while True:
        token = alphabet[value % 26] + token
        value = value // 26 - 1
        if value < 0:
            return token


def build_script(
    frame_paths: list[Path],
    output_path: Path,
    durations: list[int],
    layer_name: str,
    tag_name: str | None,
) -> str:
    """Build one open/mutate/save/reopen script for the client subprocess."""
    frame_literals = ",".join(_js_string(str(path.resolve())) for path in frame_paths)
    duration_literals = ",".join(str(duration) for duration in durations)
    tag_code = ""
    if tag_name:
        tag_code = (
            f"var tag=targetSprite.addTag(0,{len(frame_paths) - 1});"
            f"tag.name={_js_string(tag_name)};"
        )

    return f"""
    var framePaths=[{frame_literals}];
    var durations=[{duration_literals}];
    var sourceDataList=[];
    var sourceMarkers=[];
    var sourceWidth=0;
    var sourceHeight=0;
    var sourceColorMode=0;
    for(var sourceIndex=0;sourceIndex<framePaths.length;sourceIndex++){{
        var sourceDoc=app.open(framePaths[sourceIndex]);
        if(!sourceDoc) throw new Error("could not open animation source frame");
        var sourceSprite=sourceDoc.sprite;
        var sourceCel=sourceSprite.layer(0).cel(0);
        if(!sourceCel) throw new Error("animation source frame has no layer 0 cel");
        if(sourceIndex===0){{
            sourceWidth=sourceSprite.width;
            sourceHeight=sourceSprite.height;
            sourceColorMode=sourceSprite.colorMode;
        }} else if(sourceSprite.width!==sourceWidth ||
                  sourceSprite.height!==sourceHeight ||
                  sourceSprite.colorMode!==sourceColorMode){{
            throw new Error("all animation frames must have matching dimensions and color mode");
        }}
        var sourceData=sourceCel.image.getImageData();
        var sourceMarker=[];
        for(var sourceMarkerIndex=0;
            sourceMarkerIndex<sourceData.length && sourceMarkerIndex<8;
            sourceMarkerIndex++)
            sourceMarker.push(sourceData[sourceMarkerIndex]);
        sourceDataList.push(sourceData);
        sourceMarkers.push(sourceMarker);
    }}
    var targetDoc=app.open(framePaths[0]);
    if(!targetDoc) throw new Error("could not reopen first animation frame as target");
    var targetSprite=targetDoc.sprite;
    while(targetSprite.frameCount>1)
        targetSprite.removeFrame(targetSprite.frameCount-1);
    if(targetSprite.width!==sourceWidth ||
       targetSprite.height!==sourceHeight ||
       targetSprite.colorMode!==sourceColorMode)
        throw new Error("target animation sprite does not match source frames");
    var targetLayer=targetSprite.newLayer({_js_string(layer_name)});
    var originalLayer=targetSprite.layer(0);
    targetSprite.removeLayer(originalLayer);
    targetLayer=targetSprite.layer(0);
    for(var addIndex=1;addIndex<framePaths.length;addIndex++)
        targetSprite.addEmptyFrame(addIndex);
    if(targetSprite.frameCount!==framePaths.length)
        throw new Error("animation frame count setup failed");
    for(var frameIndex=0;frameIndex<framePaths.length;frameIndex++){{
        var targetCel=targetLayer.addCel(frameIndex);
        targetCel.image.putImageData(sourceDataList[frameIndex]);
        targetSprite.setFrameDuration(frameIndex,durations[frameIndex]);
    }}
    {tag_code}
    targetSprite.saveAs({_js_string(str(output_path.resolve()))},true);
    var reopened=app.open({_js_string(str(output_path.resolve()))});
    if(!reopened) throw new Error("saved animation could not be reopened");
    if(reopened.sprite.frameCount!==framePaths.length)
        throw new Error("reopened animation has the wrong frame count");
    var checkLayer=reopened.sprite.layer(0);
    for(var checkIndex=0;checkIndex<framePaths.length;checkIndex++){{
        var checkCel=checkLayer.cel(checkIndex);
        if(!checkCel) throw new Error("reopened animation is missing a frame cel");
        if(reopened.sprite.frameDuration(checkIndex)!==durations[checkIndex])
            throw new Error("reopened animation has the wrong frame duration");
        var checkData=checkCel.image.getImageData();
        for(var checkMarker=0;checkMarker<sourceMarkers[checkIndex].length;checkMarker++)
            if(checkData[checkMarker]!==sourceMarkers[checkIndex][checkMarker])
                throw new Error("reopened animation frame pixels do not match");
    }}
    console.log("animation_assembly_verified="+framePaths.length);
    """


def assemble_animation(
    client: LibreSpriteClient,
    frame_paths: list[Path],
    output_path: Path,
    durations: list[int],
    layer_name: str = "animation",
    tag_name: str | None = None,
) -> Path:
    """Assemble and verify a PNG sequence, returning the output path."""
    if not frame_paths:
        raise ValueError("at least one animation frame is required")
    if len(durations) != len(frame_paths):
        raise ValueError("one duration is required for every animation frame")
    if output_path.suffix.lower() != ".ase":
        raise ValueError("animation output must use the .ase extension")
    if not output_path.parent.is_dir():
        raise ValueError(f"animation output directory does not exist: {output_path.parent}")
    for path in frame_paths:
        if not path.is_file():
            raise ValueError(f"animation frame does not exist: {path}")
    if any(path.resolve() == output_path.resolve() for path in frame_paths):
        raise ValueError("animation output cannot overwrite an input frame")

    staged_paths = []
    staged_files = []
    try:
        for index, path in enumerate(frame_paths):
            staged_path = output_path.parent / (
                f".animation-source-{uuid4().hex}-frame-{_alpha_token(index)}.png"
            )
            shutil.copy2(path, staged_path)
            staged_paths.append(staged_path)
            staged_files.append(staged_path)
        client.run_script(build_script(staged_paths, output_path, durations, layer_name, tag_name))
    finally:
        for staged_file in staged_files:
            staged_file.unlink(missing_ok=True)
    if not output_path.is_file():
        raise RuntimeError(f"LibreSprite did not create the animation output: {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="Output multi-frame .ase path")
    parser.add_argument("--duration-ms", type=int, default=100, help="Default frame duration")
    parser.add_argument(
        "--durations-ms",
        help="Optional comma-separated duration for every frame, in input order",
    )
    parser.add_argument("--layer-name", default="animation")
    parser.add_argument("--tag", dest="tag_name", help="Optional frame-tag name")
    parser.add_argument("frames", nargs="+", type=Path, help="Input PNG frames in playback order")
    args = parser.parse_args()

    try:
        durations = parse_durations(args.durations_ms, len(args.frames), args.duration_ms)
        result = assemble_animation(
            LibreSpriteClient(),
            args.frames,
            args.output,
            durations,
            layer_name=args.layer_name,
            tag_name=args.tag_name,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(f"animation_assembly_verified={len(args.frames)} output={result}")


if __name__ == "__main__":
    main()
