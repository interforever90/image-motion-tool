"""Check the real onefile GUI and its extracted FFmpeg on a Windows runner."""

import ctypes
from ctypes import wintypes
import os
import subprocess
import tempfile
import time
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_long_duration(ffmpeg, work):
    """Exercise the application's unchanged rendering path above ten seconds."""
    sys.path.insert(0, str(ROOT))
    import tkinter as tk
    from image_motion_tool import App
    root = tk.Tk()
    root.withdraw()
    try:
        app = App(root)
        root.deiconify()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            root.update()
            if app.listbox.winfo_ismapped() and app.listbox.winfo_width() > 1:
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("Source UI did not finish mapping before layout validation")
        def check_widgets(parent):
            for widget in parent.winfo_children():
                if isinstance(widget, (tk.Listbox,)) or widget.winfo_class() in ("TButton", "TEntry", "TCombobox"):
                    in_scroll_panel = str(widget).startswith(str(app.settings_canvas) + ".")
                    x = widget.winfo_rootx() - root.winfo_rootx()
                    y = widget.winfo_rooty() - root.winfo_rooty()
                    assert 0 <= x and x + widget.winfo_width() <= root.winfo_width(), f"{widget}: horizontal clipping ({x}, {widget.winfo_width()}, {root.winfo_width()})"
                    if not in_scroll_panel:
                        assert 0 <= y and y + widget.winfo_height() <= root.winfo_height(), f"{widget}: vertical clipping ({y}, {widget.winfo_height()}, {root.winfo_height()})"
                check_widgets(widget)
        check_widgets(root)
        app.settings_canvas.yview_moveto(1)
        root.update_idletasks()
        assert app.settings_canvas.yview()[1] >= 0.999, "Export controls cannot be reached by scrolling"
        app.settings_canvas.yview_moveto(0)
        root.withdraw()
        app.duration.set("15")
        app.res.set("64x64")
        app.fps.set("24")
        app.ffmpeg = lambda: str(ffmpeg)
        image = work / "duration-test.ppm"
        image.write_bytes(b"P6\n64 64\n255\n" + bytes(
            component for y in range(64) for x in range(64)
            for component in (x * 4, y * 4, 128)))
        output = work / "duration-15s.mp4"
        app.run_one(str(image), output, "Zoom In")
        probe = subprocess.run([str(ffmpeg), "-hide_banner", "-i", str(output),
                                "-map", "0:v:0", "-c", "copy", "-f", "null", "-"],
                               capture_output=True, text=True, check=True, timeout=30)
        assert re.search(r"Duration: 00:00:15\.0", probe.stderr), probe.stderr
        assert app.duration.get() == "15", "Duration unexpectedly changed"
        print("PASS: real application filter and FFmpeg generated a 15-second MP4")
    finally:
        root.destroy()


def application_window_exists(version=None):
    titles = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32 = ctypes.windll.user32
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL

    @callback_type
    def visit(window, _):
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(window, title, len(title))
        titles.append(title.value)
        return True

    if not user32.EnumWindows(visit, 0):
        raise RuntimeError("Unable to enumerate application windows")
    prefix = "Image Motion Tool " if version is None else f"Image Motion Tool {version} —"
    return any(title.startswith(prefix) for title in titles)


def main():
    if os.name != "nt":
        raise RuntimeError("This smoke test requires Windows")
    exe = ROOT / "dist" / "ImageMotionTool.exe"
    assert exe.is_file(), "Missing standalone executable"
    with tempfile.TemporaryDirectory(prefix="imt-smoke-") as directory:
        work = Path(directory)
        env = dict(os.environ, TEMP=str(work), TMP=str(work))
        process = subprocess.Popen([str(exe)], cwd=work, env=env)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"GUI exited during startup: {process.returncode}")
                binaries = list(work.glob("_MEI*/ffmpeg.exe"))
                if binaries and application_window_exists():
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("Packaged Tk GUI or bundled FFmpeg did not become ready")
            ffmpeg = binaries[0]
            subprocess.run([str(ffmpeg), "-version"], check=True, timeout=30)
            output = work / "smoke.mp4"
            subprocess.run([
                str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=64x64:r=24",
                "-t", "0.25", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(output),
            ], check=True, timeout=30)
            assert output.is_file() and output.stat().st_size > 0, "FFmpeg produced no video"
            print("PASS: standalone Tk GUI, bundled FFmpeg and libx264 MP4 encoding")
            subprocess.run(["powershell", "-NoProfile", "-File",
                            str(ROOT / "scripts" / "capture_windows.ps1"),
                            "-Output", str(ROOT / "dist" / "interface.png")],
                           check=True, timeout=30)
            check_long_duration(ffmpeg, work)
        finally:
            if process.poll() is None:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=True)
            process.wait(timeout=30)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"::error::{type(error).__name__}: {error}", flush=True)
        raise
