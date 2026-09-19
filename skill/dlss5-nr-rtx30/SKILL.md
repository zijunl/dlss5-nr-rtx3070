---
name: dlss5-nr-rtx30
description: Set up, tune and measure the community DLSS 5 Neural Rendering (NR, "3D-guided neural rendering", feature 18) on an RTX 3070 / RTX 30-series (Ampere) PC for a new game. The default target is a game with native DLSS, rendered internally at 1440p, upscaled by DLSS SR to 4K, with NR through RenoDX DLSS5 + DLSSNR-Cost-Scaler, 4K output at about 40 fps, and DLSS Frame Generation unlocked with dlssg_for_sm86. It also covers games without DLSS through DLSS5-Feeder (32-bit, D3D9/10/11, Vulkan). Use this skill whenever the user mentions DLSS 5, 神经渲染, NR, neural rendering, RenoDX DLSS5, Cost Scaler, DLSS5-Feeder, 帧生成/FG on a 30-series card, 在3070上跑DLSS5, or asks to set up "the same thing we did for BioShock" on another game, even if they only name the game.
---

# DLSS 5 Neural Rendering on an RTX 3070

This skill captures a working, measured method from a long session on a reference PC (RTX 3070
8 GB, 4K 120 Hz G-Sync monitor, Windows 10). Before relying on the numbers, confirm the user's GPU,
monitor refresh rate and resolution. Reply in the user's language. Keep each turn to one concrete
step the user performs at the PC ("launch the game, load the save, tell me when you're in"), then
verify it yourself from the logs.

Read these when needed:
- `references/components.md`: sources, versions, sha256, config keys, and the log lines that prove
  things work. Read it before you download or edit anything.
- `references/bioshock-case-study.md`: measured costs, image-quality findings, and every failure
  from the first game, each with the rule it taught. Read it before you tune performance or when
  something breaks.
- `scripts/frametime_report.py`: summarises PresentMon captures and draws the frame-time chart.

## What the user wants (default target profile)

```
game renders at 1440p → the game's own DLSS SR (Quality) → 4K
  → RenoDX DLSS5 captures that DLSS evaluate → Cost Scaler → NR at ~540p–720p → matched-residual composite back to 4K
  → about 40 fps real frames → DLSS Frame Generation (dlssg_for_sm86 on Ampere) → display
```

Why this order: on Ampere, NR costs about 9 ms fixed plus about 12 ms per NR megapixel. The only
ways to reach a playable frame rate are (a) the game rendering fewer pixels (native DLSS SR),
(b) a small NR size (the Cost Scaler; 540p looked like 1440p NR in pixel crops), and (c) frame
generation after NR.

**Check the monitor's refresh rate before promising FG numbers** (the reference PC's panel is 4K **120 Hz** G-Sync). On a 120 Hz panel, FG 2x from a base of about 40 fps gives about 80 fps, which fits inside the VRR range. That is the case FG is designed for. On a **60 Hz** panel, with G-Sync plus V-Sync
(and Reflex, which DLSS-G turns on), FG output is capped just under 60, so FG 2× runs the real game
at about 29 fps and adds latency. A base of about 40 fps with FG therefore turns into about 29 real
fps shown as 58. FG is worth it when the base is well below 57. Otherwise a steady 45–57 fps inside
the G-Sync range may feel better. Present both options with PresentMon numbers and let the user
choose.

## Step 1: Classify the game before touching anything

The route depends entirely on these facts. Check them from the files, not from memory:

1. **Bitness**: read the PE header of the render exe. Machine `0x8664` means x64, `0x14c` means x86:
   ```powershell
   $b=[IO.File]::ReadAllBytes($exe); $pe=[BitConverter]::ToInt32($b,0x3C); '{0:X}' -f [BitConverter]::ToUInt16($b,$pe+4)
   ```
2. **API**: while the game runs, list its loaded modules (`d3d12.dll`, `d3d11.dll`, `vulkan-1.dll`,
   `d3d9.dll`). Imports alone can mislead: BioShock imports both D3D9 and D3D11.
