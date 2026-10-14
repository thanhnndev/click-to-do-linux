"""NPU discovery (AMD XDNA / Intel VPU) via sysfs. Pure detection: never loads a runtime or wakes the device."""

import resource
import shutil
from dataclasses import dataclass
from pathlib import Path

_VENDORS = {"0x1022": "AMD XDNA", "0x8086": "Intel NPU"}


@dataclass
class NPUInfo:
    present: bool = False
    name: str = ""
    driver: str = ""
    device_node: str = ""
    flm: bool = False          # FastFlowLM CLI (AMD)
    xrt: bool = False          # xrt-smi (AMD XRT userspace)
    memlock_ok: bool = False   # NPU buffers need a large RLIMIT_MEMLOCK

    @property
    def llm_ready(self) -> bool:
        return self.present and self.flm and self.memlock_ok


def detect() -> NPUInfo:
    info = NPUInfo()
    info.flm = shutil.which("flm") is not None
    info.xrt = shutil.which("xrt-smi") is not None
    soft, _ = resource.getrlimit(resource.RLIMIT_MEMLOCK)
    info.memlock_ok = soft == resource.RLIM_INFINITY or soft >= 8 * 1024**3
    for dev in sorted(Path("/sys/class/accel").glob("accel*")):
        d = dev / "device"
        try:
            vendor = (d / "vendor").read_text().strip().lower()
        except OSError:
            continue
        info.present = True
        info.name = _VENDORS.get(vendor, f"NPU ({vendor})")
        drv = d / "driver"
        info.driver = drv.resolve().name if drv.exists() else ""
        info.device_node = f"/dev/accel/{dev.name}"
        break
    return info
