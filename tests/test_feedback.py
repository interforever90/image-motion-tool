import io
import json
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from image_motion_tool import APP_VERSION, App


class Variable:
    def __init__(self, value):
        self.value = value
        self.history = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.history.append(value)


def make_app():
    app = App.__new__(App)
    app.duration = Variable("10")
    app.res = Variable("1920x1080")
    app.fps = Variable("30")
    app.progress = Variable(0)
    app.progress_text = Variable("0%")
    app.status = Variable("Pronto")
    app.cancel_event = threading.Event()
    app.current_process = None
    app.root = SimpleNamespace(after=lambda delay, callback: callback())
    app.filter = lambda effect: "unchanged-test-filter"
    app.ffmpeg = lambda: "ffmpeg.exe"
    app.update_button = Mock()
    app.update_check_running = False
    app.update_download_running = False
    return app


class FeedbackTests(unittest.TestCase):
    def test_stream_progress_and_completion(self):
        app = make_app()
        values = []
        process = Mock(stdout=iter([
            "out_time_us=N/A\n", "out_time_us=2000000\n",
            "out_time_us=2000000\n", "out_time_us=8000000\n",
            "out_time_us=10000000\n", "progress=end\n",
        ]))
        process.wait.return_value = 0
        with patch("image_motion_tool.subprocess.Popen", return_value=process):
            app.run_one("input.png", "output.mp4", "Zoom In", on_progress=values.append)
        self.assertEqual(values, [.2, .8, .99, 1.0])
        self.assertIsNone(app.current_process)

    def test_error_never_reports_complete(self):
        app = make_app()
        values = []
        process = Mock(stdout=iter(["out_time_us=8000000\n"]))
        process.wait.return_value = 1
        with patch("image_motion_tool.subprocess.Popen", return_value=process):
            with self.assertRaises(RuntimeError):
                app.run_one("input.png", "output.mp4", "Zoom In", on_progress=values.append)
        self.assertEqual(values, [.8])

    def test_cancel_never_reports_complete(self):
        app = make_app()
        app.cancel_event.set()
        values = []
        process = Mock(stdout=iter(["out_time_us=10000000\n"]))
        process.wait.return_value = 0
        with patch("image_motion_tool.subprocess.Popen", return_value=process):
            app.run_one("input.png", "output.mp4", "Zoom In", on_progress=values.append)
        process.terminate.assert_called_once()
        self.assertEqual(values, [])

    def test_batch_progress_includes_current_video(self):
        app = make_app()
        app.images = ["one.png", "two.png"]
        app.effect = Variable("Zoom In")
        app.outname = lambda *args: "output.mp4"
        def render(*args, on_progress):
            on_progress(.5)
            on_progress(1.0)
        app.run_one = render
        app._generate_worker()
        self.assertEqual(app.progress.history, [0, 25, 50, 50, 75, 100])
        self.assertEqual(app.progress_text.get(), "100%")
        self.assertTrue(app.status.get().startswith("Completato"))

    def test_silent_network_check_highlights_without_downloading(self):
        app = make_app()
        pending = queue.Queue()
        app.root.after = lambda delay, callback: pending.put(callback)
        data = {"version": "99.0", "download_url": "https://example.test/app.exe"}
        with patch("image_motion_tool.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(data).encode())), \
                patch("image_motion_tool.urllib.request.urlretrieve") as download, \
                patch("image_motion_tool.messagebox.askyesno") as prompt:
            app.check_update(silent=True)
            pending.get(timeout=5)()
            app.update_button.configure.assert_called_with(text="Aggiorna · V99.0", style="Primary.TButton")
            self.assertFalse(app.update_check_running)
            prompt.assert_not_called()
            download.assert_not_called()

    def test_current_version_restores_button(self):
        app = make_app()
        with patch("image_motion_tool.messagebox.showinfo") as prompt:
            app._update_checked({"version": APP_VERSION}, False, True)
            prompt.assert_not_called()
        app.update_button.configure.assert_called_with(text="Aggiornamenti", style="TButton")

    def test_offline_silent_check_has_no_popup(self):
        app = make_app()
        pending = queue.Queue()
        app.root.after = lambda delay, callback: pending.put(callback)
        with patch("image_motion_tool.urllib.request.urlopen", side_effect=OSError("offline")), \
                patch("image_motion_tool.messagebox.showerror") as error:
            app.check_update(silent=True)
            pending.get(timeout=5)()
            error.assert_not_called()
        self.assertFalse(app.update_check_running)
        app.update_button.configure.assert_not_called()

    def test_poll_repeats_every_thirty_minutes(self):
        app = make_app()
        app.check_update = Mock()
        app.root.after = Mock()
        app._poll_updates()
        app.check_update.assert_called_once_with(silent=True)
        app.root.after.assert_called_once_with(1_800_000, app._poll_updates)


if __name__ == "__main__":
    unittest.main()