3. **Native DLSS SR**: `nvngx_dlss.dll` in the game folder, plus a DLSS option in the game menu.
4. **Native DLSS Frame Generation**: `nvngx_dlssg.dll` and Streamline `sl.dlss_g.dll`/`sl.interposer.dll`,
   plus a "DLSS Frame Generation" menu option.
5. **Anti-cheat and online play**: EAC/BattlEye/online modes. Proxy DLLs and ReShade can get the
   account banned. Only proceed for single-player or offline play, and say so.
6. Current driver (`nvidia-smi`) and free VRAM. NR at 4K used about 4–6 GB on this 8 GB card.

## Step 2: Pick the route

| Game | Route | Frame generation |
|---|---|---|
| x64 **DX12** + native DLSS SR + native DLSS-G | **Target route**: ReShade (addon build) + `renodx-dlss5.addon64` + NR DLL behind the Cost Scaler, next to the exe. The game's own DLSS SR at Quality. `dlssg_for_sm86` for FG | ✅ unlock with dlssg_for_sm86 (x64 D3D12 + Streamline only) |
| x64 DX12 + DLSS SR, no DLSS-G | Same NR route | ❌ no in-game FG. The only external option is Lossless Scaling (paid; the user must buy it) |
| x64 DX11 + DLSS SR | NR route, but the Cost Scaler says "DirectX 12". Check RenoDX's D3D11 handling first and plan for NR at a fixed size without the proxy | ❌ the dlssg_for_sm86 unlock is D3D12 only |
| x64 without DLSS | ShortFuse `renodx-dlss` (RenoDX Discord) **or** the Feeder. Never both | ❌ |
| **32-bit**, Vulkan, D3D9/10 | DLSS5-Feeder + 64-bit `host64\` helper (the BioShock route). DLAA only, no real SR | ❌ nothing in-pipeline |

Games without DLSS cannot do "render 2K → SR → 4K". The Feeder's `work_upscale=2` SR always
outputs at the game's own backbuffer size, and the author measured that it "saves nothing" and
shimmers. For those games, reduce the game resolution and upscale outside the game (NVIDIA Image
Scaling, Magpie), or accept native resolution.

## Step 3: Prepare safely

- **Ask before each download**: give the file name, source URL and size. Take files only from the
  upstream locations in `references/components.md`, and check each sha256 or Authenticode signature
  against the release page. The Feeder project itself warns about fake, malicious copies.
- **Driver**: 616.56 is the known-good version for the Feeder with RenoDX. 616.64 and newer crashed
  with RenoDX 4.6/4.7 (Feeder issue #54). dlssg_for_sm86 was tested by its author on 591.86 and
  610.74. Don't upgrade the driver blindly. If the combination is untested, call it a "test
  candidate". Driver installs need UAC. If the session has no admin token, the user has to
  approve the prompt.
- **Keep everything in a work folder**: `%USERPROFILE%\Documents\<game>-nr-validation\`, with
  `downloads\`, `evidence\` and `tools\` inside. Before changing any game file, record the original
  file list and back up every file you will touch into `evidence\before-<change>\`. Write a
  `rollback-game.ps1` that moves only the files you added. Never overwrite original game DLLs
  without keeping a copy. For the FG unlock, keep the game's original `version.dll` if one exists.
- Never add trust exceptions, run unsigned installers, overclock, or disable security features.
  If ReShade's installer certificate isn't trusted, extract the DLL from the official package and
  compare its hash against a reference instead.

## Step 4: Install and prove each layer separately

Do one layer at a time and prove it from the logs before adding the next. The log lines to look
for are in `references/components.md` §4.

1. **Game plus its own DLSS SR at Quality, 4K output, NR off.** Record the baseline FPS.
2. **NR standalone check if possible** (the Feeder ships a `host64 --test` diagnostic). Then turn NR
   on in the game. The proof is that `feature 18 evaluation succeeded (count=…)` keeps rising, and
   that the NR input and output are 3840×2160 (the post-SR frame). An FPS drop proves nothing.
3. **Cost Scaler**: rename the real NR DLL to `nvngx_dlssnr_real.dll`, put the proxy and its ini in
   place, and set `ResolutionScale = 0.25` (960×540 on a 4K input). Proof: `Allocated slot …
   work=960x540, native=3840x2160`.
4. **Frame generation** (only on the target route): add dlssg_for_sm86, turn on DLSS-G in the game,
   and confirm that the NR count still rises with FG on. **NR + FG together has not been verified
   on this PC.** Another NR consumer gave a black screen with FG, so check the picture as well as
   the logs. If it fails, roll back only the FG files.

The game must be fully closed whenever you change the game resolution, turn NR or the Feeder
**on**, or change the Feeder's `work_resolution`. The Cost Scaler ini (`ResolutionScale`,
`EnableAlternatingFrames`) reloads live and is safe to change while playing. Before each launch,
check the game's display ini, because after a crash BioShock reset itself to 1024×768 windowed.

## Step 5: Tune with measurements, not impressions

- **Frame timing**: run PresentMon 2.x in the background while the user pans the camera steadily
  for about 40 s. Tell them to start panning *before* you start recording, and not to alt-tab.
  ```
  PresentMon-2.5.1-x64.exe --process_name <Game>.exe --output_file <run>.csv --timed 30 --terminate_after_timed --no_console_stats --stop_existing_session
  python scripts/frametime_report.py a.csv b.csv --labels "A" "B" --svg chart.svg
  ```
  Report average fps, 1% low, standard deviation, and odd/even frame averages. Then send the SVG.
  With FG, report the real frame rate as well as the displayed one.
- **NR size sweep**: in one game session with the camera held still, change `ResolutionScale`
  live (0.25 → 0.333 → 0.444 → 0.5 → 0.667), have the user hold PrtScn (ReShade saves the PNG next
  to the exe) after each change, and make 1:1 crops with ffmpeg
  (`C:\Program Files\ffmpeg-5.1.2\bin`), for example
  `ffmpeg -i a.png -i b.png -filter_complex "[0]crop=900:700:X:Y[a];[1]crop=900:700:X:Y[b];[a][b]hstack" out.png`.
  Use a well-lit, static interior with materials (statues, metal, brick). Fire, water and fog
  change between frames and hide the differences. Compare against NR off at the same resolution to
  show what NR actually changes.
- Aim for the smallest NR size that looks the same as the larger ones. That was 540p on 4K here.
- `EnableAlternatingFrames` is **not** FG. It produces a 10 ms / 23 ms sawtooth, and the 1% low
  doesn't improve. Explain that before offering it.

## Step 6: Hand over

Finish with a short table of the final settings, the measured fps (average, 1% low, stdev), the
backup and rollback locations, and what was not verified. Add useful new findings to
`references/` in this skill, for example a new case-study file per game. Keep the per-game numbers
there rather than in this file.

## Hard-won rules (details in the case study)
- Check the game's own refresh/V-Sync settings. BioShock's ini had `DesiredRefreshRate=60` with
  V-Sync on, which quietly capped a 120 Hz panel at 60 fps and made every measurement look capped.
- Turning the Feeder `enabled` 1→0 live is fine. Turning it 0→1 live crashed the helper.
- Changing `work_resolution` live crashed or froze. Changing the game resolution in the menu
  rebuilds DLSS and may crash. Edit the ini with the game closed instead.
- Alt-tab makes ReShade reload, and key presses sent during it are lost. Ask the user to use
  Alt+Tab (the mouse moves the camera), wait about 10 s, then hold PrtScn for about 0.5 s.
- An overclock that looks stable caused a GPU hang (LiveKernelEvent 141) under NR load. Recommend
  against overclocking.
- The helper logs NR time (`DLSS GPU … ms`) only every 1800 frames, and the Feeder logs fps every
  600 frames. Short or interrupted runs therefore mix settings. Use PresentMon for precise numbers.
