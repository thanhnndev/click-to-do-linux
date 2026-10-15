# NPU support — research notes & status

Goal: stop keeping a discrete GPU busy/awake for background features. This document records what was
measured and researched on the author's machine (AMD Ryzen AI 9 HX 370, XDNA2 NPU, RTX 5060 dGPU,
CachyOS, kernel 7.2) and what the app implements. Anything not measured is marked **unverified**.

## 1. Where the power actually goes (measured)

| Component | Runs on | Measured / observed |
|---|---|---|
| `click-to-do daemon` idle | CPU | 0 CPU ticks over 20 s, ~195 MB RSS (OCR models resident), **no GPU use** (not in `nvidia-smi`) |
| RapidOCR detection (ONNX Runtime, CPU only) | CPU | ~0.42 s for a 2560×1520 capture, ~0.73 s with Tesseract recognition (18 lines) — only on demand |
| rembg cutout | CPU (ONNX) | on demand |
| **LLM (Translate / Explain / Ask)** via Ollama | **dGPU/CPU** | model is loaded into VRAM and kept for `keep_alive` — this is the only part that wakes the dGPU |

Conclusion: OCR is a short on-demand CPU burst; the idle daemon is essentially free. The LLM is the
component worth moving to the NPU.

## 2. NPU software stack on Linux (AMD XDNA2)

- Kernel driver `amdxdna` is in-tree (kernel ≥ 6.14; FastFlowLM docs want 7.0+ for firmware 1.1.x).
  On the test machine: `/dev/accel/accel0` present, runtime-PM state `suspended` when idle.
- Userspace: `xrt` + `xrt-plugin-amdxdna` (packaged in Arch `extra`).
- **LLMs: FastFlowLM** (`fastflowlm` in Arch `extra`/CachyOS repos). Runs LLMs entirely on the NPU,
  serves an **OpenAI-compatible API** on `http://127.0.0.1:52625/v1` (`/v1/models`, `/v1/chat/completions`).
  Models include `qwen3:{0.6b,1.7b,4b,8b}`, `qwen3-it:4b`, `qwen2.5-it:3b`, `qwen3.5:*`, Llama and Gemma
  families (Q4 quantised, FLM-specific format — **not** Ollama/GGUF models). Source and kernels:
  MIT CLI + free closed-source NPU kernels (FastFlowLM NPU Binary License).
- Requirements per FastFlowLM docs: NPU firmware ≥ 1.1.0.0, `ulimit -l` = unlimited (memlock),
  XDNA2 chip (Strix Point/Halo, Krackan, Gorgon). XDNA1 (Phoenix/Hawk Point) is not supported.
- **ONNX models (OCR/cutout) on the NPU: not viable today.** AMD's Vitis AI Execution Provider is
  documented as Windows-only for Ryzen AI; a community CachyOS stack (Ryzen AI SW 1.8, ORT 1.27, XRT 2.26)
  runs a transformer ONNX model but showed **no speed-up vs CPU** and issues (multi-output graphs → NaN,
  compiled cache not reloadable). No evidence exists of DBNet/OCR detection on XDNA2 under Linux.
  Given OCR detection costs ~0.4 s of CPU on demand, the benefit would not justify the fragility.

## 3. What the app implements

- `llm_backend = "openai"` → any OpenAI-compatible server; defaults point to FastFlowLM
  (`openai_base_url = http://127.0.0.1:52625/v1`). Select it in **Settings → General & AI → Run models on**.
- `llm_keep_alive` for Ollama (`0` unload immediately, `2m` default, `10m`, `-1` never) so the dGPU can
  sleep right after a request. (Previously hard-coded to 10 minutes.)
- Qwen3 "no think" handled for both backends.
- Diagnostics row for NPU: device node, driver, `flm`, memlock — detection is read-only (sysfs), it never
  wakes the NPU.
- Nothing is started automatically: run `flm serve qwen3:4b` yourself (or a user systemd unit).

## 3b. Measurements (2026-10-15, plugged in, kernel 7.2.10, NPU fw 1.1.2.64)

Same prompt (≈40 output tokens, Vietnamese → English), 5 sequential requests each, `scripts/bench_llm.py`.
Models: Ollama `qwen2.5:3b` (Q4_K_M) vs FastFlowLM `qwen2.5-it:3b` (Q4_1). "chunk" ≈ one streamed token.

| | Ollama on RTX 5060 (`keep_alive=0`) | FastFlowLM on XDNA2 NPU |
|---|---|---|
| Throughput (warm) | ~111 chunks/s | ~24 chunks/s |
| Time to first token | ~1.2 s (model reloaded to VRAM every request) | ~0.9 s (model resident in NPU server) |
| Whole 40-token answer | ~1.5 s | ~2.6 s |
| dGPU power while generating | 27.9 W (idle 8.8 W → **+19 W**) | 16.7 W (idle 14.9 W → **+1.8 W**, within desktop noise) |
| iGPU power while generating | 21.9 W | 19.9 W (idle readings 6.7–34 W: noisy) |
| Output | "…Thursday: Progress report to customers." | "…Thursday: Report progress to the customers." |

Caveats — read before quoting:
- **Plugged in.** No battery discharge reading was taken, so total-system power / battery life is *not* measured.
  dGPU idle varied between 8.8 W and 17 W across runs (compositor and other apps share the GPU), so only the
  generation-time delta is meaningful. Single laptop, single model pair, short prompts, 5 runs.
- Both Q4 3B models translate "Thứ Tư" as *Thursday* (it is Wednesday): a model-size limitation on both
  backends, not an NPU issue — use a larger model (e.g. `qwen3:4b/8b`) for accuracy.
- The NPU is ~4–5× slower per token than the dGPU; for short Translate/Explain answers this means about
  one extra second, in exchange for not waking the dGPU.
- FastFlowLM was run from its portable tarball (bundled XRT) with `ulimit -l unlimited`; first model load
  into the NPU happens at `flm serve` start and was not timed.

## 4. Not done / open questions (unverified)

- Battery discharge-rate comparison while **unplugged** (the numbers above were taken on AC).
- Vietnamese quality of FLM `qwen3:4b/8b` vs Ollama equivalents (only the 3B Qwen2.5 pair was compared, one prompt).
- Auto-spawning `flm serve` on demand and stopping it when idle (socket activation) — design below.
- Vision/QR/OCR on NPU — see §2, not pursued.

### Idea: on-demand `flm serve`
A systemd user socket unit on port 52625 that starts `flm serve <model>` on first connection and exits
after N idle minutes would give "zero resident cost" NPU inference. Requires FLM to tolerate being
started per request (load time to be measured).

## Sources
- FastFlowLM: https://github.com/FastFlowLM/FastFlowLM , https://fastflowlm.com/docs/install_lin/ ,
  https://fastflowlm.com/docs/instructions/server/ , https://fastflowlm.com/docs/models/qwen/
- ONNX Runtime Vitis AI EP (Windows-only for Ryzen AI): https://onnxruntime.ai/docs/execution-providers/Vitis-AI-ExecutionProvider.html
- Community Linux stack report: https://github.com/craigchandler/ryzen-ai-arch
