# Components, sources and settings

Everything here was verified on this PC in September 2026 (RTX 3070 8 GB, Windows 10 22H2).
These are community projects that change weekly. Before downloading, check each project's current
release and README. Treat the versions below as a **known-good baseline**, not as the only valid
choice.

## Contents
1. Known-good baseline
2. Where each piece comes from
3. Config keys that matter
4. Log lines that prove things work

---

## 1. Known-good baseline (BioShock Remastered, 32-bit D3D11, Feeder path)

| Piece | Version | Notes |
|---|---|---|
| NVIDIA driver | **616.56** | The Feeder documents a minimum of 616.56. Its issue #54 reports that RenoDX 4.6/4.7 NR evaluation crashes inside NGX on **616.64 and newer**. 616.56 was chosen deliberately. The rollback installer for 560.94 is kept in `nr-validation\drivers\`. |
| ReShade (with add-on support) | 6.8.0 | Use the "Addon" build. Its DLLs were extracted from the official package. The installer's certificate chain was not trusted on this PC, so it was not run, and no trust or security exception was added. |
| NR runtime `nvngx_dlssnr.dll` | **310.8.SF-v2** (FileVersion string `310.8.SF.0`) | The Ampere-patched community build. sha256 of the zip: `1da35941894994eb087e017577829e492454e9bae3a6a9397027069ceb74955c` |
| DLSS runtime `nvngx_dlss.dll` | 310.9.1 | Used for DLAA/SR |
| NR consumer | RenoDX DLSS5 Generic **5.2.1** (`renodx-dlss5.addon64`) | 4.70 also worked and ran at the same speed |
| Cost Scaler | DLSSNR-Cost-Scaler **1.0.6** | A proxy DLL in front of the NR runtime. D3D12 only |
| Feeder (only for games without DLSS) | DLSS5-Feeder **1.16.0-beta.4** | 32-bit, Vulkan, D3D9/10/11 without DLSS |
| Motion vectors (Feeder path) | LumeniteFX Kernel | Picked automatically by the Feeder installer |
| Frame timing | Intel PresentMon **2.5.1** CLI | Signed by Intel Corporation. No admin needed |

## 2. Where each piece comes from

Use only these upstream locations. The Feeder release itself ships a file called
`CAREFUL_FAKE_MALICIOUS_FEEDER.txt` warning that fake, malicious copies exist. Check each download
against the sha256 digest on the GitHub release page.

- DLSS5-Feeder: https://github.com/jlrouzies-fr/DLSS5-Feeder/releases (the README is the manual.
  Read "Before you install", "Configuration", and "Logs and troubleshooting")
- RenoDX DLSS5 add-on and NR runtime mirrors: https://github.com/RankFTW/rhi-repo/releases
  (tags `renodx-dlss5-<ver>` and `dlssnr-310.8.SF-v2`). The original source is the RenoDX Discord,
  `#DLSS5` channel.
- ShortFuse `renodx-dlss` (a different add-on that replaces the Feeder for 64-bit games without
  DLSS): RenoDX Discord only. Never install it together with `renodx-dlss5` or the Feeder.
- Cost Scaler: https://github.com/xenmods/DLSSNR-Cost-Scaler/releases
- DLSS-FG unlock for Ampere: https://github.com/sdli1995/dlssg_for_sm86 (a `version.dll` plus
  `dlssg_sm86.ini` placed next to the game exe. **x64 D3D12 only, and the game must ship DLSS Frame
  Generation through Streamline.** It was tested on drivers 591.86 and 610.74. It has not been
  tested on 616.56 here.)
- DLSS Enabler (Nexus Mods) is an alternative FG unlock. It has the same requirement: the game must
  have native DLSS-G.
- PresentMon: https://github.com/GameTechDev/PresentMon/releases (take the `PresentMon-<ver>-x64.exe`
  CLI and check that its Authenticode signature is Intel Corporation)
- NVIDIA drivers: nvidia.com, or the NVIDIA App's cached update record. Check the digital signature.

## 3. Config keys that matter

### Cost Scaler — `nvngx_dlssnr.ini` (next to the NR DLL)
**Reloaded live** when the file changes (the proxy checks the file's timestamp on every evaluate).
Changing these while the game runs is safe:

| Key | Meaning |
|---|---|
| `EnableProxy` | 0 = NR at full output size (the proxy is bypassed) |
| `ResolutionScale` | NR model size as a fraction of the size the NR receives. **Clamped to 0.25–2.0 in code.** Sizes are rounded to even numbers: `round(W*s) & ~1` |
| `EnableAlternatingFrames` | NR every 2nd frame. This is NOT frame generation (see the case study) |
| `EnlargementMode` | 1 = matched residual (native frame as the anchor, plus the NR delta). This keeps geometry and texture sharp |
| `Sharpness` | RCAS strength after the resolve (0.20 default) |
| `EnableGovernor`/`TargetFps`/`MinScale` | Changes the scale automatically, in 5% steps |
| `EnableFgMode`/`FgMultiplier` | Only tells the governor that FG is multiplying the FPS. **Does not generate frames** |

NR size = (size NR receives) × `ResolutionScale`. With a native-DLSS game, NR receives the **DLSS
SR output (4K)**, so 0.25 → 960×540 and 0.333 → 1280×720.

### RenoDX DLSS5 — `[RenoDX.DLSS5]` in the ReShade.ini that loads the add-on
`NeuralUplift` (1 = NR on), `NRPreset` (a direct probe of the 310.8 runtime found presets 1–3 give identical output, so it changes neither speed nor look), `NRStyle` (0/1/2 are three distinct looks; 3 is the same as 2), `NRPasses` (1),
`NREnableUpscaling` (leave at 0), `NRToggleKey`=117 (F6).
Changing `NeuralUplift` needs a game restart. Turning NR on while the game runs can make RenoDX
deadlock.

### Feeder — `dlss5-feed.cfg` (Feeder path only)
`enabled` (turning it **off** live is safe; turning it **on** live crashed the helper),
`mode` (1 = transport test, 2 = full), `work_resolution` 50–100 (**never change it live**, because
it crashed or froze), `work_upscale` 0 bilinear / 1 FSR1 / 2 synthetic-jitter DLSS SR (the author
measured it: "saves nothing" and it shimmers), `async_home`=1 (the NR result arrives one frame late,
which lifts a ~35 fps cap), `host_gpu_priority` (leave at 0).

## 4. Log lines that prove things work

Never report "NR works" from FPS drops or looks alone. Quote these lines:
- The NR consumer's ReShade.log: `inline feature 18 evaluation succeeded (count=N …)` with a count
  that keeps rising. `NR is currently OFF` means NeuralUplift=0.
- `nvngx_dlssnr_proxy.log`: `Config loaded: … EnableVrnr = 0/1`,
  `Allocated slot N textures: work=WxH, native=WxH`
- Feeder path: `host64\dlss5-feed-host.log` → `feature ready: WxH DLAA`, and every 1800 frames
  `DLSS GPU xx.xx ms/frame` (DLAA+NR helper GPU time). `dlss5-feed.log` → every 600 frames
  `frame interval xx ms (yy fps)`.
- Signs of trouble: `host lost`, `Present failed 0x887A0005`, `DXGI_ERROR_DEVICE_HUNG`, Windows
  System log Display event 4101, or LiveKernelEvent 141. These mean the GPU hung. In this session
  the cause was an overclock.
