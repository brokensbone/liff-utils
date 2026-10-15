import json
from html.parser import HTMLParser

from itinerary_calendar import build_calendar, parse_itinerary


def test_calendar_parser_keeps_scheduled_screenings_only(tmp_path):
    plan = tmp_path / "trial.md"
    plan.write_text(
        "# Highlighted film itinerary: 4 of 5 points\n"
        "\n## Saturday 31 October\n\n"
        "- 20:30–22:16 [Ghost in the Cell](https://example.com/ghost) — Vue in the Light, Screen 11 (4 pts)\n"
        "\n## Unscheduled highlights (1)\n\n"
        "- [Another film](https://example.com/other)\n"
    )
    parsed = parse_itinerary(plan, 2026)
    assert parsed["summary"] == "4 of 5 points"
    assert parsed["events"] == [
        {
            "date": "2026-10-31",
            "start": "20:30",
            "end_date": "2026-10-31",
            "end": "22:16",
            "title": "Ghost in the Cell",
            "url": "https://example.com/ghost",
            "venue": "Vue in the Light, Screen 11",
            "points": 4,
        }
    ]


class _PlanDataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_data = False
        self.data = ""

    def handle_starttag(self, tag, attrs):
        self.in_data = tag == "script" and ("id", "plan-data") in attrs

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_data = False

    def handle_data(self, data):
        if self.in_data:
            self.data += data


def test_calendar_build_uses_requested_year_and_local_plans(tmp_path):
    (tmp_path / "my-plan.md").write_text(
        "# Highlighted film itinerary: 2 of 3 points\n"
        "\n## Sunday 31 October\n\n"
        "- 23:15–00:45 [Late Film](https://example.com/late) — Cinema (2 pts)\n"
    )
    output = build_calendar(tmp_path, 2027)
    page = output.read_text()
    parser = _PlanDataParser()
    parser.feed(page)
    data = json.loads(parser.data)
    assert "LIFF 2027" in page
    assert data["year"] == 2027
    assert data["default"] == "my-plan"
    assert data["plans"][0]["events"][0]["end_date"] == "2027-11-01"
