import unittest
import sqlite3
import datetime
import json
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup
import sys

sys.path.append(".")

import scrape


def clashfinder_payload(output_line):
    return json.loads(output_line.removeprefix("act = "))


class TestScrape(unittest.TestCase):
    def setUp(self):
        self.cx = sqlite3.connect(":memory:")
        self.cx.execute("CREATE TABLE cache (url TEXT, html TEXT)")

    def tearDown(self):
        self.cx.close()

    def test_get_main_page(self):
        with open("tests/fixtures/allfilm-1.html", "r") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        film_links = soup.find_all("a", class_="desc")
        self.assertEqual(len(film_links), 54)

    def test_extract_venue(self):
        html = """
        <div class="location">Everyman Cinema Leeds, Leeds</div>
        <div class="venue">Screen 1</div>
        """
        book_row = BeautifulSoup(html, "html.parser")
        venue = scrape.extract_venue(book_row)
        self.assertEqual(venue, "Everyman Cinema Screen 1")

    def test_build_date_range_crosses_midnight(self):
        parsed_start, parsed_end = scrape.build_date_range(95, "Fri 7 Nov", "23:30")

        self.assertEqual(parsed_start, datetime.datetime(2025, 11, 7, 23, 30))
        self.assertEqual(parsed_end, datetime.datetime(2025, 11, 8, 1, 5))

    @patch("scrape.requests.get")
    def test_retrieve_film_uses_cached_html(self, mock_get):
        url = "https://www.leedsfilm.com/whats-on/cached-film"
        html = "<html>cached</html>"
        self.cx.execute("INSERT INTO cache VALUES (?, ?)", (url, html))

        self.assertEqual(scrape.retrieve_film(self.cx, url), html)
        mock_get.assert_not_called()

    @patch("scrape.requests.get")
    def test_retrieve_film_stores_downloaded_html(self, mock_get):
        url = "https://www.leedsfilm.com/whats-on/new-film"
        mock_get.return_value = Mock(status_code=200, content=b"<html>downloaded</html>")

        self.assertEqual(scrape.retrieve_film(self.cx, url), b"<html>downloaded</html>")
        mock_get.assert_called_once_with(url)

        row = self.cx.execute("SELECT html FROM cache WHERE url = ?", (url,)).fetchone()
        self.assertEqual(row[0], b"<html>downloaded</html>")

    @patch("scrape.output_file")
    def test_handle_film_without_runtime_uses_zero_duration(self, mock_output_file):
        url = "https://www.leedsfilm.com/whats-on/no-runtime"
        html = """
        <div class="desc"><h1>No Runtime Film</h1></div>
        <div class="desc1"><p>One line.</p></div>
        <ul id="sub-show-list1">
            <li>
                <div class="date"><div class="start">Sat 8 Nov</div></div>
                <div class="time"><span class="start">10:45</span></div>
                <div class="location">Hyde Park Picture House, Leeds</div>
                <div class="venue">Screen 1</div>
            </li>
        </ul>
        """
        self.cx.execute("INSERT INTO cache VALUES (?, ?)", (url, html))

        scrape.handle_film(url, self.cx)

        mock_output_file.write.assert_called_once()
        payload = clashfinder_payload(mock_output_file.write.call_args[0][0].strip())
        self.assertEqual(payload["act"], "No Runtime Film")
        self.assertEqual(payload["stage"], "Hyde Park Picture House, Screen 1")
        self.assertEqual(payload["start"], "2025-11-08 10:45")
        self.assertEqual(payload["end"], "2025-11-08 10:45")

    @patch("scrape.output_file")
    def test_handle_film(self, mock_output_file):
        with open("tests/fixtures/bugonia.html", "r") as f:
            html = f.read()
        self.cx.execute("INSERT INTO cache VALUES (?, ?)", ("https://www.leedsfilm.com/whats-on/bugonia-fh1q", html))
        scrape.handle_film("https://www.leedsfilm.com/whats-on/bugonia-fh1q", self.cx)

        self.assertEqual(mock_output_file.write.call_count, 4)

        calls = mock_output_file.write.call_args_list

        first_call = calls[0][0][0]
        self.assertIn('"act": "Bugonia"', first_call)
        self.assertIn('"stage": "Vue in the Light, Screen 12"', first_call)
        self.assertIn('"start": "2025-10-30 20:30"', first_call)
        self.assertIn('"end": "2025-10-30 22:30"', first_call)

        second_call = calls[1][0][0]
        self.assertIn('"act": "Bugonia"', second_call)
        self.assertIn('"stage": "Vue in the Light, Screen 12"', second_call)
        self.assertIn('"start": "2025-10-31 18:00"', second_call)
        self.assertIn('"end": "2025-10-31 20:00"', second_call)

        third_call = calls[2][0][0]
        self.assertIn('"act": "Bugonia"', third_call)
        self.assertIn('"stage": "Vue in the Light, Screen 7"', third_call)
        self.assertIn('"start": "2025-11-03 18:00"', third_call)
        self.assertIn('"end": "2025-11-03 20:00"', third_call)

        fourth_call = calls[3][0][0]
        self.assertIn('"act": "Bugonia"', fourth_call)
        self.assertIn('"stage": "Vue in the Light, Screen 7"', fourth_call)
        self.assertIn('"start": "2025-11-04 16:00"', fourth_call)
        self.assertIn('"end": "2025-11-04 18:00"', fourth_call)


if __name__ == "__main__":
    unittest.main()
