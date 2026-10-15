"""Text-detection worker for the AMD XDNA2 NPU (runs inside the Ryzen AI Python env).

Not imported by the app: it is launched as a subprocess with the Python of an
AMD Ryzen AI Software install (see docs/NPU.md). Only numpy, onnx and
onnxruntime (VitisAI build) are needed.

Protocol on stdin/stdout (binary):
  worker -> app : b"READY\\n" once all shape buckets are compiled and loaded
  app -> worker : b"<h> <w>\\n" + float32 tensor (1,3,h,w) C-order
  worker -> app : b"<n> <h> <w>\\n" + float32 map (h,w) (n=0 means "no bucket, use CPU")
"""

import os
import sys

import numpy as np

# (H, W) buckets, ascending by area. The NPU needs static shapes.
BUCKETS = [(640, 960), (1088, 1920), (1536, 2560)]


def _fix_shape(src: str, h: int, w: int, dst: str) -> None:
    import onnx
    from onnx import shape_inference

    m = onnx.load(src)
    for dim, v in zip(m.graph.input[0].type.tensor_type.shape.dim, (1, 3, h, w)):
        dim.ClearField("dim_param")
        dim.dim_value = v
    for o in list(m.graph.output) + list(m.graph.value_info):
        t = o.type.tensor_type
        for dim in t.shape.dim:
            dim.Clear()
        t.ClearField("shape")
    onnx.save(shape_inference.infer_shapes(m), dst)


def _session(cache: str, h: int, w: int):
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.log_severity_level = 3
    return ort.InferenceSession(
        os.path.join(cache, f"det_{h}x{w}.onnx"), so, providers=["VitisAIExecutionProvider"],
        provider_options=[{"cache_dir": cache, "cache_key": f"det_{h}x{w}"}],
    )


def _compile_all(model: str, cache: str) -> None:
    """The NPU compiler is single-threaded, so compile each bucket in its own process."""
    import subprocess

    procs = []
    for h, w in BUCKETS:
        fixed = os.path.join(cache, f"det_{h}x{w}.onnx")
        if not os.path.exists(fixed):
            _fix_shape(model, h, w, fixed)
        procs.append(subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--compile", cache, str(h), str(w)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ))
    for p in procs:
        p.wait()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--compile":
        _session(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
        return
    model, cache = sys.argv[1], sys.argv[2]
    os.makedirs(cache, exist_ok=True)
    _compile_all(model, cache)  # no-op per bucket once cached
    sessions = []
    for h, w in BUCKETS:
        s = _session(cache, h, w)
        if s.get_providers()[0] != "VitisAIExecutionProvider":
            raise RuntimeError("VitisAI provider not active")
        sessions.append((h, w, s, s.get_inputs()[0].name))
    out, inp = sys.stdout.buffer, sys.stdin.buffer
    out.write(b"READY\n")
    out.flush()
    while True:
        line = inp.readline()
        if not line:
            return
        h, w = (int(v) for v in line.split())
        buf = inp.read(3 * h * w * 4)
        x = np.frombuffer(buf, dtype=np.float32).reshape(1, 3, h, w)
        pick = next(((bh, bw, s, n) for bh, bw, s, n in sessions if bh >= h and bw >= w), None)
        if pick is None:
            out.write(b"0 0 0\n")
            out.flush()
            continue
        bh, bw, s, name = pick
        if (bh, bw) != (h, w):
            pad = np.zeros((1, 3, bh, bw), dtype=np.float32)
            pad[:, :, :h, :w] = x
            x = pad
        y = s.run(None, {name: x})[0][0, 0, :h, :w].astype(np.float32)
        out.write(f"1 {h} {w}\n".encode() + np.ascontiguousarray(y).tobytes())
        out.flush()


if __name__ == "__main__":
    main()
