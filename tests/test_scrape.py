import unittest
import sqlite3
from unittest.mock import patch, mock_open
from bs4 import BeautifulSoup
import sys

sys.path.append(".")

import scrape


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
