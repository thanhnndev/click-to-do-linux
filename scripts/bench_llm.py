#!/usr/bin/env python
"""Benchmark a local LLM backend (Ollama or OpenAI-compatible/FastFlowLM): latency, throughput, power.

    uv run python scripts/bench_llm.py --backend ollama --model qwen2.5:3b
    uv run python scripts/bench_llm.py --backend openai --model qwen2.5-it:3b

Power sources (whatever is readable, sampled every 0.5 s during generation):
  * dGPU: nvidia-smi power.draw          * iGPU: amdgpu hwmon power1_average
  * system: battery voltage*current (only meaningful when unplugged / discharging)
Prints a JSON report to stdout.
"""
import argparse
import glob
import json
import platform
import statistics
import subprocess
import threading
import time
from pathlib import Path

import requests

PROMPT = (
    "Translate to English, output only the translation:\n\n"
    "Lịch họp tuần này. Thứ Hai: họp nhóm phát triển lúc 9:30 sáng. Thứ Tư: báo cáo tiến độ cho khách hàng. "
    "Cuối tuần cần phát hành bản Wayland vào thứ Sáu."
)


def _read(p):
    try:
        return Path(p).read_text().strip()
    except OSError:
        return None


class PowerSampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop = threading.Event()
        self.s = {"dgpu_w": [], "igpu_w": [], "battery_w": []}
        self.bat = next(iter(glob.glob("/sys/class/power_supply/BAT*")), None)
        self.igpu = next((h for h in glob.glob("/sys/class/hwmon/hwmon*") if _read(h + "/name") == "amdgpu"), None)

    def sample(self):
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=2).stdout.strip()
            if out:
                self.s["dgpu_w"].append(float(out.splitlines()[0]))
        except Exception:
            pass
        if self.igpu and (v := _read(self.igpu + "/power1_average")):
            self.s["igpu_w"].append(int(v) / 1e6)
        if self.bat and _read(self.bat + "/status") == "Discharging":
            v, c = _read(self.bat + "/voltage_now"), _read(self.bat + "/current_now")
            if v and c:
                self.s["battery_w"].append(int(v) * int(c) / 1e12)

    def run(self):
        while not self.stop.is_set():
            self.sample()
            self.stop.wait(0.5)

    def summary(self):
        return {k: (round(statistics.mean(v), 2) if v else None) for k, v in self.s.items()}


def stream(backend, host, model, keep_alive):
    t0 = time.perf_counter()
    first, n = None, 0
    if backend == "openai":
        r = requests.post(f"{host}/chat/completions", stream=True, timeout=300, json={
            "model": model, "stream": True, "temperature": 0.3,
            "messages": [{"role": "user", "content": PROMPT}]})
        for line in r.iter_lines():
            if line.startswith(b"data:") and line[5:].strip() != b"[DONE]":
                d = json.loads(line[5:])
                if (d.get("choices") or [{}])[0].get("delta", {}).get("content"):
                    first = first or time.perf_counter()
                    n += 1
    else:
        r = requests.post(f"{host}/api/generate", stream=True, timeout=300, json={
            "model": model, "prompt": PROMPT, "stream": True, "keep_alive": keep_alive,
            "options": {"temperature": 0.3}, **({"think": False} if model.startswith("qwen3") else {})})
        for line in r.iter_lines():
            if line:
                d = json.loads(line)
                if d.get("response"):
                    first = first or time.perf_counter()
                    n += 1
    end = time.perf_counter()
    return {"ttft_s": round((first or end) - t0, 2), "total_s": round(end - t0, 2), "chunks": n,
            "chunks_per_s": round(n / max(end - (first or t0), 1e-6), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["ollama", "openai"], required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--host")
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--keep-alive", default="0")
    a = ap.parse_args()
    host = a.host or ("http://127.0.0.1:52625/v1" if a.backend == "openai" else "http://localhost:11434")

    idle = PowerSampler(); idle.start(); time.sleep(4); idle.stop.set(); idle.join()
    runs, samp = [], PowerSampler()
    samp.start()
    for _ in range(a.runs):
        runs.append(stream(a.backend, host, a.model, a.keep_alive))
    samp.stop.set(); samp.join()
    cold, warm = runs[0], runs[1:]
    print(json.dumps({
        "backend": a.backend, "model": a.model, "kernel": platform.release(),
        "cold_first_request": cold,
        "warm_median_ttft_s": statistics.median(r["ttft_s"] for r in warm) if warm else None,
        "warm_median_chunks_per_s": statistics.median(r["chunks_per_s"] for r in warm) if warm else None,
        "power_idle_w": idle.summary(), "power_during_generation_w": samp.summary(),
        "on_battery": bool(samp.s["battery_w"]),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
