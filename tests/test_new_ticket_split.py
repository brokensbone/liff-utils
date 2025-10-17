
import unittest
import os
import json
import datetime
from unittest.mock import patch, mock_open
import sys

sys.path.append(".")

from new_ticket_split import (
    load_schedules,
    parse_film_details,
    find_owner,
    process_pdfs,
)

class TestTicketSplit(unittest.TestCase):
    def setUp(self):
        self.schedules_dir = "tests/fixtures/schedules"
        self.in_dir = "tests/fixtures/in"
        self.out_dir = "tests/fixtures/out"
        self.pdf_pages_dir = "tests/fixtures/pdf_pages"
        os.makedirs(self.schedules_dir, exist_ok=True)
        os.makedirs(self.in_dir, exist_ok=True)
        os.makedirs(self.out_dir, exist_ok=True)
        os.makedirs(self.pdf_pages_dir, exist_ok=True)

        with open(os.path.join(self.pdf_pages_dir, "known_film.txt"), "w") as f:
            f.write("""Please have this e-ticket with you –
either to show on your mobile phone or printed out.
Tickets sold subject to Terms and Conditions which can be viewed at the venue’s website.
leedstickethub.co.uk • 0113 376 0318
Order No:
Row: Seat:
Test Film
LIFF 2025
Test Venue
The Light, The Headrow, LS1 8TL

Standard
LIFF Explorer
£0.00
Mr. Edward Salkeld
1044585
Screen 7
H
4
26 October 2025
6:00 PM
""")
        with open(os.path.join(self.pdf_pages_dir, "unknown_film.txt"), "w") as f:
            f.write("""Please have this e-ticket with you –
either to show on your mobile phone or printed out.
Tickets sold subject to Terms and Conditions which can be viewed at the venue’s website.
leedstickethub.co.uk • 0113 376 0318
Order No:
Row: Seat:
Unknown Film
LIFF 2025
Test Venue
The Light, The Headrow, LS1 8TL

Standard
LIFF Explorer
£0.00
Mr. Edward Salkeld
1044585
Screen 7
H
4
28 October 2025
10:00 PM
""")

        self.edward_schedule = {
            "locations": [
                {
                    "name": "Test Venue",
                    "events": [
                        {
                            "name": "Test Film",
                            "start": "2025-10-26T18:00:00",
                        }
                    ],
                }
            ]
        }
        self.hannah_schedule = {
            "locations": [
                {
                    "name": "Test Venue",
                    "events": [
                        {
                            "name": "Another Film",
                            "start": "2025-10-27T20:00:00",
                        }
                    ],
                }
            ]
        }

        with open(os.path.join(self.schedules_dir, "edward.json"), "w") as f:
            json.dump(self.edward_schedule, f)
        with open(os.path.join(self.schedules_dir, "hannah.json"), "w") as f:
            json.dump(self.hannah_schedule, f)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.schedules_dir)
        shutil.rmtree(self.in_dir)
        shutil.rmtree(self.out_dir)
        shutil.rmtree(self.pdf_pages_dir)

    def test_load_schedules(self):
        schedules = load_schedules(self.schedules_dir)
        self.assertIn("edward", schedules)
        self.assertIn("hannah", schedules)
        self.assertEqual(len(schedules["edward"]["locations"]), 1)
        self.assertEqual(len(schedules["hannah"]["locations"]), 1)

    def test_parse_film_details(self):
        with open(os.path.join(self.pdf_pages_dir, "known_film.txt"), "r") as f:
            page_text = f.read()
        film_name, film_place, film_date, film_time = parse_film_details(page_text)
        self.assertEqual(film_name, "Test Film")
        self.assertEqual(film_place, "The Light, The Headrow, LS1 8TL")
        self.assertEqual(film_date, datetime.datetime(2025, 10, 26))
        self.assertEqual(film_time, datetime.time(18, 0))

    def test_find_owner_removes_event(self):
        schedules = load_schedules(self.schedules_dir)
        owner, schedules = find_owner(
            schedules,
            "Test Film",
            "Test Venue",
            datetime.datetime(2025, 10, 26),
            datetime.time(18, 0),
        )
        self.assertEqual(owner, "edward")
        self.assertEqual(len(schedules["edward"]["locations"][0]["events"]), 0)

    def test_process_pdfs(self):
        import pypdf

        # Create a dummy PDF for a known film
        pdf_path = os.path.join(self.in_dir, "test.pdf")
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=300, height=500)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        # Create a dummy PDF for an unknown film
        pdf_path_unknown = os.path.join(self.in_dir, "unknown.pdf")
        writer_unknown = pypdf.PdfWriter()
        writer_unknown.add_blank_page(width=300, height=500)
        with open(pdf_path_unknown, "wb") as f:
            writer_unknown.write(f)

        with open(os.path.join(self.pdf_pages_dir, "known_film.txt"), "r") as f:
            known_film_text = f.read()
        with open(os.path.join(self.pdf_pages_dir, "unknown_film.txt"), "r") as f:
            unknown_film_text = f.read()

        def mock_extract_text_known(self):
            return known_film_text

        def mock_extract_text_unknown(self):
            return unknown_film_text

        with patch("os.listdir") as mock_listdir:
            mock_listdir.return_value = ["test.pdf", "unknown.pdf"]
            with patch("pypdf.PdfReader") as mock_reader:
                mock_page_known = unittest.mock.MagicMock()
                mock_page_known.extract_text.side_effect = [known_film_text]
                mock_page_unknown = unittest.mock.MagicMock()
                mock_page_unknown.extract_text.side_effect = [unknown_film_text]
                mock_reader.return_value.pages = [mock_page_known, mock_page_unknown]
                schedules = load_schedules(self.schedules_dir)
                process_pdfs(self.in_dir, self.out_dir, schedules)

        expected_path = os.path.join(
            self.out_dir, "edward", "20251026-1800-Test Film.pdf"
        )
        self.assertTrue(os.path.exists(expected_path))

        expected_unknown_path = os.path.join(
            self.out_dir, "unknown", "20251028-2200-Unknown Film.pdf"
        )
        self.assertTrue(os.path.exists(expected_unknown_path))














if __name__ == "__main__":
    unittest.main()
