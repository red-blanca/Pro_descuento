from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
FACEBOOK_DIR = ROOT / "facebook_marketplace"
if str(FACEBOOK_DIR) not in sys.path:
    sys.path.insert(0, str(FACEBOOK_DIR))

import facebook_api as fb


class FacebookLocationFilterTest(unittest.TestCase):
    def test_rejects_explicit_unresolved_foreign_location(self):
        def fake_geocode(location: str, country_code: str = "CL"):
            raise RuntimeError(f"not in {country_code}: {location}")

        items = [
            {"title": "Hacha", "location": "Stockton, CA"},
            {"title": "Hacha local", "location": "Curico, Maule"},
            {"title": "Hacha sin ubicacion", "location": ""},
        ]

        with patch.object(fb, "geocode_location", fake_geocode):
            filtered = fb.apply_location_filter(
                items,
                fb.CURICO_LATITUDE,
                fb.CURICO_LONGITUDE,
                35,
                "CL",
                "Curico, Maule, Chile",
                include_talca=False,
            )

        self.assertEqual(
            [item["title"] for item in filtered],
            ["Hacha local", "Hacha sin ubicacion"],
        )


if __name__ == "__main__":
    unittest.main()
