import datetime
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ticket_split", ROOT / "ticket-split.py")
ticket_split = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ticket_split)


class TestTicketSplit(unittest.TestCase):
    def test_parse_ticket_fields(self):
        lines = [""] * 22
        lines[4] = "Order No:"
        lines[6] = "Mouse"
        lines[8] = "Vue"
        lines[19] = "29 October 2026"
        lines[20] = "05:45 PM"
        lines[21] = "footer text"

        self.assertEqual(
            ticket_split.parse_film(lines),
            [
                "Mouse",
                "Vue",
                datetime.datetime(2026, 10, 29),
                datetime.time(17, 45),
            ],
        )
        with self.assertRaises(ValueError):
            ticket_split.parse_film(lines[:10])

    def test_owner_requires_matching_title_and_start_time(self):
        task = ticket_split.Task()
        task.schedule_map = {
            "hannah": {
                "locations": [
                    {"events": [{"name": "Mouse", "start": "2026-10-29 18:00"}]}
                ]
            },
            "edward": {
                "locations": [
                    {"events": [{"name": " Mouse ", "start": "2026-10-29 17:45"}]}
                ]
            },
        }
        date = datetime.datetime(2026, 10, 29)
        time = datetime.time(17, 45)

        self.assertEqual(task.calculate_owner("MOUSE", "Vue", date, time), "edward")
        self.assertTrue(
            task.schedule_map["edward"]["locations"][0]["events"][0]["found"]
        )
        self.assertEqual(task.calculate_owner("MOUSE", "Vue", date, time), "unknown")

    def test_missing_schedules_does_not_delete_existing_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "out" / "edward" / "29" / "ticket.pdf"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"previous ticket")
            (root / "in").mkdir()
            with (
                patch.object(ticket_split, "DIRECTORY", str(root / "in")),
                patch.object(ticket_split, "OUTDIR", str(root / "out")),
                patch.object(
                    ticket_split, "SCHEDULES", str(root / "missing-schedules")
                ),
            ):
                with self.assertRaises(FileNotFoundError):
                    ticket_split.Task().run()
            self.assertEqual(output.read_bytes(), b"previous ticket")
