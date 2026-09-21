# DLSS 5 Neural Rendering on an RTX 3070: a measured field report (BioShock Remastered)

*September 2026 (last updated 2026-09-19). One RTX 3070, one 2016 game, about two days of testing, and a lot of
frame-time captures.*

DLSS 5 "3D-guided" Neural Rendering (NR, NGX feature 18) is officially an RTX 40/50 feature. A community
stack gets it running on Ampere. This post documents what it took to run it on an **RTX 3070 8 GB** in
**BioShock Remastered**, a 32-bit D3D11 game with no DLSS support at all. It covers what NR actually
costs per frame, how small the NR pass can be before you can see the difference, and which ideas
(frame generation, "render at 2K and use DLSS to reach 4K") do not work for this kind of game.

Every number here comes from logs or Intel PresentMon captures on this machine. Estimates are labelled
as estimates.

> **Disclaimer.** Everything here is a community mod stack on top of an unofficial, Ampere-patched NR
> runtime. Nothing in this repository redistributes NVIDIA or third-party binaries. There are only
> links. Use it in single-player games only: proxy DLLs and injected ReShade can trip anti-cheat.

**Contents:** [TL;DR](#tldr) · [1. Hardware](#1-hardware-and-software) · [2. The stack](#2-the-stack-and-why-it-looks-like-this) ·
[3. Frame cost](#3-what-a-frame-costs) · [4. Image quality](#4-image-quality) ·
[5. Every-other-frame NR](#5-every-other-frame-nr-is-not-frame-generation) · [6. What doesn't work](#6-things-that-dont-work-and-why) ·
[7. Frame generation](#7-frame-generation-on-an-rtx-3070) · [8. Operational lessons](#8-operational-lessons) ·
[9. Budgeting a new game](#9-budgeting-a-new-game-the-nr-tax) · [10. What's next](#10-whats-next-games-with-native-dlss) ·
[11. Open questions](#11-open-questions) ·
[12. Second game: Expedition 33](#12-second-game-clair-obscur-expedition-33-the-native-dlss-route-and-real-frame-generation) · [Appendix: final config](#appendix-the-final-configuration)

---

## TL;DR

| Configuration (every-frame NR, NR at 960×540 via the Cost Scaler) | Avg fps | 1% low | Frame-time stdev |
|---|---:|---:|---:|
| 4K output, 4K DLAA | 44.2 | 38.8 | 1.50 ms |
| 4K output, every-other-frame NR | 60.6 | 40.2 | **6.51 ms** (a 10/23 ms sawtooth) |
| 2560×1440 output, 1440p DLAA | 57.0 | 53.2 | 0.47 ms |
| 2560×1440 output, mild GPU overclock, game capped at 60* | **60.0** | 55.4 | 0.66 ms |

- **NR is the whole cost.** At 1440p it takes about 12–13 of the 17.5 ms frame. The game plus ReShade
  take about 2.7 ms.
- **The NR pass can be tiny.** With the Cost Scaler's matched-residual resolve, NR at 540p (and at 2K
  even 360p) looks essentially identical to NR at full resolution in 1:1 crops.
- **Resolution still beats NR for sharpness.** Native 4K is visibly sharper than 2K with or without NR.
  NR changes the lighting and materials, not the resolved detail.
- **Frame generation:** there's no in-pipeline FG for a 32-bit D3D11 game on a 3070; only Lossless
  Scaling works. In native-DLSS DX12 games, `dlssg_for_sm86` can unlock DLSS-G on Ampere
  ([section 7](#7-frame-generation-on-an-rtx-3070)).
- **"2K → DLSS SR → 4K" needs native DLSS in the game.** For BioShock it's impossible.
- **NR is a fixed tax per frame** (~8.5 ms at 2K/360p, ~12 ms at 2K/540p, ~13.4 ms at 4K/540p). To hold
  60 fps with NR at 2K, a game needs ~120 fps at 1440p with DLSS Quality and NR off ([section 9](#9-budgeting-a-new-game-the-nr-tax)).
- **A second game (Clair Obscur: Expedition 33) confirmed the method and finally measured FG**: NR on top
  of the game's own DLSS worked first try (10.0 ms tax), and the Ampere DLSS-G unlock gave ~97 displayed /
  ~49 real fps ([section 12](#12-second-game-clair-obscur-expedition-33-the-native-dlss-route-and-real-frame-generation)).
- **Recommended daily setting for BioShock on this card:** 2K output, 1440p DLAA, every-frame NR at 540p
  (or 360p for more headroom; it looks the same). See the [appendix](#appendix-the-final-configuration).

\* The 60 cap came from the game itself: in-game V-Sync plus `DesiredRefreshRate=60` in `Bioshock.ini` puts a 120 Hz panel into 60 Hz fullscreen. Raising it to 120 removes the cap.

![Frame-time comparison](images/frametime.svg)

---

## 1. Hardware and software

| | |
|---|---|
| GPU | RTX 3070 8 GB (Ampere, SM86) |
| Display | 4K, **120 Hz**, G-Sync |
| OS / driver | Windows 10 22H2, **NVIDIA 616.56** |
| Game | BioShock Remastered (Epic), `BioshockHD.exe`, **32-bit**, D3D11, no DLSS/FSR/XeSS |

**Why driver 616.56 and not the newest.** DLSS5-Feeder documents 616.56 as its minimum, and its issue #54
reports NR evaluation crashing inside NGX with RenoDX 4.6/4.7 on **616.64 and newer**. 616.56 was the
most defensible first test. The previous driver's installer was kept for rollback.

## 2. The stack, and why it looks like this

The game has no DLSS, and NVIDIA ships no 32-bit NGX runtime. So the DLSS call has to be
*manufactured* outside the game, in a 64-bit helper process:

```
BioshockHD.exe (32-bit D3D11, renders the finished frame)
 └─ ReShade 6.8.0 x86 ── LumeniteFX motion vectors + depth
     └─ DLSS5-Feeder 1.16.0-beta.4 (dlss5-feed.addon32) ── ships color/depth/MV to →
         host64\dlss5-feed-host64.exe (D3D12) + ReShade x64
           └─ NVIDIA DLSS 310.9.1 in DLAA mode (1:1, e.g. 1440p → 1440p)
               └─ RenoDX DLSS5 Generic 5.2.1 intercepts that evaluate → runs NR (feature 18)
                   └─ DLSSNR-Cost-Scaler 1.0.6 (proxy nvngx_dlssnr.dll)
                       ├─ downsample to the NR work size (e.g. 960×540)
                       ├─ real NR runtime 310.8.SF-v2 (Ampere-patched)
                       └─ "matched residual" resolve: native frame + upscaled NR delta, RCAS 0.2
         ← result copied back to the game (one frame late, async_home=1) → Present
```

Links to every component are in [`skill/dlss5-nr-rtx30/references/components.md`](skill/dlss5-nr-rtx30/references/components.md).

**Proving it works.** An FPS drop proves nothing. NR was only counted as running when the consumer's
log showed `inline feature 18 evaluation succeeded (count=…)` with a rising count, and the proxy log
showed `Allocated slot … work=960x540, native=2560x1440`. A standalone `host64 --test` run passed
(feature 18 created, evaluations counting) before anything touched the game folder.

### How it got here, in order

| Step | What happened | Result |
|---|---|---|
| Driver | NVIDIA App offered 616.92; **616.56** was installed instead (see §1). The installer's PhysX sub-package "failed" because a newer PhysX was already present. That's harmless | 616.56 confirmed after reboot |
| Standalone test | `host64 --test`, 640×360, 300 frames, before touching the game | feature 18 created and evaluating, **11.09 ms/frame** of DLAA+NR even at 640×360 |
| First in-game run | 4K output, NR at full 4K | **8–13 fps**, GPU 100% |
| Feeder `work_resolution=50` | DLAA+NR on a 1080p copy, then bilinearly stretched back to 4K | ~26 fps. Changing this value **while the game ran crashed the helper**, so the game had to be restarted |
| + FSR 1 expand-back (`work_upscale=1`) | sharper stretch | clearer image, **same speed** (26 fps, helper 32.2 ms) |
| Transport-only (`mode=1`) | frames go to the helper and back, with no NGX | 158 fps, copy **0.02 ms**, so the transfer isn't the bottleneck |
| DLAA only (NR off) | same 1080p work size | 143 fps, **1.1 ms**, so DLAA isn't the bottleneck either |
| RenoDX 4.70 → 5.2.1 | newer NR consumer | 26 → 26.6 fps, **no speed change** |
| Cost Scaler 1.0.6 | NR shrunk *inside* the NR call (1286×724), with the native frame kept as the anchor | **39.6 fps**, helper 19.0 ms |
| Tuning | Feeder back to 100%, NR size swept, output 4K vs 2K, every-other-frame on and off | the tables below |

Two log lines here are misleading. The helper's NGX capability query reports feature 18 as
`NotImplemented (0xBAD00012)`, and after start-up it prints `consumer did not intercept (ReShade.log
is unavailable)`. NR works anyway. Only the consumer's own `feature 18 evaluation succeeded` lines
count as evidence.

### What the NR runtime itself can and can't do

The Feeder's hard floor is `work_resolution=50`, so why is a separate Cost Scaler needed at all?
Probing the 310.8 NR runtime directly (72 create/evaluate combinations of hint preset × style × NGX
quality mode at 320×180 → 640×360) showed:

- **NR never upscales.** Every case wrote only an input-sized image (the upper-left quarter of a 2×
  output). Its internal `ScalingRatio` is accepted but changes nothing. So NR is an image
  transformation at the input resolution, and resolution reconstruction still needs DLSS SR or an
  external resolve like the Cost Scaler's.
- **The render preset (1–3) doesn't change the output.** The checksum was identical, and a separate
  community test found the same. It's not a quality or speed knob.
- **Style does change it.** Styles 0/1/2 produce three different results (3 is the same as 2), so
  Style is what selects the three NR "looks".


## 3. What a frame costs

Measured at 2560×1440 output, 1440p DLAA, NR 540p every frame (PresentMon plus the helper log):

```
17.5 ms per frame, GPU-bound, 100% utilisation
├─ game process GPU (BioShock + ReShade effects + frame copy) ... 2.7 ms
└─ helper GPU (DLAA + NR)  .......................................... 14.1–14.7 ms
    ├─ DLAA 1440p ............................ ~2.0 ms (estimate: 1.10 ms measured at 1080p, scaled)
    └─ NR 540p + Cost Scaler resolve ......... ~12–12.5 ms (estimate: remainder)
Cross-process transfer: 0.02 ms (measured in transport-only mode)
Game CPU busy: ~3.2 ms per frame. The CPU is not the limit.
```

### NR size vs frame time (4K output, 4K DLAA, every frame)

| NR size | Frame time | fps |
|---|---:|---:|
| NR off (DLAA only) | 9.2 ms | 109 |
| 960×540 | 24.8 ms | 40.4 |
| 1286×724 | 30.3 ms | 33.0 |
| 1706×960 | 37.3 ms | 26.8 |
| 1920×1080 | 44.2 ms | 22.6 |
| 2560×1440 | 63.9 ms | 15.6 |
| 3840×2160 (proxy off) | ~80 ms | 12.5 |

A linear fit is a good predictor: **frame time ≈ 18.4 ms + 12.3 ms per NR megapixel**. That base
includes about 9.2 ms of game + DLAA at 4K. Even a 640×360 NR pass took about 11 ms in the standalone
test, so on Ampere NR has a large fixed cost. That fixed cost is why 4K + NR tops out in the 40s on
this card no matter how small the NR pass is.

### NR size vs fps (2K output, every frame, mild overclock, game capped at 60)

| NR size | 360p | 540p | 720p | 960p | 1080p | 1440p (passthrough) |
|---|---:|---:|---:|---:|---:|---:|
| fps | 60 (cap) | 60 (cap) | 48 | 35.5 | 30 | 18.7 |
| helper GPU | ~10.5 ms | ~14 ms | | | | |


### What did and didn't change speed

| Change | Effect on frame time |
|---|---|
| NR size (the Cost Scaler's `ResolutionScale`) | **large**, about 12 ms per NR megapixel at 4K |
| Output resolution 4K → 2K | **large**, 44 → 57 fps at NR 540p |
| Every-other-frame NR | the average rises, but the slow frames and 1% lows don't change |
| Mild overclock (~1980 → ~2025 MHz under load, memory +723) | small but real: 57 → 60+ at 2K, helper 14.7 → 14.1 ms |
| Feeder FSR 1 vs bilinear expand-back | none (image only) |
| RenoDX 4.70 vs 5.2.1 | none |
| NR render preset | none (and no image change either) |
| Cost Scaler downsample + resolve | too small to separate from noise (sub-millisecond by the fit) |
| Cross-process transfer | 0.02 ms |
| Game settings (the game process totals ~2.7 ms at 2K) | at most a few fps |

### Power, clocks and VRAM

| Configuration | VRAM used (whole GPU) | Clock / power / temperature |
|---|---|---|
| 4K output, NR on a 1080p work copy | 3.4–4.4 GiB | 100% utilisation |
| 4K output, Feeder 100%, NR 1706×960 | ~6.3 GB | 1980 MHz, 232 W |
| 2K output, NR 540p, mild overclock | – | 2025 MHz, ~210 W, 67–69 °C |

8 GB is enough for NR alone. Frame generation on top would be tight (§7).

## 4. Image quality

All comparisons are 1:1 pixel crops. The camera was held still and NR sizes were switched **live**:
the Cost Scaler re-reads its ini on every change, so every image in a sweep has identical framing.

**Picking a test scene.** The fire-and-water opener is a bad test: flames, water and fog change
every frame, and lamp flicker comes and goes on its own. Good scenes are static, well lit and full
of *materials* (metal, stone, brick, fabric, faces). Save there, hold the mouse still, and switch
settings live when you can, so that every shot has the same framing. Reloading a save moves the
camera by a few pixels, and the first-person weapon sways, so leave it out of the crops or switch
to a small weapon. Security panels and neon signs animate on their own, so don't read their
differences as NR.


### NR on vs off

In the lighthouse hall, NR is not subtle. Glossy gold becomes patinated bronze, stone and brick gain
grime and grain, and coloured bloom and emissive glow get damped. The one constant: NR at 540p and NR
at 1440p look the same.

*4K + 4K DLAA: NR off / NR 540p / NR 1440p*
![NR on/off, statue](images/nr-on-off-statue-4k.jpg)

*Same camera, pixel-aligned: native 4K vs 4K + NR 960p*
![NR on/off, same camera](images/nr-on-off-hall-statue-alt.jpg)

In fog-heavy underwater scenes the effect shrinks to slightly tighter bloom and a little more contrast.
How much NR changes depends on how much *material* the scene has.

### Lights and faces, zoomed in

Each strip shows NR off, NR on, and the absolute difference amplified ×5 (black means unchanged).
The lighthouse pairs were captured in one session with the camera untouched: DLSS 5 was switched
off live. "Off" there is native 4K without DLAA, so the difference map also contains DLAA's
edge anti-aliasing. The Medical Pavilion pairs compare DLAA with DLAA + NR at 2K, so NR is the only
variable.

**Faces.** The statue's face changes the most. Polished gold turns into darker, pitted bronze with
harder specular highlights, and the whole surface lights up in the difference map. A human face in a
dim scene barely moves: some skin shading and wrinkle contrast, mostly at edges.

![Statue face, NR off / on / difference](images/lf-face-statue.jpg)
![Character face, NR off / on / difference](images/lf-face-splicer.jpg)

**Lights.** NR re-renders emissive fixtures as hotter, whiter sources. Warm-yellow and green-tinted
glass goes close to neutral white, and the soft glow halo around the fixture shrinks. In the
difference maps the lamp bodies and their halos are the brightest areas.

![Hall lantern, NR off / on / difference](images/lf-light-hall-lamp.jpg)
![Door lamp, NR off / on / difference](images/lf-light-hall-door-lamp.jpg)
![Wall lamp at 2K, NR off / on / difference](images/lf-light-wall-lamp.jpg)

### How small can the NR pass be?

At 4K output (540p / 724p / 1080p / 1440p NR):

![NR size sweep, 4K](images/nr-size-sweep-4k-statue.jpg)
![NR size sweep, 4K, panel](images/nr-size-sweep-4k-panel.jpg)

At 2K output (360p through 1440p NR; each label has that setting's fps):

![NR size sweep, 2K](images/nr-size-sweep-2k-pillar.jpg)
![NR size sweep, 2K, character](images/nr-size-sweep-2k-body.jpg)

The Cost Scaler keeps the *native* frame as the anchor and only transfers the NR delta. Geometry,
edges and texture come from the full-resolution image, and the NR delta is mostly low-frequency
lighting and material information. **540p at 4K, and 360p at 2K, are the sweet spots on this card.**

### Resolution vs NR

4K native, 2K native, 2K DLAA-only and 2K + NR, all shown at 4K pixel scale:

![Resolution vs NR](images/resolution-vs-nr-pillar.jpg)

Native 4K is the sharpest by a clear margin, and 2K with or without NR is equally soft. So on a 3070
the choice is: **4K native** (sharp, ~160 fps, no NR), **2K + NR** (~60 fps, the NR look, softer), or
**4K + NR 540p** (both, at ~44 fps).

### Every scene, every capture

Four scenes were captured. They are listed here in the order they were shot, with the conditions
for each so you can tell which comparisons are pixel-aligned. Labels are burned into the images,
and all crops are 1:1 unless stated otherwise.

#### Scene 1: the opening, the plane crash at sea (night, fire, water)

The least reliable scene. The camera moved between shots, and fire and water change every frame.
Use it for overall character, not for detail.

*4K native | 4K + NR 960p (every other frame) | 2K + NR 960p (every other frame, upscaled to 4K scale):*
![Scene 1, lantern](images/s1-3way-lantern.jpg)
![Scene 1, floating lamp and water](images/s1-3way-water.jpg)
![Scene 1, fire](images/s1-3way-fire.jpg)

At 4K output, NR 960p keeps native sharpness. The 2K shot is soft because of the resolution, not
the NR. In both NR shots the floating lamp goes dim and white and loses its golden reflection, and
the fire loses saturation and fine flame tips.

*4K native | 4K + NR at full 4K (every frame, proxy off, ~12.5 fps):*
![Scene 1, 4K NR, water](images/s1-4knr-water.jpg)
![Scene 1, 4K NR, fire](images/s1-4knr-fire.jpg)
![Scene 1, 4K NR, lantern](images/s1-4knr-lantern.jpg)

At the same resolution, the NR changes are all lighting: emissive light gets dimmer and whiter,
fire gets flatter, and sharpness stays about the same.

#### Scene 2: the lighthouse hall (statue, brass, stone)

The best scene for NR. Its images are the ones in "NR on vs off", "Lights and faces" and the 4K size
sweep above. The NR-off vs NR-960p pair was captured in one session by switching DLSS 5 off live,
so it's pixel-aligned. The 4K size sweep (540p/724p/1080p/1440p) was shot in one session with live
`ResolutionScale` changes.

#### Scene 3: Welcome to Rapture, the window corridor (underwater, fog, neon)

2K output, every-frame NR. All six NR sizes, DLAA-only and 2K native were captured in **one
session with the camera untouched**. DLAA-only was made by setting the Cost Scaler's transfer to 0,
and native by switching DLSS 5 off live. The 4K native shot came from a reload of the same save.
The held wrench sways and the water behind the glass keeps moving, so ignore those areas.

| NR size | 360p | 540p | 720p | 960p | 1080p | 1440p |
|---|---:|---:|---:|---:|---:|---:|
| fps (60 cap from the game) | 60 | 60 | 47.4 | 35.2 | 28.3 | 18.4 |

*NR size sweep:*
![Scene 3, NR sizes, neon](images/s3-sizes-neon.jpg)
![Scene 3, NR sizes, column](images/s3-sizes-column.jpg)
![Scene 3, NR sizes, floor](images/s3-sizes-floor.jpg)

*2K native (no DLAA, no NR) | DLAA only | NR 540p | NR 1440p:*
![Scene 3, on/off, neon](images/s3-onoff-neon.jpg)
![Scene 3, on/off, floor](images/s3-onoff-floor.jpg)
![Scene 3, on/off, column](images/s3-onoff-column.jpg)

*4K native | 2K + NR 540p | 2K native (both 2K shots upscaled to 4K scale):*
![Scene 3, resolution, neon](images/s3-res-neon.jpg)
![Scene 3, resolution, column](images/s3-res-column.jpg)
![Scene 3, resolution, floor](images/s3-res-floor.jpg)

Findings: this is the scene where NR does least. Fog and emissive signage leave NR little
*material* to work with, and the visible change is slightly tighter bloom around signs and a
little more contrast. The six NR sizes can't be told apart. Native 4K is clearly the sharpest,
with finer waterfall streaks, wrench knurling and sign lettering, and 2K with or without NR is
equally soft.

#### Scene 4: Medical Pavilion entrance (tiles, stone pillar, patterned floor, a body)

2K output, every-frame NR. The six NR sizes were captured in **one session with the camera
untouched**. The NR 540p, DLAA-only and 2K native shots come from a second session, and the 4K
native shot from a reload of the same save.

*NR size sweep (the fps is in each label):*
![Scene 4, NR sizes, pillar](images/nr-size-sweep-2k-pillar.jpg)
![Scene 4, NR sizes, body](images/nr-size-sweep-2k-body.jpg)
![Scene 4, NR sizes, floor](images/s4-sizes-floor.jpg)
![Scene 4, NR sizes, background](images/s4-sizes-background.jpg)

*4K native | 2K native | 2K DLAA only | 2K + NR 540p (2K shots upscaled to 4K scale):*
![Scene 4, resolution, pillar](images/resolution-vs-nr-pillar.jpg)
![Scene 4, resolution, body](images/s4-res-body.jpg)
![Scene 4, resolution, floor](images/s4-res-floor.jpg)
![Scene 4, resolution, background](images/s4-res-background.jpg)

Findings: NR brightens the highlights on the pale stone and adds a little local contrast. The body
and floor hardly change. 360p through 1440p look the same. The security panel in the background
blinks on its own (red and white dots), so that difference isn't NR. The blood glints in the 4K
native body shot come from a different moment after the reload.


## 5. "Every-other-frame NR" is not frame generation

The Cost Scaler can run NR on alternate frames (`EnableAlternatingFrames`). The average jumps from 44
to 60 fps at 4K, but PresentMon shows why that number misleads:

| | avg | 1% low | odd / even frames | stdev |
|---|---:|---:|---:|---:|
| every-other-frame | 60.6 fps | 40.2 | **10.1 / 22.9 ms** | 6.51 ms |
| every frame | 44.2 fps | 38.8 | 23.0 / 22.2 ms | 1.50 ms |

The slow frame is exactly as slow as before, and the 1% low does not move. The fast frame reuses the
previous frame's NR delta, so the NR layer effectively updates at about 30 Hz. On this 120 Hz G-Sync
panel the fast frames stay inside the VRR window, so it doesn't tear, but the 10/23 ms cadence is still
uneven. Every-frame NR at 44 fps is slower but even.

## 6. Things that don't work (and why)

**"Render at 2K, DLSS SR to 4K."** The GPU supports DLSS SR, but SR needs the *game* to render
smaller, jitter its camera and provide real motion vectors. BioShock does none of that. The Feeder's
experimental `work_upscale=2` creates an SR feature, but its target is always the game's own
backbuffer size. With the game at 4K, the game has already paid for every native pixel (the Feeder
author measured it: "saves nothing", and it shimmers). With the game at 2K, SR can only output 2K.
The real fix is a proxy swapchain, which the Feeder author has designed but not built. Today the
only way to get "2K render, 4K display" is to upscale *after* NR, outside the game (NVIDIA Image
Scaling, Magpie, Lossless Scaling).

**Frame generation in this game.** No in-pipeline FG path exists for a 32-bit D3D11 game on a 3070.
See [section 7](#7-frame-generation-on-an-rtx-3070).

**A big overclock.** NR holds the GPU at 100% continuously. An Afterburner overclock that seemed fine
produced `DXGI_ERROR_DEVICE_HUNG`, Display event 4101 and LiveKernelEvent 141 within seconds, and
the game went down with it. A milder curve (flat at ~2040 MHz from ~1068 mV, power limit 104%) has
been stable and gave the last ~3 fps to a locked 60 at 2K. The memory offset (+723) is the next thing
to verify: GDDR6 error correction can cost performance without crashing.

## 7. Frame generation on an RTX 3070

Frame generation was the next thing I wanted after NR: take a ~40 fps NR image and double it.
*(Update: this section's estimates were later checked against a real FG run in another game — see
[section 12](#12-second-game-clair-obscur-expedition-33-the-native-dlss-route-and-real-frame-generation).
The ~3 ms guess for FG's own cost held up: ~3.2 ms measured at 1440p 2X.)*
Here is what exists for Ampere, where FG has to sit relative to NR, and what it can realistically
deliver on this card. Nothing in this section was measured in BioShock, because no FG path works
there. The FG numbers below are estimates or come from the tools' own documentation.

### Where FG has to sit: after NR

```
game render → (DLSS SR) → DLSS 5 NR → UI → FG interpolates between two finished frames → display
```

FG builds an in-between frame from two finished frames, the game's motion vectors, and optical
flow. If it ran before NR, every generated frame would lack the NR look and the image would flicker
between "NR" and "no NR" frames. In a game with native DLSS the order comes for free. NR runs at the
DLSS SR evaluate, in the middle of the frame, and DLSS-G (Streamline) runs at Present, after all
post-processing. In BioShock, the NR result is copied back into the game's own backbuffer before
Present, so anything that captures the final image would also see NR.

### What exists for Ampere

| Method | On a 3070? | Requirements | Usable in BioShock (32-bit D3D11, no DLSS)? |
|---|---|---|---|
| DLSS Frame Generation / MFG (official) | ❌ RTX 40/50 only | game integrates DLSS-G | ❌ |
| [`dlssg_for_sm86`](https://github.com/sdli1995/dlssg_for_sm86) (community) | ✅ SM86 build of DLSS-G (a proxy `version.dll`) | **x64 D3D12**, and the game must already ship DLSS-G through Streamline. The author tested drivers 591.86 and 610.74 | ❌ |
| DLSS Enabler (community) | ✅ | same idea: redirects the game's own DLSS-G requests | ❌ |
| NVIDIA Smooth Motion (driver-level, any DX11/12/Vulkan game) | ❌ RTX 40/50 only, no known Ampere unlock | – | ❌ (the Feeder does support it on 40/50 cards) |
| FSR 3 FG via OptiScaler | ✅ any GPU | 64-bit game with upscaler inputs. Stock OptiScaler also hijacks the NGX calls the Feeder makes | ❌ |
| AMD AFMF | ❌ AMD GPUs only | – | ❌ |
| Lossless Scaling (LSFG) | ✅ any GPU | captures the final window (windowed or borderless). Paid | ✅ the only option |

Why the BioShock stack can't host FG: the game process is 32-bit, and every DLSS-G component is
64-bit D3D12. The 64-bit helper does have a D3D12 swapchain, but it's the helper's own hidden
window. Interpolating it would never reach the screen. The Feeder's docs also note that a live FG
test with another NR consumer produced a black screen.

### What FG could deliver here (estimates)

- **FG isn't free.** The generated frame costs GPU time, and with NR the GPU is already at 100%.
  Expect the real frame rate to drop by a few fps when FG turns on. I haven't measured this on a
  3070 yet.
- **Latency follows the real frames.** FG holds back one real frame to interpolate. A 40 fps base
  still responds like 40 fps (a bit worse) even though motion looks like ~80. Vendors recommend a
  base of at least 40–60 fps.
- **Refresh rate decides whether it's worth it.** This panel is 120 Hz G-Sync, and with Reflex and
  V-Sync, FG output is capped at about 116.

  | Real fps (NR on) | FG 2× output | Verdict on 120 Hz G-Sync |
  |---|---|---|
  | ~40 (4K + NR 540p) | ~80 | good: inside VRR, smooth motion, 40 fps latency |
  | ~57–60 (2K + NR 540p) | ~115 (capped) | near ideal |
  | ~29 | ~58 | only makes sense on a 60 Hz panel, and latency is poor |

- **VRAM.** NR at 4K already used 4–6 GB of the 3070's 8 GB. FG adds its own buffers and model, so
  watch for VRAM-pressure stutter (PresentMon spikes, not low averages).

### "Every-other-frame NR" versus real FG

| | Every-other-frame NR (section 5) | Frame generation |
|---|---|---|
| Real game frames | every frame rendered | base rate only |
| NR | every 2nd frame (the NR look updates at ~30 Hz) | on every real frame |
| Pacing | 10/23 ms sawtooth | even, if the base is even |
| Latency | real frame rate | base frame rate plus one held frame |
| Works on 3070 + BioShock | ✅ | only through Lossless Scaling |

### Test plan for the first native-DLSS DX12 game

1. Measure the baseline with DLSS SR Quality at 4K and NR off, and predict the result with the
   [NR tax](#9-budgeting-a-new-game-the-nr-tax). Then add NR 540p through the Cost Scaler and record the real
   fps (~40 needs a baseline of ~86 fps before FG).
2. Add `dlssg_for_sm86` and turn on DLSS-G. Check that the NR log keeps counting feature-18
   evaluations and that the picture isn't black.
3. Capture with PresentMon 2.x, which separates generated frames from application frames. Report the
   real fps, the displayed fps, 1% lows and frame-time stdev.
4. Look for NR consistency between real and generated frames, and for HUD artifacts, in a slow pan.

## 8. Operational lessons

- **Live changes that are safe:** the Cost Scaler's `ResolutionScale`, `EnableAlternatingFrames` and
  `TransferStrength`/`ColorStrength`/`Sharpness`. It hot-reloads its ini. A scale within 0.005 of 1.0
  switches it to passthrough (full-res NR), and switching back is also safe. Turning DLSS 5 *off*
  (`enabled=0`) live is also safe.
- **Changes that need a game restart:** turning DLSS 5 back *on* (the helper deadlocked), changing
  the Feeder's `work_resolution`, turning NR on/off in RenoDX (`NeuralUplift`), and changing the game
  resolution. Edit the ini while the game is closed, because changing resolution in the menu rebuilds
  DLSS.
- The Cost Scaler clamps `ResolutionScale` to 0.25–2.0 and rounds the NR size down to even numbers
  (so 1707 becomes 1706). At 2K the smallest NR pass is 640×360, and at 4K it's 960×540.
- The ReShade Addon installer's certificate chain wasn't trusted on this PC. Instead of adding a trust
  exception, the DLLs were extracted from the official package and their hashes checked against a
  reference. Every downloaded component was checked against its release's sha256 or Authenticode
  signature.
- After a crash the game can quietly reset itself to **1024×768 windowed**. Check the display ini
  before each launch.
- Alt-Tab recreates ReShade's runtime and briefly pauses the feed. Hold PrtScn for about half a
  second, because very short presses get lost at low frame rates.
- The helper reports NR time only every 1800 frames and the Feeder reports fps every 600, so short
  runs mix settings. Use **PresentMon** for precise numbers. It needs no admin rights for your own
  process:
  ```
  PresentMon-2.5.1-x64.exe --process_name BioshockHD.exe --output_file run.csv --timed 30 --terminate_after_timed --no_console_stats --stop_existing_session
  python scripts/frametime_report.py run.csv --svg chart.svg
  ```
- For a "DLAA-only" look without a restart, set `TransferStrength = 0`, `ColorStrength = 0` and
  `Sharpness = 0`. NR still runs at full cost, so this is for comparing images only.

## 9. Budgeting a new game: the NR tax

The SR + NR stack costs **about the same GPU time every frame, whatever the game**. DLSS SR's cost
depends on its output size, and NR's cost depends on the NR size and the output size. Neither depends
on what the game draws. SR is already included when you measure the game with DLSS on, so the part
you have to budget on top is NR. Section 3 showed this: the NR time
scales with NR megapixels, the Cost Scaler's resolve is negligible, and the cross-process transfer
is 0.02 ms. So NR works like a fixed tax on every frame, and the only question for a new game is how
much of the frame budget is left for the game itself.

```
final frame time  =  game frame time with its own DLSS SR (NR off)  +  NR tax
final fps         =  1000 / (1000 / baseline_fps + NR tax)
baseline needed   =  1000 / (1000 / target_fps - NR tax)
```

### The NR tax on this RTX 3070 (mild overclock, every-frame NR)

| Output | NR size | NR tax | Where it comes from |
|---|---|---:|---|
| 2560×1440 | 640×360 | **~8.5 ms** | helper 10.5 ms at 360p minus ~2 ms for DLAA at 1440p |
| 2560×1440 | 960×540 | **~12 ms** | helper 14.1 ms minus ~2 ms for DLAA |
| 3840×2160 | 960×540 (the Cost Scaler's minimum at 4K) | **~13.4 ms** | 22.6 ms with NR minus 9.2 ms with DLAA only |

Sanity check against BioShock: a 2K baseline of about 4.7 ms (~210 fps) plus a 12 ms tax gives
16.7 ms, which is the measured locked 60. A 4K baseline of 9.2 ms (109 fps) plus 13.4 ms gives
22.6 ms, which is the measured 44 fps. The tax was measured through the Feeder's helper process. In
a native-DLSS game the NR call and the resolve are the same work, so the tax should carry over,
minus the (tiny) cross-process copy. **Confirmed on the second game, with a caveat:** Expedition 33's tax
was **10.0 ms** at 2K/360p where BioShock's was 8.5 ms, so the prediction landed within 6% but the tax is
not a constant — re-measure it per game.

### What the game has to reach with DLSS on and NR off

Measure the game first with its own DLSS SR at Quality and NR off (the "baseline"). You need at
least:

| Output + NR preset | for **60 fps** final | for 50 | for 45 | for 40 (then FG 2× → ~80) |
|---|---:|---:|---:|---:|
| **2K + NR 360p** | **~122 fps** | ~87 | ~73 | ~61 (~74 if FG costs ~3 ms) |
| **2K + NR 540p** | **~214 fps** | ~125 | ~98 | ~77 (~100 with FG) |
| **4K + NR 540p** | **~306 fps** (not realistic) | ~152 | ~113 | ~86 (**~116 with FG**) |

The same math the other way round (final fps with NR on, for a given baseline):

| Baseline (DLSS on, NR off) | 60 | 80 | 100 | 120 | 150 | 200 |
|---|---:|---:|---:|---:|---:|---:|
| 2K + NR 360p | 40 | 48 | 54 | 59 | 66 | 74 |
| 2K + NR 540p | 35 | 41 | 45 | 49 | 54 | 59 |
| 4K + NR 540p | 33 | 39 | 43 | 46 | 50 | 54 |

Takeaways:

- **Real 60 fps at 4K with NR is out of reach on a 3070.** The tax alone is ~13.4 ms of the 16.7 ms
  budget. 4K + NR means about 40–50 real fps, with frame generation on top.
- **At 2K, NR 360p is the setting that makes 60 reachable.** The game needs ~120 fps with DLSS
  Quality at 1440p, which is 3 to 4 times what heavy modern games manage on this card.
- A light game gains little from DLSS, because the baseline is already near the tax floor. A heavy
  game gains a lot from DLSS, but its baseline is far too low. NR on a 3070 suits **older or lighter
  games that already run at 120–200+ fps.**
- **FG's own cost (~3 ms here) is a guess.** It hasn't been measured on this card with NR yet.

### Which games fit which preset (rough 3070 numbers, to be verified)

The baselines below are rough RTX 3070 figures (1440p or 4K, high preset, DLSS Quality, no ray
tracing) from typical published results, **not measurements from this PC**. Treat them as a
starting point, and measure your own baseline with PresentMon and NR off before you commit. The NR
route also needs a 64-bit game with native DLSS, and frame generation needs DX12 plus native DLSS-G.
Avoid anything with kernel anti-cheat or online play.

| Tier | Needed baseline | Examples (approx. 3070 baseline) | Expected result |
|---|---|---|---|
| **2K + NR 540p at 60** | ≥ ~200 fps at 1440p DLSS Q | Doom Eternal (~200+, Vulkan, so NR goes through the Feeder's Vulkan path, not the Cost Scaler) | ~60 |
| **2K + NR 360p at ~60** | ≥ ~120 fps at 1440p DLSS Q | Death Stranding (~120–140), Shadow of the Tomb Raider (~120–140), Horizon Zero Dawn (~110–130) | ~55–60 |
| **2K + NR 360p at 45–55** | ~75–100 fps | Red Dead Redemption 2 (~85–95), Marvel's Spider-Man Remastered (~90–110), Cyberpunk 2077 without RT (~75–85) | ~45–55 |
| **4K + NR 540p + FG** | ≥ ~86–116 fps at 4K DLSS Q, **and native DLSS-G** | Few DLSS-G games are this light on a 3070. Marvel's Spider-Man Remastered (~70–80 at 4K DLSS Q) is close | ~35–40 real, ~70–80 displayed |
| too heavy | < ~60 fps baseline | Alan Wake 2, Cyberpunk 2077 with RT, Black Myth: Wukong at high settings | < 35 real fps; FG gets a poor base |

The practical rule for this card: **if a game runs at ≥ ~120 fps at 1440p with DLSS Quality, it can
run NR at 2K and 60 fps. If it only makes 60–100, expect 40–55 fps with NR, or use FG where the game
supports DLSS-G.**

## 10. What's next: games with native DLSS

Everything that made BioShock hard disappears in a 64-bit DX12 game with native DLSS. The game renders
at 1440p, its own DLSS SR produces 4K, RenoDX DLSS5 hooks that evaluate, and the Cost Scaler keeps NR at
~540p. If the game ships DLSS-G, `dlssg_for_sm86` can unlock frame generation on Ampere. Before
installing anything, measure the game's DLSS baseline and check it against the
[NR tax table](#9-budgeting-a-new-game-the-nr-tax). For FG expectations and the test plan, see
[section 7](#7-frame-generation-on-an-rtx-3070).

The whole procedure, with the lessons above, is packaged as a Claude skill in
[`skill/dlss5-nr-rtx30/`](skill/dlss5-nr-rtx30/SKILL.md). It covers classifying the game, choosing a
route, safe install with backups, log-based verification, NR size sweeps, PresentMon measurement, and
FG caveats.


## 11. Open questions

| Question | Status |
|---|---|
| Real fps at 2K + NR now that the 60 cap is gone (`DesiredRefreshRate=120`) | not measured yet. The budget math predicts ~60–65 at 540p and ~70–75 at 360p |
| Best memory overclock (+723 vs lower) for NR throughput | not measured. Compare helper ms at +0 / +400 / +723 |
| NR tax in a native-DLSS game (no Feeder helper) | **answered**: 10.0 ms in Expedition 33 at 2K/360p vs 8.5 ms in BioShock. Same order, not identical |
| FG cost on a 3070 | **answered**: ~3.2 ms per group at 1440p 2X (Expedition 33). Whether NR *survives* DLSS-G is still untested — NR was removed there before FG went in |
| A close-up of a lit, living face (NR's skin model) | only a dead character in a dim scene so far. Try a Little Sister or a lit splicer |
| Motion artefacts of NR at 360p (shimmer or lag in pans) | static crops only so far. Needs a slow-pan comparison |

## 12. Second game: Clair Obscur: Expedition 33 (the native-DLSS route, and real frame generation)

BioShock was the hard case: 32-bit, no DLSS, everything faked from outside. Expedition 33 is the easy
one — x64 D3D12, UE5, shipping DLSS SR, Ray Reconstruction **and** DLSS-G (310.2.1, Streamline 2.7.30),
single-player, no anti-cheat. It took about five minutes to classify and the NR install worked on the
first try.

### NR on top of the game's own DLSS

Seven files next to the exe (ReShade Addon as `dxgi.dll`, `renodx-dlss5.addon64`, the Ampere NR
runtime as `nvngx_dlssnr_real.dll`, the Cost Scaler as `nvngx_dlssnr.dll` + ini + companion), nothing
overwritten. No Feeder, no helper process. The log shows the order the Feeder could only approximate:

```
NGX feature create intercepted: feature=1 (DLSS/DLAA)
feature 18 created ... after DLSS/DLAA for NR input 2560x1440 -> output 2560x1440 with guides 1485x836
[Proxy] Allocated slot 0 textures: work=640x360, native=2560x1440
```

NR runs on the **post-SR 1440p image**, with the game's own 1485×836 render as guides.

**Measured NR tax: 10.0 ms** at 2K with NR 640×360 (65.1 → 39.5 fps), against 8.5 ms for BioShock at
the same setting. The section 9 prediction (42 fps) was 6% off. So the tax is a good planning tool,
but **it is not a constant across games** — scene content moves it.

### Why NR came back out

NVIDIA's research page says DLSS 5 "is not designed for games whose visual identity depends on a
strongly stylized aesthetic", and that on illustrated or cartoon-like games it "may work against the
art direction". Expedition 33 is painterly. Between that, community complaints that DLSS 5 "ruins the
art style" in this game, and 10 ms per frame, NR was removed. Worth checking the art style *before*
installing.

### Frame generation, finally measured

`dlssg_for_sm86` 0.3.5 (two files next to the exe: a self-signed `version.dll` plus an ini) unlocks
the game's own DLSS-G on Ampere. The game's FG option stopped being greyed out, and PresentMon
`--v2_metrics` proves what is happening: every generated frame appears as an extra present with a
~0.4 ms `FrameTime` next to the ~18 ms real frame. A healthy 2X run is exactly 1:1.

- **FG's own cost here: ~3.2 ms per group at 1440p 2X** — twice the ~1.5 ms in the tool's own table.
  Section 7 guessed 3 ms, which turned out to be close.
- Extra VRAM per the tool's docs: ~540 MiB at 1440p, ~810 MiB at 4K.
- Latency: displayed latency measured 25.8 ms with FG on.

### Six configurations measured (FG 2X everywhere, 2K = 2560×1440 @ 120 Hz)

| Output | DLSS | Preset | Displayed fps | Real fps | 1% low | Frame-time stdev |
|---|---|---|---:|---:|---:|---:|
| 2K | Balanced | **Epic** | **97.5 ± 2.5** (4 runs) | **48.8 ± 1.3** | ~71 | 1.4 ms |
| 2K | Balanced | High | 107.9 | 53.9 | 82.9 | 0.85 ms |
| 2K | Quality | Epic | 83.7 | 41.9 | 61.2 | 2.5 ms |
| 2K | Quality | Epic, **FG 3X** | **119.3** | **39.8** | **86.0** | **1.5 ms** |
| 2K | DLAA | Epic | 54.6 | 27.5 | 21.9 | 12.7 ms (49 frames > 50 ms) |
| 4K | Performance | Epic | 60.2 | 30.1 | 45.7 | 1.8 ms |
| 4K | Performance | High | 79.0 | 39.5 | 63.4 | 0.99 ms |

Reading it:

- **Epic costs ~8% of real fps at 2K but ~31% at 4K**, because Epic's shadow/GI/reflection work scales
  with output resolution. On this card, spending the budget on output resolution beats spending it on
  Epic effects.
- **DLAA at Epic is beyond the card.** It isn't VRAM (7.7 GB, same as the rest); the frame time simply
  falls apart.
- **VRAM ran 7.4–7.7 GB of 8 GB in every playable configuration.** 4K + Performance used *less* than
  2K + Balanced, because the internal render buffers dominate, not the output.
- **3X frame generation is the better fit for a 120 Hz panel.** Going from 2X to 3X cost only 5% of the
  real frame rate (41.9 → 39.8) and filled the refresh rate: 119.3 displayed, exactly 2 generated frames
  per real one, and *steadier* pacing than 2X (stdev 2.5 → 1.5 ms, 1% low 61 → 86) because the output sits
  against the 120 Hz ceiling. 4X would be pointless here — the panel can't show it.
- **Multipliers don't change how the game feels.** Input still tracks the ~40 real fps at both 2X and 3X.
- Final settings: **2K + Epic + DLSS Quality + FG 3X** — 119 displayed / 40 real.

### Four measurement traps this game exposed

1. **Wait for textures to settle after a settings change.** The first Epic capture showed a 334 ms
   hitch and only 958 generated frames against 1461 real ones. Two re-runs a couple of minutes later
   were clean (1503:1503, max frame 32 ms). The first reading produced a wrong "VRAM is full" call.
2. **A capture with the game out of focus is garbage.** UE throttles to 30 fps and FG stops
   completely (0 generated frames, GPU at 61%).
3. **Changing the desktop resolution reset the monitor to 60 Hz**, twice. Check the refresh rate
   after every resolution change or the capture is V-Sync-limited.
4. **Borderless windowed locks the game's resolution to the desktop's**, which is why the in-game
   resolution list is greyed out. Change the desktop, or use exclusive fullscreen.

## Appendix: the final configuration

`%APPDATA%\My Games\Bioshock Epic HD\Bioshock\Bioshock.ini`
```ini
FullscreenViewportX=2560
FullscreenViewportY=1440
StartupFullscreen=True
DesiredRefreshRate=120      ; was 60, which forced the 120 Hz panel into 60 Hz fullscreen (uncapped fps not re-measured yet)
UseVSync=1                  ; with G-Sync
```
`dlss5-feed.cfg` (next to the game exe)
```ini
enabled=1
mode=2
work_resolution=100
work_upscale=0
async_home=1
```
`host64\nvngx_dlssnr.ini` (the Cost Scaler)
```ini
EnableProxy = 1
ResolutionScale = 0.375     ; 960x540 on 2560x1440. 0.25 = 640x360 looked the same, with more headroom
EnableAlternatingFrames = 0
EnlargementMode = 1
TransferStrength = 1.00
ColorStrength = 1.00
Sharpness = 0.20
```
`host64\ReShade.ini`, section `[RenoDX.DLSS5]`: `NeuralUplift=1`, `NRPasses=1`, `NRPreset=0`,
`NREnableUpscaling=0`.

## Repository contents

| Path | What |
|---|---|
| `README.md` | this write-up |
| `images/` | 1:1 comparison crops and the frame-time chart |
| `data/` | raw PresentMon captures behind the frame-time table |
| `scripts/frametime_report.py` | PresentMon CSV summary + SVG chart |
| `skill/dlss5-nr-rtx30/` | the Claude skill (SKILL.md, component/version reference, BioShock and Expedition 33 case studies) |

## Credits

DLSS5-Feeder (jlrouzies-fr), RenoDX / renodx-dlss5 (Krish, ShortFuse and the RenoDX Discord), the
rhi-repo mirrors (RankFTW), DLSSNR-Cost-Scaler (xenmods), LumeniteFX, ReShade (crosire), Intel
PresentMon, and dlssg_for_sm86 (sdli1995). This report only measures their work.
