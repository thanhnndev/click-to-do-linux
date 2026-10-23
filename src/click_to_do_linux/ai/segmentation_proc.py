"""Out-of-process background removal.

rembg/onnxruntime inference inside the UI process competes with the Qt main
thread (GIL and CPU), which made the overlay animation stutter while a cutout
was being computed. The model therefore lives in a separate, low-priority
process that stays warm for the lifetime of the app.

Protocol on the child's stdin/stdout (binary):
  child  -> app : b"READY\\n" once the model is loaded
  app    -> child: b"<task> <w> <h>\\n" + RGB bytes (w*h*3)
  child  -> app : b"<mode> <w> <h>\\n" + raw bytes, or b"ERR 0 0\\n"
"""

from __future__ import annotations

import atexit
import os
import subprocess
import sys
import threading
from typing import Optional

from PIL import Image

_MODES = {"RGB": 3, "RGBA": 4}


def _read_exact(stream, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            raise EOFError
        buf += chunk
    return bytes(buf)


def _serve() -> None:
    # Keep stdout clean for the protocol: library chatter goes to stderr.
    out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    try:
        os.nice(10)
    except OSError:
        pass
    from .segmentation import SegmentationEngine

    SegmentationEngine.get_session()
    out.write(b"READY\n")
    out.flush()
    stdin = sys.stdin.buffer
    while True:
        header = stdin.readline()
        if not header:
            return
        task, w, h = header.decode().split()
        w, h = int(w), int(h)
        image = Image.frombytes("RGB", (w, h), _read_exact(stdin, w * h * 3))
        if task == "remove_bg":
            result = SegmentationEngine.remove_background(image)
        else:
            result = SegmentationEngine.blur_background(image)
        if result is None:
            out.write(b"ERR 0 0\n")
        else:
            if result.mode not in _MODES:
                result = result.convert("RGBA")
            out.write(f"{result.mode} {result.width} {result.height}\n".encode())
            out.write(result.tobytes())
        out.flush()


class SegmentationClient:
    """Talks to the warm worker process; restarts it if it ever dies."""

    _proc: Optional[subprocess.Popen] = None
    _ready = False
    _lock = threading.Lock()

    @classmethod
    def _start(cls) -> None:
        if cls._proc is not None and cls._proc.poll() is None:
            return
        cls._ready = False
        cls._proc = subprocess.Popen(
            [sys.executable, "-m", "click_to_do_linux.ai.segmentation_proc"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        )
        atexit.register(cls.shutdown)

    @classmethod
    def prewarm(cls) -> None:
        """Spawn the worker ahead of time so the first cutout is not delayed."""
        with cls._lock:
            try:
                cls._start()
            except OSError as e:
                print(f"[SegmentationClient] cannot start worker: {e}")

    @classmethod
    def run(cls, task: str, image: Image.Image) -> Optional[Image.Image]:
        with cls._lock:
            cls._start()
            proc = cls._proc
            if not cls._ready:
                if proc.stdout.readline().strip() != b"READY":
                    raise RuntimeError("segmentation worker failed to start")
                cls._ready = True
            rgb = image.convert("RGB")
            proc.stdin.write(f"{task} {rgb.width} {rgb.height}\n".encode() + rgb.tobytes())
            proc.stdin.flush()
            mode, w, h = proc.stdout.readline().split()
            if mode == b"ERR":
                return None
            w, h, mode = int(w), int(h), mode.decode()
            return Image.frombytes(mode, (w, h), _read_exact(proc.stdout, w * h * _MODES[mode]))

    @classmethod
    def shutdown(cls) -> None:
        proc, cls._proc, cls._ready = cls._proc, None, False
        if proc is not None and proc.poll() is None:
            try:
                proc.stdin.close()
                proc.wait(timeout=2)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    _serve()
