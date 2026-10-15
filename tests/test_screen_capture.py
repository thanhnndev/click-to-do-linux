import json
import os
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from click_to_do_linux.capture import screen as screen_module


class FakeScreen:
    def __init__(self, name, width=960, height=540, x=0, y=0):
        self._name = name
        self._width = width
        self._height = height
        self._x = x
        self._y = y

    def name(self):
        return self._name

    def geometry(self):
        return SimpleNamespace(
            x=lambda: self._x,
            y=lambda: self._y,
            width=lambda: self._width,
            height=lambda: self._height,
        )

    def devicePixelRatio(self):
        return 2.0


class FakeQImage:
    Format = SimpleNamespace(Format_RGB888=1)

    def __init__(self, width=1920, height=1080):
        self._width = width
        self._height = height

    @classmethod
    def fromData(cls, _data, _format):
        return cls()

    def isNull(self):
        return False

    def width(self):
        return self._width

    def height(self):
        return self._height

    def convertToFormat(self, _format):
        return self

    def constBits(self):
        class Bits(bytes):
            def setsize(self, _size):
                pass

        return Bits(self._width * self._height * 3)

    def bytesPerLine(self):
        return self._width * 3


class FakePixmap:
    @classmethod
    def fromImage(cls, _image):
        return cls()

    def setDevicePixelRatio(self, _scale):
        pass


class FakeWayfireSocket:
    def __init__(self, response):
        self.response = response
        self.sent = b""
        self.connected_path = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, _timeout):
        pass

    def connect(self, path):
        self.connected_path = path

    def sendall(self, payload):
        self.sent = payload

    def recv(self, size):
        if not self.response:
            return b""
        chunk, self.response = self.response[:size], self.response[size:]
        return chunk


