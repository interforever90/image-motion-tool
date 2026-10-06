"""Run the production updater inside a genuine PyInstaller onefile process."""
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from image_motion_tool import App, messagebox, subprocess

if __name__ == "__main__":
    work = Path(sys.argv[1])
    work.joinpath("old-extraction.txt").write_text(sys._MEIPASS, encoding="utf-8")
    messagebox.askyesno = lambda *args, **kwargs: True
    launch = subprocess.Popen
    def record_launch(*args, **kwargs):
        process = launch(*args, **kwargs)
        work.joinpath("updater-pid.txt").write_text(str(process.pid), encoding="ascii")
        return process
    subprocess.Popen = record_launch
    app = App.__new__(App)
    app.root = SimpleNamespace(destroy=lambda: None,
                               after=lambda delay, callback: (time.sleep(delay / 1000), callback()))
    app.apply_update(work / "replacement.exe")
