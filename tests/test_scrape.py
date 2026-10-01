import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
import scrape


ROOT = Path(__file__).resolve().parents[1]
YEAR_DIR = ROOT / "2026"


def payloads(filename, url):
    return [
        json.loads(line.removeprefix("act = "))
        for line in scrape.parse_film((YEAR_DIR / filename).read_bytes(), url)
    ]


class TestScrape(unittest.TestCase):
    def test_index_extraction_and_saved_film_list(self):
        html = """
        <a class="desc" href="/whats-on/preview"><h3 class="title">LIFF 2026 Programme Preview</h3></a>
        <a class="desc" href="/whats-on/mouse-sbj2"><h3 class="title">Mouse</h3></a>
        <a class="desc" href="/whats-on/mouse-sbj2"><h3 class="title">Mouse</h3></a>
        """
        entries = scrape.index_entries(html)
        self.assertEqual(entries, [
            {"title": "LIFF 2026 Programme Preview", "url": "https://www.leedsfilm.com/whats-on/preview"},
            {"title": "Mouse", "url": "https://www.leedsfilm.com/whats-on/mouse-sbj2"},
        ])
        films = json.loads((YEAR_DIR / "films.json").read_text())
        self.assertEqual(len(films), 152)
        self.assertEqual(len({item["url"] for item in films}), 152)
        self.assertNotIn("LIFF 2026 Programme Preview", [item["title"] for item in films])

    def test_three_live_film_pages(self):
        cases = [
            ("pan-s-labyrinth-20th-anniversary-4k-restoration-7nl8", "Pan's Labyrinth (20th Anniversary 4K Restoration)", 2, "2026-10-29 15:30", "2026-10-29 17:28", "Vue in the Light, Screen 7"),
            ("iron-boy-n31f", "Iron Boy", 3, "2026-10-29 15:45", "2026-10-29 17:15", "Vue in the Light, Screen 12"),
            ("mouse-sbj2", "Mouse", 4, "2026-10-29 17:45", "2026-10-29 19:45", "Hyde Park Picture House, Screen 1"),
        ]
        for slug, title, count, start, end, venue in cases:
            with self.subTest(title=title):
                url = f"https://www.leedsfilm.com/whats-on/{slug}"
                rows = payloads(f"{slug}.html", url)
                self.assertEqual(len(rows), count)
                self.assertEqual(rows[0]["act"], title)
                self.assertEqual(rows[0]["start"], start)
                self.assertEqual(rows[0]["end"], end)
                self.assertEqual(rows[0]["stage"], venue)
                self.assertTrue(rows[0]["blurb"])
                self.assertTrue(all(row["url"] == url for row in rows))
        iron_boy = payloads("iron-boy-n31f.html", "https://www.leedsfilm.com/whats-on/iron-boy-n31f")
        self.assertEqual(iron_boy[-1]["stage"], "Cottage Road Cinema")

    @patch("scrape.fetch")
    def test_retrieve_film_uses_cache(self, fetch):
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE cache (url TEXT PRIMARY KEY, html BLOB)")
            db.execute("INSERT INTO cache VALUES (?, ?)", ("https://example.com/film", b"saved"))
            self.assertEqual(scrape.retrieve_film(db, "https://example.com/film"), b"saved")
        fetch.assert_not_called()

    @patch("scrape.time.sleep")
    @patch("scrape.fetch", return_value=b"<html>downloaded</html>")
    def test_download_missing_only_fetches_uncached_pages(self, fetch, sleep):
        films = [
            {"url": "https://example.com/cached"},
            {"url": "https://example.com/missing"},
        ]
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE cache (url TEXT PRIMARY KEY, html BLOB)")
            db.execute("INSERT INTO cache VALUES (?, ?)", (films[0]["url"], b"saved"))
            self.assertEqual(scrape.download_missing(db, films), 1)
            self.assertEqual(scrape.download_missing(db, films), 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM cache").fetchone()[0], 2)
        fetch.assert_called_once_with(films[1]["url"])
        sleep.assert_not_called()

    def test_single_screening_without_a_total_runtime(self):
        html = """
        <div class="desc"><h1>Short Film Competition</h1></div>
        <div class="desc1"><p>First | 12 mins</p><p>Second | 18 mins</p></div>
        <div class="top-date"><span class="start">Sat 31 Oct</span><span class="time">- 13:15</span></div>
        <div class="location">Vue in the Light, Leeds</div><div class="venue">Screen 11</div>
        """
        review = []
        row = json.loads(scrape.parse_film(html, "https://example.com/shorts", review, marker="NOTD")[0][6:])
        self.assertEqual((row["start"], row["end"]), ("2026-10-31 13:15", "2026-10-31 13:45"))
        self.assertEqual(row["stage"], "Vue in the Light, Screen 11")
        self.assertEqual(row["act"], "NOTD: Short Film Competition")
        self.assertEqual(review[0]["minutes"], 30)

    def test_marathon_config_labels_four_films_in_each_group(self):
        parents, labels = scrape.marathon_labels(YEAR_DIR)
        self.assertEqual(len(parents), 2)
        self.assertEqual(list(labels.values()).count("DOTD"), 4)
        self.assertEqual(list(labels.values()).count("NOTD"), 4)

    def test_explicit_runtime_override_is_recorded_for_review(self):
        html = """
        <div class="desc"><h1>Unscheduled Event</h1></div>
        <div class="top-date"><span class="start">Wed 4 Nov</span><span class="time">- 18:00</span></div>
        <div class="location">Leeds City Library</div><div class="venue">Screening Room</div>
        """
        url = "https://example.com/event"
        review = []
        row = json.loads(scrape.parse_film(
            html, url, review, {url: {"minutes": 90, "reason": "Provisional estimate"}}
        )[0][6:])
        self.assertEqual(row["end"], "2026-11-04 19:30")
        self.assertEqual(review[0]["reason"], "Provisional estimate")

    @patch("scrape.requests.get")
    def test_fetch_stops_on_rate_limit(self, get):
        response = requests.Response()
        response.status_code = 429
        response.url = "https://example.com/rate-limited"
        get.return_value = response
        with self.assertRaises(requests.HTTPError):
            scrape.fetch(response.url)
        get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
