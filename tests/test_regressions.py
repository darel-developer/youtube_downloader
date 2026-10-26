import importlib.util
import os
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location("app_module", Path(__file__).resolve().parents[1] / "app.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class DownloadDirectoryTests(unittest.TestCase):
    def test_get_download_dir_prefers_machine_downloads(self):
        os.environ.pop("VERCEL", None)
        path = app.get_download_dir()
        self.assertEqual(path.name.lower(), "downloads")
        self.assertTrue(path.exists())


class GroqRequestTests(unittest.TestCase):
    def test_summary_uses_supported_groq_param(self):
        calls = {}

        class FakeCompletions:
            def create(self, **kwargs):
                calls.update(kwargs)
                return type(
                    "Response",
                    (),
                    {"choices": [type("Choice", (), {"message": type("Message", (), {"content": "Résumé de test"})()})()]},
                )()

        class FakeClient:
            chat = type("Chat", (), {"completions": FakeCompletions()})()

        original_client = app.client
        original_validate = app.validate_url
        original_extract = app.extract_subtitles

        try:
            app.client = FakeClient()
            app.validate_url = lambda url: True
            app.extract_subtitles = lambda video_url, work_id: "Texte de test pour le résumé."

            result = app.generate_summary("https://www.youtube.com/watch?v=test")
            self.assertEqual(result, "Résumé de test")
            self.assertIn("max_tokens", calls)
            self.assertNotIn("max_completion_tokens", calls)
        finally:
            app.client = original_client
            app.validate_url = original_validate
            app.extract_subtitles = original_extract


if __name__ == "__main__":
    unittest.main()
