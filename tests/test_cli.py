import json
from unittest.mock import patch

import clashfinder_highlight
import itinerary
import itinerary_calendar

VUE = "Vue in the Light, Screen 7"
HYDE_PARK = "Hyde Park Picture House, Screen 1"


def event(name, start, end, hls, short):
    return {
        "name": name,
        "start": f"2026-{start}",
        "end": f"2026-{end}",
        "hls": hls,
        "short": short,
        "url": f"https://example.com/{name.lower()}",
    }


def run_main(module, *args):
    with patch("sys.argv", [module.__name__, *map(str, args)]):
        module.main()


def test_plan_highlight_and_calendar_scripts_work_together(tmp_path, capsys):
    export = tmp_path / "export.json"
    export.write_text(
        json.dumps(
            {
                "id": "liff26",
                "gets": ["hl1", "hl2", "hl3"],
                "locations": [
                    {
                        "name": VUE,
                        "events": [
                            event("Alpha", "10-30 18:00", "10-30 19:30", "3", "a(1)"),
                            event("Beta", "10-30 18:30", "10-30 20:00", "1", "b(1)"),
                            event("Beta", "10-31 14:00", "10-31 15:30", "1", "b(2)"),
                        ],
                    },
                    {
                        "name": HYDE_PARK,
                        "events": [
                            event("Gamma", "10-31 15:00", "10-31 16:30", "2", "c(1)"),
                            event("Gamma", "11-01 11:00", "11-01 12:30", "2", "c(2)"),
                        ],
                    },
                ],
            }
        )
    )
    delta_url = "https://example.com/delta"
    clashfinder = tmp_path / "clashfinder"
    clashfinder.write_text(
        "act = "
        + json.dumps(
            {
                "start": "2026-11-01 20:00",
                "end": "2026-11-01 21:30",
                "stage": "Cottage Road Cinema",
                "act": "Delta",
                "url": delta_url,
            }
        )
        + "\n"
    )
    rules = tmp_path / "rules.json"
    rules.write_text(
        json.dumps(
            {
                "unavailable": [
                    {"start": "2026-11-01T10:00", "end": "2026-11-01T13:00"}
                ],
                "venue_transfer_minutes": {"Cottage Road Cinema": 40},
            }
        )
    )
    scenario = tmp_path / "scenario.json"
    scenario.write_text(
        json.dumps(
            {
                "highlight_points": {"3": 4},
                "additional_films": {delta_url: 1},
                "preferred_showings": {"https://example.com/gamma": "2026-10-31 15:00"},
            }
        )
    )
    plans = tmp_path / "itineraries"
    plan = plans / "plan.md"

    run_main(
        itinerary,
        export,
        "--transfer-minutes",
        20,
        "--rules",
        rules,
        "--scenario",
        scenario,
        "--clashfinder",
        clashfinder,
        "--output",
        plan,
    )

    text = plan.read_text()
    assert text.startswith("# Highlighted film itinerary: 7 of 8 points")
    scheduled, unscheduled = text.split("## Unscheduled highlights")
    for title in ("Alpha", "Gamma", "Delta"):
        assert f"[{title}]" in scheduled
    assert "[Beta]" in unscheduled
    assert "Wrote" in capsys.readouterr().out

    overrides = tmp_path / "overrides.json"
    overrides.write_text(
        json.dumps(
            [
                {
                    "url": delta_url,
                    "start": "2026-11-01 20:00",
                    "venue": "Cottage Road Cinema",
                    "short": "d(1)",
                }
            ]
        )
    )
    script = tmp_path / "set4.js"
    run_main(
        clashfinder_highlight,
        plan,
        export,
        "--year",
        2026,
        "--overrides",
        overrides,
        "--output",
        script,
    )
    assert 'const desired = ["a(1)", "c(1)", "d(1)"]' in script.read_text()

    calendar = tmp_path / "calendar.html"
    run_main(itinerary_calendar, 2026, "--directory", plans, "--output", calendar)
    page = calendar.read_text()
    assert "LIFF 2026" in page
    assert "https://example.com/gamma" in page
