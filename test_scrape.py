
import unittest
import sqlite3
from unittest.mock import MagicMock, patch, mock_open
from bs4 import BeautifulSoup

import scrape

class TestScrape(unittest.TestCase):
    def setUp(self):
        self.cx = sqlite3.connect(":memory:")
        self.cx.execute("CREATE TABLE cache (url TEXT, html TEXT)")

    def tearDown(self):
        self.cx.close()

    def test_extract_venue(self):
        html = """
        <div class="location">Everyman Cinema Leeds, Leeds</div>
        <div class="venue">Screen 1</div>
        """
        book_row = BeautifulSoup(html, "html.parser")
        venue = scrape.extract_venue(book_row)
        self.assertEqual(venue, "Everyman Cinema Screen 1")

    def test_build_date_range(self):
        minutes = 90
        date_text = "Fri 6 Nov"
        time_text = "13:15"
        parsed_date, parsed_end = scrape.build_date_range(minutes, date_text, time_text)
        self.assertEqual(parsed_date.strftime(scrape.DATE_FORMAT_OUT), "2025-11-06 13:15")
        self.assertEqual(parsed_end.strftime(scrape.DATE_FORMAT_OUT), "2025-11-06 14:45")

    def test_build_output(self):
        url = "http://example.com"
        title = "My Film"
        desc = "A great film"
        parsed_date = MagicMock()
        parsed_date.strftime.return_value = "2025-01-01 12:00"
        parsed_end = MagicMock()
        parsed_end.strftime.return_value = "2025-01-01 13:30"
        venue = "My Venue"
        output = scrape.build_output(url, title, desc, parsed_date, parsed_end, venue)
        self.assertIn('"act": "My Film"', output)
        self.assertIn('"stage": "My Venue"', output)

    @patch("scrape.retrieve_film")
    def test_handle_film(self, mock_retrieve_film):
        with patch("builtins.open", mock_open()) as mock_file:
            # Create a mock film page
            with open("film.html", "wb") as f:
                f.write(b'')

            with open("film.html", "rb") as f:
                mock_retrieve_film.return_value = f.read()

            # Call the function
            scrape.handle_film("http://example.com", self.cx)

            # Check that the output file was written to
            mock_file().write.assert_called()

if __name__ == "__main__":
    unittest.main()
