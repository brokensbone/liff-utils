import contextlib
import datetime
import importlib.util
import json
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ticket_split", ROOT / "ticket-split.py")
ticket_split = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ticket_split)


def ticket_lines(title, venue, date, time):
    # Mirrors the line order pypdf extracts from real LIFF e-tickets
    return [
        "Please have this e-ticket with you –",
        "either to show on your mobile phone or printed out.",
        "Tickets sold subject to Terms and Conditions.",
        "leedstickethub.co.uk",
        "Order No:",
        "Row: Seat:",
        title,
        "LIFF 2026",
        venue,
        "The Headrow, LS1 8TL",
        " ",
        "Standard Seating",
        "LIFF Explorer",
        "£0.00",
        "Test Person",
        "1000001",
        "Screen 12",
        "G",
        "9",
        date,
        time,
    ]


def write_ticket_pdf(path, tickets):
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    for lines in tickets:
        page = writer.add_blank_page(595, 842)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        ops = ["BT", "/F1 10 Tf", "40 800 Td"]
        for line in lines:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(")
            escaped = escaped.replace(")", "\\)")
            ops += [f"({escaped}) Tj", "0 -20 Td"]
        ops.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(ops).encode("cp1252"))
        page.replace_contents(stream)
    with open(path, "wb") as f:
        writer.write(f)


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

    def test_cli_splits_pdf_pages_into_owner_folders(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "ticket-split"
            for name in ("in", "out", "schedules"):
                (root / name).mkdir(parents=True)
            stale = root / "out" / "edward" / "01" / "old ticket.pdf"
            stale.parent.mkdir(parents=True)
            stale.write_bytes(b"stale")
            write_ticket_pdf(
                root / "in" / "order.pdf",
                [
                    ticket_lines(
                        "Mouse", "Vue -  The Light", "29 October 2026", "5:45 PM"
                    ),
                    ticket_lines(
                        "Filipiñana (Restored)",
                        "Hyde Park",
                        "07 November 2026",
                        "8:30 AM",
                    ),
                    ticket_lines(
                        "Bonus Film", "Cottage Road", "29 October 2026", "9:00 PM"
                    ),
                ],
            )
            (root / "in" / "notes.txt").write_text("ignored")
            schedule = {
                "locations": [
                    {
                        "events": [
                            {"name": "Mouse", "start": "2026-10-29 17:45"},
                            {
                                "name": "Filipiñana (Restored)",
                                "start": "2026-11-07 08:30",
                            },
                            {"name": "Sold Out", "start": "2026-11-14 12:45"},
                        ]
                    }
                ]
            }
            (root / "schedules" / "edward.json").write_text(json.dumps(schedule))

            with (
                contextlib.chdir(temp),
                patch("sys.argv", ["ticket-split.py"]),
                self.assertLogs(level="WARNING") as logs,
            ):
                runpy.run_path(str(ROOT / "ticket-split.py"), run_name="__main__")

            written = sorted(
                str(path.relative_to(root / "out"))
                for path in (root / "out").rglob("*.pdf")
            )
            self.assertEqual(
                written,
                [
                    "edward/07/0830 Filipiñana (Restored) (Hyde Park).pdf",
                    "edward/29/1745 Mouse (Vue -  The Light).pdf",
                    "unknown/29/2100 Bonus Film (Cottage Road).pdf",
                ],
            )
            for path, title in zip(
                written, ["Filipiñana", "Mouse", "Bonus Film"], strict=True
            ):
                pages = PdfReader(root / "out" / path).pages
                self.assertEqual(len(pages), 1)
                self.assertIn(title, pages[0].extract_text())
            self.assertEqual(
                logs.output,
                ["WARNING:root:edward is missing Sold Out at 2026-11-14 12:45"],
            )
