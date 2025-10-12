
import unittest
import sqlite3
from unittest.mock import patch, mock_open
from bs4 import BeautifulSoup
import sys
sys.path.append('.')

import scrape

class TestScrape(unittest.TestCase):
    def setUp(self):
        self.cx = sqlite3.connect(":memory:")
        self.cx.execute("CREATE TABLE cache (url TEXT, html TEXT)")

    def tearDown(self):
        self.cx.close()

    def test_get_main_page(self):
        with patch("requests.get") as mock_get:
            with open("tests/fixtures/allfilm-1.html", "r") as f:
                mock_get.return_value.text = f.read()
                mock_get.return_value.status_code = 200
            page = scrape.get_main_page(1)
            self.assertEqual(page.status_code, 200)

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
        mock_output_file.write.assert_called()

if __name__ == "__main__":
    unittest.main()
