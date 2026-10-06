"""Exercise the production three-image batch at 1080p, 8 seconds and 30 FPS."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from image_motion_tool import App, messagebox


class Variable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def main():
    if os.name != "nt":
        raise RuntimeError("This regression check requires Windows")
    ffmpeg = ROOT / "ffmpeg.exe"
    with tempfile.TemporaryDirectory(prefix="imt-fullhd-") as directory:
        work = Path(directory)
        app = App.__new__(App)
        for name, value in {
            "duration": "8", "res": "1920x1080", "fps": "30",
            "zoom_strength": "8", "move_strength": "12", "effect": "Zoom In",
            "output_dir": str(work), "filename": "", "prefix": "",
            "progress": 0, "progress_text": "0%", "status": "Pronto",
        }.items():
            setattr(app, name, Variable(value))
        app.root = SimpleNamespace(after=lambda delay, callback: callback())
        app.cancel_event = threading.Event()
        app.current_process = None
        app.ffmpeg = lambda: str(ffmpeg)
        app.images = []
        # Representative input dimensions from the reported PNG; all three use
        # the 4x/4x Zoom In path, which requires more memory than Pan or Tilt.
        for index, color in enumerate(("#537fa6", "#bd8764", "#70a480"), 1):
            image = work / f"image-{index}.png"
            subprocess.run([
                str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"color=c={color}:s=1672x942",
                "-frames:v", "1", "-threads", "2", str(image),
            ], check=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            app.images.append(str(image))
        errors = []
        messagebox.showerror = lambda *args: errors.append(args)
        app._generate_worker()
        assert not errors, f"Full HD batch failed: {errors}"
        assert app.progress.get() == 100, "Batch did not reach 100%"
        assert app.status.get().startswith("Completato"), app.status.get()
        for index in range(1, 4):
            output = work / f"image-{index}.mp4"
            assert output.stat().st_size > 0, f"Missing video {index}"
            probe = subprocess.run([
                str(ffmpeg), "-hide_banner", "-i", str(output),
                "-map", "0:v:0", "-c", "copy", "-f", "null", "-",
            ], capture_output=True, text=True, check=True, timeout=30,
               creationflags=subprocess.CREATE_NO_WINDOW)
            assert re.search(r"Duration: 00:00:08\.0", probe.stderr), probe.stderr
            assert "1920x1080" in probe.stderr and "30 fps" in probe.stderr, probe.stderr
        print("PASS: three-image production batch generated three 1080p/30 FPS/8-second videos with 4x Zoom In oversampling")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"::error::{type(exc).__name__}: {exc}", flush=True)
        raise
