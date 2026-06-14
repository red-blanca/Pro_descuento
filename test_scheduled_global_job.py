import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import scheduled_global_job


class ScheduledGlobalJobTests(unittest.TestCase):
    def test_writes_only_two_combined_json_files(self) -> None:
        config = {
            "query": "notebook",
            "groups": {
                "usado": {"sources": ["mercadolibre"], "mercadolibre_condition": "used"},
                "nuevo": {"sources": ["mercadolibre"], "mercadolibre_condition": "new"},
            },
        }
        results = [
            {
                "created_at": "2026-06-14T10:00:00",
                "query": "notebook",
                "total_count": 1,
                "elapsed_seconds": 1,
                "runs": [{"source": "mercadolibre", "ok": True, "count": 1}],
                "items": [{"source": "mercadolibre", "title": "Notebook usado"}],
            },
            {
                "created_at": "2026-06-14T10:00:01",
                "query": "notebook",
                "total_count": 1,
                "elapsed_seconds": 1,
                "runs": [{"source": "mercadolibre", "ok": True, "count": 1}],
                "items": [{"source": "mercadolibre", "title": "Notebook nuevo"}],
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "searches.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            with patch.object(scheduled_global_job.global_search, "run_global_search", side_effect=results) as search:
                written = scheduled_global_job.run(config_path, root / "results")

            self.assertEqual(2, len(written))
            self.assertEqual({"usado", "nuevo"}, {path.parent.name for path in written})
            self.assertEqual(2, len(list((root / "results").rglob("*.json"))))
            self.assertEqual(["used", "new"], [
                call.args[0]["mercadolibre_condition"] for call in search.call_args_list
            ])
            self.assertEqual("Notebook usado", json.loads(written[0].read_text())["items"][0]["title"])
            summary = (root / "results" / "summary.md").read_text(encoding="utf-8")
            self.assertIn("Failed store runs: **0**", summary)
            self.assertIn("| mercadolibre | OK | 1 |", summary)


if __name__ == "__main__":
    unittest.main()
