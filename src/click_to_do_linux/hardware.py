"""Hardware acceleration detector for AMD XDNA NPU, Intel NPU, GPUs and CPUs on Linux."""

import glob
import os
import platform
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class HardwareReport:
    npu_name: Optional[str] = None
    npu_device: Optional[str] = None
    npu_driver: Optional[str] = None
    gpu_names: List[str] = None
    cpu_name: str = ""
    active_accelerator: str = "CPU"
    badge_text: str = "⚡ CPU"
    onnx_providers: List[str] = None

    def __post_init__(self):
        if self.gpu_names is None:
            self.gpu_names = []
        if self.onnx_providers is None:
            self.onnx_providers = []


class HardwareDetector:
    """Detects available AI NPUs, GPUs and acceleration runtimes."""

    @staticmethod
    def detect() -> HardwareReport:
        report = HardwareReport()

        # 1. Detect CPU
        report.cpu_name = HardwareDetector._get_cpu_name()

        # 2. Detect NPU (AMD XDNA / Intel VPU / Qualcomm)
        npu_info = HardwareDetector._detect_npu()
        if npu_info:
            report.npu_name, report.npu_device, report.npu_driver = npu_info

        # 3. Detect GPUs
        report.gpu_names = HardwareDetector._detect_gpus()

        # 4. Detect ONNX Runtime Providers
        report.onnx_providers = HardwareDetector._get_onnx_providers()

        # 5. Determine active accelerator & badge
        if report.npu_name and (
            "VitisAIExecutionProvider" in report.onnx_providers
            or os.path.exists("/dev/accel/accel0")
        ):
            # Highlight NPU if present
            short_npu = "AMD XDNA NPU" if "AMD" in report.npu_name else (
                "Intel NPU" if "Intel" in report.npu_name else "NPU"
            )
            report.active_accelerator = f"{short_npu}"
            report.badge_text = f"⚡ {short_npu}"
        elif report.gpu_names and any("NVIDIA" in g for g in report.gpu_names):
            gpu = [g for g in report.gpu_names if "NVIDIA" in g][0]
            # shorten name
            short_gpu = "RTX GPU"
            if "5060" in gpu:
                short_gpu = "RTX 5060"
            elif "4060" in gpu:
                short_gpu = "RTX 4060"
            elif "3060" in gpu:
                short_gpu = "RTX 3060"
            report.active_accelerator = f"NVIDIA {short_gpu}"
            report.badge_text = f"⚡ {short_gpu}"
        else:
            report.active_accelerator = "CPU (AVX-512)"
            report.badge_text = "⚡ CPU"

        return report

    @staticmethod
    def _get_cpu_name() -> str:
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return platform.processor() or "Generic x86_64 CPU"

    @staticmethod
    def _detect_npu() -> Optional[Tuple[str, str, str]]:
        accel_devs = sorted(glob.glob("/dev/accel/accel*"))
        if not accel_devs:
            return None

        primary_dev = accel_devs[0]
        npu_name = "Neural Processing Unit"
        driver = "unknown"

        # Check loaded kernel modules
        try:
            lsmod = subprocess.check_output(["lsmod"], text=True)
            if "amdxdna" in lsmod:
                driver = "amdxdna (AMD XDNA Linux Driver)"
            elif "intel_vpu" in lsmod:
                driver = "intel_vpu (Intel VPU Driver)"
        except Exception:
            pass

        # Check lspci
        try:
            lspci = subprocess.check_output(["lspci"], text=True)
            for line in lspci.splitlines():
                if any(k in line for k in ["Neural Processing Unit", "Strix/Krackan", "NPU", "AI Engine"]):
                    npu_name = line.split(": ", 1)[-1].strip()
                    break
        except Exception:
            pass

        return npu_name, primary_dev, driver

    @staticmethod
    def _detect_gpus() -> List[str]:
        gpus = []
        try:
            lspci = subprocess.check_output(["lspci"], text=True)
            for line in lspci.splitlines():
                if any(k in line for k in ["VGA compatible controller", "3D controller", "Display controller"]):
                    name = line.split(": ", 1)[-1].strip()
                    gpus.append(name)
        except Exception:
            pass
        return gpus

    @staticmethod
    def _get_onnx_providers() -> List[str]:
        try:
            import onnxruntime as ort
            return ort.get_available_providers()
        except Exception:
            return []

    @staticmethod
    def get_preferred_onnx_providers(preference: str = "auto") -> List[str]:
        """Returns ordered list of ONNX Runtime Execution Providers based on hardware."""
        providers = HardwareDetector._get_onnx_providers()
        
        if preference == "cpu":
            return ["CPUExecutionProvider"]
        
        ordered = []
        # Check NPU provider
        if "VitisAIExecutionProvider" in providers:
            ordered.append("VitisAIExecutionProvider")
        if "OpenVINOExecutionProvider" in providers:
            ordered.append("OpenVINOExecutionProvider")
        if "QNNExecutionProvider" in providers:
            ordered.append("QNNExecutionProvider")

        # Check GPU provider
        if preference in ["auto", "gpu"]:
            if "TensorrtExecutionProvider" in providers:
                ordered.append("TensorrtExecutionProvider")
            if "CUDAExecutionProvider" in providers:
                ordered.append("CUDAExecutionProvider")
            if "ROCMExecutionProvider" in providers:
                ordered.append("ROCMExecutionProvider")

        # Fallback to CPU
        if "CPUExecutionProvider" in providers:
            ordered.append("CPUExecutionProvider")
        elif not ordered:
            ordered = ["CPUExecutionProvider"]

        return ordered
