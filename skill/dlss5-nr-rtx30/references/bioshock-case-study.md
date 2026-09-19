# Case study: BioShock Remastered (Epic), RTX 3070, September 2026

This was the first game set up with this method. Use it as the reference for measured costs, what
went wrong, and the final state.

## Setup
- Game: `<install dir>\Build\FinalEpic\BioshockHD.exe`, **32-bit, D3D11, no native DLSS**
  (no NGX, FSR or XeSS strings in the exe). The only route is the Feeder with a 64-bit helper in `host64\`.
- Work folder with every download, backup, log and screenshot:
  `%USERPROFILE%\Documents\...\nr-validation\` (`evidence\`, `tools\`,
  `drivers\`, `rollback-game.ps1`)
- Game display settings: `%APPDATA%\My Games\Bioshock Epic HD\Bioshock\Bioshock.ini`, keys
  `FullscreenViewportX/Y` and `StartupFullscreen`. Saves are in
  `Documents\My Games\Bioshock Epic HD\...\SaveGames\`.
- Pipeline: game → ReShade x86 (Lumenite motion vectors, depth) → Feeder → helper (D3D12) → DLSS
  DLAA 1:1 → RenoDX 5.2.1 → Cost Scaler → NR 310.8.SF-v2 → result back to the game (one frame
  late) → present.

## Final state the user chose ("stable 57 fps")
2560×1440 fullscreen, Feeder 100% / `work_upscale=0`, NR every frame at 960×540
(`ResolutionScale = 0.375`), alternating off.
Result: **57.0 fps average, 1% low 53.2, stdev 0.47 ms** while panning.
Update 2026-09-19: the user applied a smaller Afterburner overclock (about 2025 MHz under load, up
from about 1980). That gave a **locked 60.0 fps** (a 60 fps cap was active), 1% low 55.4,
helper 14.06 ms, and no driver resets in 2 h. The earlier, larger overclock hung the GPU (see
below), so check the System event log for 4101/141 events after long sessions.

## Measured costs (every-frame NR, lighthouse hall)
| Output | NR size | Frame time | FPS |
|---|---|---:|---:|
| 4K, DLAA only (NR off) | — | 9.2 ms | 109 |
| 4K | 960×540 | 24.8 ms | 40.4 |
| 4K | 1286×724 | 30.3 ms | 33.0 |
| 4K | 1706×960 | 37.3 ms | 26.8 |
| 4K | 1920×1080 | 44.2 ms | 22.6 |
| 4K | 2560×1440 | 63.9 ms | 15.6 |
| 4K | 3840×2160 (proxy off) | ~80 ms | 12.5 |
| 2K | 960×540 | 17.5 ms | 57.0 |

A linear fit at 4K gives **frame time ≈ 18.4 ms + 12.3 ms per NR megapixel**, which includes about
9.2 ms of game + DLAA work. Use it to estimate other NR sizes. On Ampere the NR has a large fixed
cost: even 640×360 in the standalone test took about 11 ms.

2K sweep (2026-09-19, Medical Pavilion-style tiled hall, mild OC, 60 fps cap): NR 360p 60 fps
(helper about 10.5 ms), 540p 60 (about 14 ms), 720p 48, 960p 35.5, 1080p 30, 1440p 18.7. In 1:1
crops, 360p through 1440p were almost identical. 360p leaves about 3.5 ms of headroom below the
60 fps limit.
Setting `ResolutionScale` to 0.999 (anything within 0.005 of 1.0) puts the Cost Scaler into
passthrough, which gives full-resolution NR. Switching into and out of passthrough live was safe.
To show a "DLAA only" look without restarting, set `TransferStrength = 0`, `ColorStrength = 0`
and `Sharpness = 0`. NR still runs at full cost in this mode, so it is for comparing images only.

## Image quality findings (pixel-for-pixel crops, static scene)
- With the Cost Scaler's matched-residual resolve, **NR at 540p looked almost the same as NR at
  1440p** at 4K output. Geometry and texture come from the native frame, and the NR delta is mostly
  low-frequency. So 540p is the sweet spot.
- NR on versus off, at the same resolution: NR turns glossy gold into bronze with patina, adds
  grime and brick texture, and damps colored bloom and emissive glow (fires and lamps look dimmer
  and whiter). Whether the user likes it is a matter of taste.
- A lower output resolution (2K upscaled for comparison) is visibly softer. That softness comes from
  the output resolution, not from NR.
- In fire and water scenes it is hard to judge anything. Use a static, well-lit interior with
  materials (the lighthouse hall statue).

## Every-other-frame NR (`EnableAlternatingFrames`) is not frame generation
4K, 540p NR, measured with PresentMon while panning:
- Alternating: average 60.6 fps, but the frames go **10 ms / 23 ms / 10 / 23…** (stdev 6.5 ms),
  1% low 40.2.
- Every frame: 44.2 fps, steady 22.6 ms (stdev 1.5), 1% low 38.8.
On a 60 Hz G-Sync display the 10 ms frames exceed the VRR range and tear, and the NR layer updates
at about 30 Hz. The user chose every-frame NR.

## Things that broke, and the rule each one taught
1. **Turning the Feeder back on live** (`enabled=0→1`) → RenoDX deadlock → helper crash. Rule:
   turning it off live is fine, turning it on needs a game restart.
2. **Changing `work_resolution` live** → the helper crashed on rebuild. Rule: change it only with
   the game closed.
3. **Cost Scaler `ResolutionScale` and `EnableAlternatingFrames` change live safely.** Use this to
   sweep NR sizes with the camera fixed. This gives pixel-identical screenshots.
4. **Alt-tab** recreates ReShade's runtime and pauses the feed for about 1 s. It also drops the key
   press if the user switches away while taking a screenshot. Ask the user to switch with Alt+Tab
   (not the mouse, which moves the camera), wait about 10 s, then hold PrtScn for about 0.5 s.
5. **After a crash the game reset itself to 1024×768 windowed** (`StartupFullscreen=False`).
   Check the display ini before every launch. Change the resolution in the ini while the game is
   closed. Changing it in the in-game menu rebuilds DLSS and can crash.
6. **A GPU overclock in Afterburner** → Display event 4101 plus LiveKernelEvent 141, and the
   helper's device was removed. NR keeps the GPU at 100%, so an overclock that is stable elsewhere
   may not be stable here. Don't recommend overclocking. If the user does it anyway, tell them to
   use small core steps and test NR for 5 minutes or more.
7. The Feeder's synthetic SR (`work_upscale=2`) cannot turn a 2K game into a 4K output: the SR
   target is always the game's own backbuffer size. The only way to get "render less, display
   more" in a game without DLSS is to upscale outside the game (NVIDIA Image Scaling or GPU
   scaling, Magpie, Lossless Scaling).
8. Frame generation on this game: none is possible in-pipeline. DLSS-G/MFG unlocks need x64 DX12
   with Streamline, Smooth Motion needs RTX 40/50, and FSR3 through OptiScaler does not work on
   32-bit D3D11. Only an external capture tool (Lossless Scaling) would work. The user did not buy
   it.
