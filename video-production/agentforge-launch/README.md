# AgentForge launch film

A 45-second launch film built with Remotion, React, TypeScript, and procedural Three.js geometry. The concept is **Built for the failure path**: a worker interruption, durable checkpoints, the execution architecture, an inspectable repair, and the AgentForge closing identity.

## Source and assets

- [Finished film](../../assets/media/Project_Launch_Cinematic.mp4): the curated H.264/AAC export, 1920 × 1080, 30 fps, 1,350 frames.
- `src/`: composition, five scenes, kinetic typography, masks, camera, geometry, and audio integration.
- `creative/`: approved narration, fitted subtitles and phrase cues, and the final storyboard.
- `public/fonts/`: locally bundled Space Grotesk, Inter, and IBM Plex Mono.
- `public/audio/`: narration, original score/effects, and the mastered soundtrack.
- `public/reference/`: the dashboard capture and real Docker fixture evidence used in the film.
- `licenses/`: bundled asset licenses and provenance.
- `scripts/`: rendering, optional asset regeneration, export checks, and source packaging.

`out/`, `work/`, installed dependencies, and downloaded tools are local-only and ignored by Git. Exported frames, contact sheets, measurements, and source ZIPs belong in `out/`; speech fragments and intermediate mixes belong in `work/`. Do not add those directories to Git.

## Render

Use Node.js 22+ and npm. From this directory:

```sh
npm ci
npm run typecheck
npm run render
```

The render writes `out/Project_Launch_Cinematic.mp4`. It downloads Chrome Headless Shell on first use; fonts, audio, and reference assets are bundled. No AgentForge credentials, running application stack, or model API are needed. Dependency versions are locked in `package-lock.json`.

```sh
npm run studio
npm run stills
node scripts/render.mjs --stills --frames=30,300,574,915,1240
```

`AgentForgeLaunch` has half-open scene intervals `[0,210)`, `[210,450)`, `[450,780)`, `[780,1110)`, and `[1110,1350)`. Animation uses deterministic frame state, Remotion interpolation/easing, and selected springs. HTML typography remains selectable. There are no browser animation timelines or wall-clock visual state.

The supplied renderer is tested on Windows with Node 24. It uses software WebGL (`swangle`), one worker, two encoder threads, H.264 CRF 17, and AAC 320 kbps. Nine contiguous 150-frame silent sections release browser memory between renders; video streams join without re-encoding, and the mastered soundtrack is muxed once. The 1440 × 810 antialiased WebGL pass sits beneath full-resolution HTML/SVG typography. This arrangement accommodates the tested machine's hardware WebGL and memory constraints.

For other platforms, adapt the FFmpeg executable paths in `scripts/render.mjs` and the Python tools. The composition itself uses portable browser assets. Publishing a changed film is deliberate: inspect the export, then replace `assets/media/Project_Launch_Cinematic.mp4` and its poster from the repository root.

## Optional asset preparation

Rendering uses the included assets directly. Regenerating narration requires Windows, the installed Microsoft David Desktop voice, and Python dependencies in `scripts/requirements.txt`. Set `$launchPython` to the intended Python executable:

```powershell
& $launchPython -m pip install -r scripts/requirements.txt
& ./scripts/prepare-assets.ps1
& $launchPython scripts/produce_audio.py
```

Speech comes from `creative/storyboard.json`, with pronunciation aliases for AgentForge and PostgreSQL. Bundled fonts are preserved unless `-RefreshFonts` is passed. NumPy synthesizes the original score and effects using a fixed seed. No third-party music recording or sample pack is used.

`scripts/capture_fixture.py` optionally reproduces the included fixture evidence using the repository's Python environment, Docker, and `agentforge-tool:local`. It invokes the real Docker executor for failing tests, a source write, and unchanged passing tests in disposable containers.

## Export inspection and packaging

```powershell
& $launchPython scripts/prepare-qa-tools.py
& $launchPython scripts/verify_export.py
& $launchPython scripts/verify-seams.py
& $launchPython scripts/package_source.py
```

Checks inspect `out/Project_Launch_Cinematic.mp4` when present, otherwise the curated film. They check dimensions, frames, codecs, decoding, black frames, audio peaks, and correlation with the master; they extract representative and consecutive boundary frames into `out/`. Review those frames and listen to the exported soundtrack before publishing. Source packaging runs from a Git checkout and respects its ignore rules, excluding renders, working files, private configuration, downloaded tools, and dependencies.

## Motion and limitations

The film combines clipped line/word reveals, staggered characters, stable-container tracking, fragmented typography, perspective depth, foreground occlusion, traced SVG paths, data pulses, checkpoint-layer assembly, camera push/orbit/pullback, directional shape transitions, and synchronized synthesized Foley. Moving stencil and SVG masks keep grid/network lines off the opening object's face and aperture. The closing CTA is text only, with no URL or bottom duration indicator.

Architecture labels represent the implemented PostgreSQL queue/state store, fenced leases, atomic checkpoints, provider routing, and private Docker gateway. The repair sequence uses a genuine dashboard capture and actual bundled-fixture test evidence. The demo is labelled scripted, recovery is time-condensed after lease expiry, and no benchmark or exactly-once external execution claim is introduced.

Narration uses a synthetic system voice. Software WebGL has reduced internal resolution. Automated export checks were completed during production; manual audio listening was not available in the production environment. Human audition remains necessary before a new publication.

Space Grotesk, Inter, and IBM Plex Mono retain SIL OFL 1.1 licenses. The dashboard identity includes a Lucide-derived mark under ISC. See [asset provenance](licenses/ASSET_PROVENANCE.md) for complete attribution; software dependencies retain their upstream license terms.
