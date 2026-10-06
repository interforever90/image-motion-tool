"""Check the real onefile GUI and its extracted FFmpeg on a Windows runner."""

import ctypes
from ctypes import wintypes
import os
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def application_window_exists():
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
    return any(title.startswith("Image Motion Tool ") for title in titles)


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
        finally:
            if process.poll() is None:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=True)
            process.wait(timeout=30)


if __name__ == "__main__":
    main()