class ScreenCaptureTests(unittest.TestCase):
    def test_captures_only_umbriels_focused_output(self):
        first = FakeScreen("eDP-2", width=1440, height=900)
        focused = FakeScreen("HDMI-A-1", width=1920, height=1080)
        gui = SimpleNamespace(
            screens=lambda: [first, focused],
            screenAt=lambda _pos: first,
            primaryScreen=lambda: first,
        )
        outputs = [
            {"name": "eDP-2", "enabled": True, "focused": False,
             "scale": 2.0, "logical_size": {"width": 1440, "height": 900}},
            {"name": "HDMI-A-1", "enabled": True, "focused": True,
             "scale": 1.0, "logical_size": {"width": 1920, "height": 1080}},
        ]
        umbriel_result = SimpleNamespace(stdout=json.dumps(outputs).encode(), stderr=b"")
        grim_result = SimpleNamespace(stdout=b"ppm", stderr=b"")

        with (
            patch.object(screen_module, "detect_compositor", return_value=SimpleNamespace(id="umbriel")),
            patch.object(screen_module, "QGuiApplication", gui),
            patch.object(screen_module, "QImage", FakeQImage),
            patch.object(screen_module, "QPixmap", FakePixmap),
            patch.object(screen_module.Image, "frombuffer", return_value=object()),
            patch.object(screen_module.shutil, "which", return_value="/usr/bin/umbriel"),
            patch.object(screen_module.subprocess, "run", side_effect=[umbriel_result, grim_result]) as run_capture,
        ):
            captured = screen_module.ScreenCapture.capture()

        self.assertIsNotNone(captured)
        self.assertEqual(captured.output_name, "HDMI-A-1")
        self.assertIs(captured.qt_screen, focused)
        self.assertEqual(captured.logical_w, 1920)
        self.assertEqual(run_capture.call_args_list[0].args[0], ["umbriel", "outputs", "--json"])
        self.assertEqual(run_capture.call_args_list[1].args[0], ["grim", "-t", "ppm", "-o", "HDMI-A-1", "-"])

    def test_focused_output_adapters_for_niri_hyprland_and_sway(self):
        cases = [
            (
                "niri",
                [{"name": "DP-3", "logical": {"width": 2560, "height": 1440, "scale": 1.5}}],
                ("DP-3", 1.5, 2560, 1440),
                ["niri", "msg", "-j", "focused-output"],
            ),
            (
                "hyprland",
                [[{"name": "DP-3", "focused": False},
                  {"name": "HDMI-A-1", "focused": True, "scale": 1.5,
                   "scaledWidth": 1280, "scaledHeight": 720}]],
                ("HDMI-A-1", 1.5, 1280, 720),
                ["hyprctl", "-j", "monitors"],
            ),
            (
                "sway",
                [
                    [{"name": "1", "output": "DP-3", "focused": False},
                     {"name": "2", "output": "HDMI-A-1", "focused": True}],
                    [{"name": "HDMI-A-1", "active": True, "scale": 1.25,
                      "rect": {"width": 1536, "height": 864}}],
                ],
                ("HDMI-A-1", 1.25, 1536, 864),
                ["swaymsg", "-t", "get_workspaces", "-r"],
            ),
        ]

        for compositor_id, payloads, expected, expected_first_command in cases:
            with self.subTest(compositor=compositor_id):
                results = [SimpleNamespace(stdout=json.dumps(payload).encode(), stderr=b"") for payload in payloads]
                with (
                    patch.object(screen_module, "detect_compositor", return_value=SimpleNamespace(id=compositor_id)),
                    patch.object(screen_module.shutil, "which", return_value="/usr/bin/compositor-tool"),
                    patch.object(screen_module.subprocess, "run", side_effect=results) as run_capture,
                ):
                    output = screen_module.ScreenCapture._get_focused_output()

                self.assertEqual(output, expected)
                self.assertEqual(run_capture.call_args_list[0].args[0], expected_first_command)

    def test_wayfire_focused_output_ipc(self):
        payload = json.dumps({
            "info": {
                "name": "HDMI-A-1",
                "scale": 1.25,
                "geometry": {"width": 1536, "height": 864},
            },
        }).encode()
        client = FakeWayfireSocket(struct.pack("<I", len(payload)) + payload)

        with (
            patch.dict(os.environ, {"WAYFIRE_SOCKET": "/run/user/1000/wayfire.sock"}),
            patch.object(screen_module.socket, "socket", return_value=client),
        ):
            output = screen_module.ScreenCapture._get_wayfire_focused_output()

        self.assertEqual(output, ("HDMI-A-1", 1.25, 1536, 864))
        self.assertEqual(client.connected_path, "/run/user/1000/wayfire.sock")
        request_size = struct.unpack("<I", client.sent[:4])[0]
        request = json.loads(client.sent[4:4 + request_size])
        self.assertEqual(request["method"], "window-rules/get-focused-output")

    def test_generic_compositor_fallback_still_targets_one_output(self):
        primary = FakeScreen("eDP-2", width=1440, height=900)
        cursor_screen = FakeScreen("HDMI-A-1", width=1920, height=1080)
        gui = SimpleNamespace(
            screens=lambda: [primary, cursor_screen],
            screenAt=lambda _pos: cursor_screen,
            primaryScreen=lambda: primary,
        )
        run = SimpleNamespace(stdout=b"ppm", stderr=b"")

        with (
            patch.object(screen_module, "detect_compositor", return_value=SimpleNamespace(id="generic")),
            patch.object(screen_module, "QGuiApplication", gui),
            patch.object(screen_module, "QCursor", SimpleNamespace(pos=lambda: (2000, 200))),
            patch.object(screen_module, "QImage", FakeQImage),
            patch.object(screen_module, "QPixmap", FakePixmap),
            patch.object(screen_module.Image, "frombuffer", return_value=object()),
            patch.object(screen_module.subprocess, "run", return_value=run) as run_capture,
        ):
            captured = screen_module.ScreenCapture.capture()

        self.assertEqual(captured.output_name, "HDMI-A-1")
        self.assertEqual(run_capture.call_args.args[0], ["grim", "-t", "ppm", "-o", "HDMI-A-1", "-"])

    def test_unnamed_screen_fallback_uses_its_geometry(self):
        selected = FakeScreen("", width=1920, height=1080, x=1920, y=0)
        other = FakeScreen("", width=1440, height=900, x=0, y=0)
        gui = SimpleNamespace(
            screens=lambda: [other, selected],
            screenAt=lambda _pos: selected,
            primaryScreen=lambda: other,
        )
        run = SimpleNamespace(stdout=b"ppm", stderr=b"")

        with (
            patch.object(screen_module, "detect_compositor", return_value=SimpleNamespace(id="generic")),
            patch.object(screen_module, "QGuiApplication", gui),
            patch.object(screen_module, "QCursor", SimpleNamespace(pos=lambda: (2500, 300))),
            patch.object(screen_module, "QImage", FakeQImage),
            patch.object(screen_module, "QPixmap", FakePixmap),
            patch.object(screen_module.Image, "frombuffer", return_value=object()),
            patch.object(screen_module.subprocess, "run", return_value=run) as run_capture,
        ):
            captured = screen_module.ScreenCapture.capture()

        self.assertEqual(captured.output_name, "")
        self.assertEqual(run_capture.call_args.args[0], ["grim", "-t", "ppm", "-g", "1920,0 1920x1080", "-"])

    def test_unknown_multimonitor_without_screen_fails_closed(self):
        gui = SimpleNamespace(
            screens=lambda: [FakeScreen(""), FakeScreen("")],
            screenAt=lambda _pos: None,
            primaryScreen=lambda: None,
        )

        with (
            patch.object(screen_module, "detect_compositor", return_value=SimpleNamespace(id="generic")),
            patch.object(screen_module, "QGuiApplication", gui),
            patch.object(screen_module, "QCursor", SimpleNamespace(pos=lambda: (0, 0))),
            patch.object(screen_module.subprocess, "run") as run_capture,
        ):
            captured = screen_module.ScreenCapture.capture()

        self.assertIsNone(captured)
        run_capture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
