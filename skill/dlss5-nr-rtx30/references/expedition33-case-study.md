# Case study: Clair Obscur: Expedition 33 (Steam), RTX 3070, 2026-09-20

The second game, and the first on the **native-DLSS route** (no Feeder, no helper process). It is
also the case where **NR was installed, measured, and then removed on purpose**.

## Classification (5 minutes, before touching anything)
- `SandFall-Win64-Shipping.exe`, **x64, D3D12**, UE5, single-player, no anti-cheat.
- Ships DLSS SR + Ray Reconstruction + **DLSS-G** (`nvngx_dlss*.dll` 310.2.1, Streamline 2.7.30 under
  `Sandfall\Plugins\NVIDIA\`). FG was greyed out until the Ampere unlock went in.
- Settings live in `%LOCALAPPDATA%\Sandfall\Saved\Config\Windows\GameUserSettings.ini`
  (`sg.*` quality levels, `sg.ResolutionQuality` = DLSS ratio, `CurrentSelectedUpscalerQualityMode`,
  `CurrentSelectedFrameGenerationMode`, `ResolutionSizeX/Y`, `FullscreenMode`).

## NR on the native-DLSS route: it works, first try
Install next to the exe: ReShade 6.8.0 Addon (`dxgi.dll`), `renodx-dlss5.addon64` 5.2.1, the
Ampere-patched NR runtime as `nvngx_dlssnr_real.dll`, and the Cost Scaler 1.0.6 as `nvngx_dlssnr.dll`
plus its ini and companion add-on. Seven added files, nothing overwritten.

The log proves the order that the Feeder path could only approximate:
```
NGX feature create intercepted: feature=1 (DLSS/DLAA)
feature 18 created via the signed snippet after DLSS/DLAA for NR input 2560x1440 -> output 2560x1440 with guides 1485x836
[Proxy] Allocated slot 0 textures: work=640x360, native=2560x1440
```
So NR runs on the **post-SR image** (1440p), with the game's own render size (1485×836) as guides.

**Measured NR tax: 10.0 ms** at 2K output with NR 640×360 (65.1 → 39.5 fps). BioShock's tax at the
same settings was 8.5 ms, so the tax is **not identical across games** — predict with it, then
re-measure. The prediction (42 fps) was 6% off the measured 39.5.

VRAM with NR: 7.44 GB of 8 GB, +0.37 GB over the baseline. No stutter.

## Why NR was removed
NVIDIA's own research page states DLSS 5 "is not designed for games whose visual identity depends on
a strongly stylized aesthetic" and that applying it to illustrated or cartoon-like games "may work
against the art direction". Expedition 33 is painterly/impressionist, and community posts complain
that DLSS 5 "ruins the art style" there. The user chose to drop NR rather than pay 10 ms for a look
that fights the game's art direction. **Check the game's art style before selling NR.**

## Frame generation on Ampere: dlssg_for_sm86
- Version **0.3.5** (2026-09-19). Install = `version.dll` + `dlssg_sm86.ini` next to the exe;
  uninstall = delete them. Factory ini: `Optimized=1`, `MaxGeneratedFrames=3`.
- The DLL is **self-signed**, so Windows reports the signature as untrusted. Do not add a trust
  exception; verify the size against the repo and note the limitation to the user.
- Docs give FG's own GPU cost per group: 1440p 2X ≈ 1.49 ms optimized, 4K 2X ≈ 1.99 ms, and the extra
  VRAM: ~540 MiB at 1440p, ~810 MiB at 4K.
- **Measured here at 1440p 2X: about 3.2 ms per group**, twice the documented figure (65.1 fps
  baseline → 53.9 real fps with FG on, same settings).
- PresentMon `--v2_metrics` is how you prove it: each generated frame appears as an extra present
  with a tiny `FrameTime` (~0.4 ms) next to the real frame (~18 ms). Count them: a healthy 2X run is
  1:1. In the failed runs the ratio dropped to 958:1461.

## Measured configurations (Epic unless noted, FG 2X, 2K = 2560×1440 @ 120 Hz)

| Output | DLSS | Preset | Displayed | Real | 1% low (displayed) | Frame-time stdev |
|---|---|---|---:|---:|---:|---:|
| 2K | Balanced | Epic | **97.5 ± 2.5** (4 runs) | **48.8 ± 1.3** | ~71 | 1.4 ms |
| 2K | Balanced | High | 107.9 | 53.9 | 82.9 | 0.85 ms |
| 2K | Quality | Epic | 83.7 | 41.9 | 61.2 | 2.5 ms |
| 2K | DLAA | Epic | 54.6 | 27.5 | 21.9 | **12.7 ms** (49 frames > 50 ms) |
| 4K | Performance | Epic | 60.2 | 30.1 | 45.7 | 1.8 ms |
| 4K | Performance | High | 79.0 | 39.5 | 63.4 | **0.99 ms** |

The user settled on **2K + Epic + DLSS Balanced + FG 2X**.

Notes:
- Epic costs only ~8% of real fps at 2K but ~31% at 4K, because the Epic shadow/GI/reflection work
  scales with output resolution.
- DLAA at Epic is beyond this card: the frame time falls apart (not a VRAM problem, VRAM stayed at
  7.7 GB; it is simply GPU-bound).
- VRAM ran 7.4–7.7 GB of 8 GB in every playable configuration. 4K + Performance used *less* than
  2K + Balanced, because the internal render buffers dominate.

## Lessons this game added
1. **Wait for textures to settle before measuring.** The first Epic capture showed 334 ms hitches and
   a 958:1461 generated-frame ratio; it was the texture streaming that follows a settings change.
   Two re-runs after a couple of minutes of play were clean. An early wrong call ("VRAM is full")
   came from measuring too soon.
2. **A capture with the game out of focus is garbage.** UE caps background frame rate (30 fps here)
   and FG stops entirely: 0 generated frames, 61% GPU. Tell the user to Alt+Tab back and wait ~10 s
   before the capture starts.
3. **Changing the desktop resolution resets the refresh rate to 60 Hz** on this monitor. Check it
   every time, or the measurement is V-Sync-limited.
4. **Borderless windowed locks the game's resolution to the desktop's.** To test another output
   resolution, change the desktop (or switch to exclusive fullscreen). Borderless is still the better
   mode for this workflow: instant Alt+Tab, overlays work, and external FG tools require it.
5. With FG on, the in-game frame limiter usually caps *real* frames. To cap the displayed rate, use
   the NVIDIA Control Panel's Max Frame Rate. And a cap halves into the real rate, so never set 60.
