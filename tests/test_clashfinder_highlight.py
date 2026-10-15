import json

import pytest

from clashfinder_highlight import render_script, scheduled_shorts


def test_highlight_script_matches_exact_occurrences_and_overrides(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text(
        "# Highlighted film itinerary: 6 of 6 points\n"
        "\n## Friday 6 November\n\n"
        "- 11:45–13:24 [Animation](https://example.com/animation) — Vue, Screen 7 (4 pts)\n"
        "- 18:00–19:30 [Feature](https://example.com/feature) — Everyman (2 pts)\n"
    )
    export = tmp_path / "export.json"
    export.write_text(
        json.dumps(
            {
                "id": "liff26",
                "locations": [
                    {
                        "name": "Everyman",
                        "events": [
                            {
                                "url": "https://example.com/feature",
                                "start": "2026-11-06 18:00",
                                "short": "featur(2)",
                            }
                        ],
                    }
                ],
            }
        )
    )
    overrides = tmp_path / "overrides.json"
    overrides.write_text(
        json.dumps(
            [
                {
                    "url": "https://example.com/animation",
                    "start": "2026-11-06 11:45",
                    "venue": "Vue, Screen 7",
                    "short": "animat(1)",
                }
            ]
        )
    )
    with pytest.raises(ValueError, match="No Clashfinder short ID"):
        scheduled_shorts(plan, export, 2026)
    festival, shorts = scheduled_shorts(plan, export, 2026, overrides)
    assert festival == "liff26"
    assert shorts == ["animat(1)", "featur(2)"]
    script = render_script(festival, shorts, 4, "Scheduled")
    assert 'const festival = "liff26"' in script
    assert 'const desired = ["animat(1)", "featur(2)"]' in script
