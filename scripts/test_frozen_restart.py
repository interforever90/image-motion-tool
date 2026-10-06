"""Verify replacement and restart after the old onefile extraction is deleted."""
import os
import ctypes
from ctypes import wintypes
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


def wait_for_updater_exit(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x100000 | 0x1000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:  # Process already gone.
            return
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        assert kernel.WaitForSingleObject(handle, 15000) == 0, "Updater command shell remained open"
        code = wintypes.DWORD()
        assert kernel.GetExitCodeProcess(handle, ctypes.byref(code)), "Cannot inspect updater exit"
        assert code.value == 0, f"Updater exited with error {code.value}"
    finally:
        kernel.CloseHandle(handle)


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
        # Also verify the updater releases its working directory on completion.
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
                    wait_for_updater_exit(int(work.joinpath("updater-pid.txt").read_text()))
                    assert not (work / "ImageMotionTool_apply_update.bat").exists(), "Updater BAT not removed"
                    print("PASS: frozen update restarted; independent runtime ready; BAT removed and command shell closed")
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
