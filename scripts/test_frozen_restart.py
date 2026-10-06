"""Verify replacement and restart after the old onefile extraction is deleted."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from smoke_windows import application_window_exists

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from image_motion_tool import APP_VERSION


def main():
    if os.name != "nt":
        raise RuntimeError("Frozen restart validation requires Windows")
    with tempfile.TemporaryDirectory(prefix="imt-restart-") as directory:
        work = Path(directory)
        subprocess.run([
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--onefile", "--windowed", "--noupx", "--name", "UpdaterRestartTest",
            "--paths", str(ROOT), "--distpath", str(work / "dist"),
            "--workpath", str(work / "build"), "--specpath", str(work),
            str(ROOT / "scripts" / "frozen_restart_harness.py"),
        ], check=True, cwd=ROOT)
        installed = work / "UpdaterRestartTest.exe"
        shutil.copy2(work / "dist" / installed.name, installed)
        shutil.copy2(ROOT / "dist" / "ImageMotionTool.exe", work / "replacement.exe")
        env = dict(os.environ, TEMP=str(work), TMP=str(work))
        process = subprocess.Popen([str(installed), str(work)], cwd=work, env=env)
        try:
            assert process.wait(timeout=90) == 0, "Original frozen updater failed"
            old = Path(work.joinpath("old-extraction.txt").read_text(encoding="utf-8"))
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                extractions = [p for p in work.glob("_MEI*") if p != old]
                if (not old.exists() and extractions
                        and any((p / "python312.dll").is_file() and
                                (p / "ffmpeg.exe").is_file() for p in extractions)
                        and application_window_exists(APP_VERSION)):
                    assert not (work / "replacement.exe").exists(), "Replacement not moved"
                    assert installed.stat().st_size == (ROOT / "dist" / "ImageMotionTool.exe").stat().st_size
                    print("PASS: frozen updater replaced EXE; old extraction deleted; new GUI, Python and FFmpeg ready")
                    return
                time.sleep(0.5)
            raise RuntimeError("Updated EXE did not restart with independent Python/FFmpeg extraction")
        finally:
            subprocess.run(["taskkill", "/IM", installed.name, "/T", "/F"],
                           capture_output=True, check=False)
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"::error::{type(exc).__name__}: {exc}", flush=True)
        raise
