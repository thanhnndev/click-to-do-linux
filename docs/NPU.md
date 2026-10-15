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

### Unplugged re-run (battery, 3 interleaved rounds, `--runs 7 --keep-alive 0`)

Same model family (Ollama `qwen2.5:3b` vs FastFlowLM `qwen2.5-it:3b`).

| | Ollama (dGPU) | FastFlowLM (NPU) |
|---|---|---|
| dGPU power during generation (delta over idle) | about +7 to +10 W | about 0 W |
| TTFT with immediate unload | about 2.0-2.3 s | about 0.9 s |
| Throughput (stream chunks/s) | about 96-98 | about 23-24 |

Caveat: whole-system battery draw (from battery voltage x current) varied
41-60 W between idle baselines on this machine, so a total-system comparison is
inconclusive; only the per-device dGPU numbers above are reliable.

### OCR on the NPU (spike, 2026-10-15)

FastFlowLM `qwen3vl-it:4b` (vision-language model on the NPU) was asked to
transcribe a synthetic 1400x430 Vietnamese/English image with 5 text lines.

- Accuracy: all 5 lines exact (diacritics, punctuation, email, digits).
- Latency: about 7.8-8.2 s per image (3 runs). The current CPU hybrid pipeline
  measured about 0.73 s for a 2560x1520 capture with 18 lines.
- No bounding boxes: the overlay needs per-line boxes for selecting and
  copying text in place, which a chat-style VLM response does not provide.

Conclusion: a VLM on the NPU can read text accurately but is roughly 10x slower
and cannot replace detection. The detection model (PP-OCR DBNet, ONNX) would
need ONNX Runtime with the VitisAI provider, which AMD distributes for Linux
only through its download portal (Ubuntu-oriented); not tested here.

### Text detection on the NPU (measured, 2026-10-15)

AMD's Ryzen AI Software 1.8 for Linux (ONNX Runtime 1.27 with the VitisAI
execution provider) does run the PP-OCRv6 detection model on the XDNA2 NPU of
this machine (Ryzen AI 9 HX 370, kernel 7.2.10, XRT 2.25).

Requirements and gotchas found while getting it to run on CachyOS:

- The installer (`ryzen_ai-1.8.0.tgz`, 7.8 GB) is behind an AMD account and EULA.
- The detection model has dynamic input dims; the NPU compiler needs a static
  shape. With dynamic dims it assigned only 3% of the model's GOPs to the NPU
  and everything ran on the CPU. With a fixed 640x960 shape, 100% of the
  operators (14.1 GOPs) are placed on the NPU (bf16 internally).
- First compile of a shape takes minutes (one time; cached in `det.rai`).
- Linux packaging quirks: the ONNX Runtime `.so` needs its executable-stack
  flag cleared on kernels that refuse it; `libpeano`, `libvaiml2` and
  `libflexmlrt` must be on `LD_LIBRARY_PATH`; XRT must be a 2.25 build with the
  xdna driver (FastFlowLM's bundled `lib/` works) and `RYZEN_AI_INSTALLATION_PATH`
  needs `lib/x86_64-linux-gnu/libxrt_core.so.2`.

Measured (640x960 input, screenshot 01 of this repo, 20 runs):

| | CPU (ORT, 24 threads) | NPU (VitisAI EP) |
|---|---|---|
| Wall time per detection | about 87-91 ms median | about 74 ms median |
| CPU time consumed per detection | about 2039 ms | about 4 ms |
| Output vs CPU (threshold 0.3) | - | binary IoU 0.90, mean abs diff 0.003 |

So the wall time is similar, but the NPU frees the CPU cores almost entirely.
bf16 changes the probability map slightly (IoU 0.90 on that screenshot); a full
end-to-end accuracy comparison on many real captures has not been done.

Install size: the Ryzen AI venv used here is about 9 GB, plus about 8 GB for
the extracted installer.

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
