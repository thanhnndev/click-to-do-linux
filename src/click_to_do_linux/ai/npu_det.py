"""Optional NPU text detection: talks to npu_det_worker.py running in a Ryzen AI env.

The worker is a separate process because AMD's ONNX Runtime build (VitisAI
provider) is a different, proprietary Python environment. Until the worker has
compiled its models (first run only) the app keeps using the CPU detector.
"""

import subprocess
import threading
from pathlib import Path
from typing import Optional

import numpy as np

WORKER = Path(__file__).with_name("npu_det_worker.py")


def default_ryzenai_dir() -> Path:
    return Path.home() / "ryzenai"


def available(ryzenai_dir: Path) -> bool:
    return (ryzenai_dir / "venv" / "bin" / "python").exists() and (ryzenai_dir / "env.sh").exists()


class NPUDetector:
    def __init__(self, ryzenai_dir: Path, model_path: str, cache_dir: Path):
        self.ready = False
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        py = ryzenai_dir / "venv" / "bin" / "python"
        cmd = f'. "{ryzenai_dir}/env.sh" && exec "{py}" "{WORKER}" "{model_path}" "{cache_dir}"'
        self._cmd = ["bash", "-c", cmd]
        threading.Thread(target=self._start, daemon=True).start()

    def _start(self) -> None:
        try:
            self._proc = subprocess.Popen(
                self._cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            for line in iter(self._proc.stdout.readline, b""):  # blocks while models compile
                if line.strip() == b"READY":
                    self.ready = True
                    break
        except Exception as e:
            print(f"[NPUDetector] start failed: {e}")
            self.ready = False

    def run(self, x: np.ndarray) -> Optional[np.ndarray]:
        """x: float32 (1,3,h,w). Returns (1,1,h,w) probability map, or None to use CPU."""
        if not self.ready or self._proc is None or self._proc.poll() is not None:
            return None
        _, _, h, w = x.shape
        try:
            with self._lock:
                self._proc.stdin.write(f"{h} {w}\n".encode() + np.ascontiguousarray(x, dtype=np.float32).tobytes())
                self._proc.stdin.flush()
                n, rh, rw = (int(v) for v in self._proc.stdout.readline().split())
                if n == 0:
                    return None
                buf = self._proc.stdout.read(rh * rw * 4)
            return np.frombuffer(buf, dtype=np.float32).reshape(1, 1, rh, rw)
        except Exception as e:
            print(f"[NPUDetector] run failed, using CPU: {e}")
            self.ready = False
            return None

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()


class NPUSession:
    """Drop-in for RapidOCR's det session: NPU when possible, otherwise the CPU session."""

    def __init__(self, cpu_session, detector: NPUDetector):
        self._cpu = cpu_session
        self._npu = detector

    def __call__(self, x: np.ndarray) -> np.ndarray:
        y = self._npu.run(x)
        return y if y is not None else self._cpu(x)

    def __getattr__(self, name):
        return getattr(self._cpu, name)
