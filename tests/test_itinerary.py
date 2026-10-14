import json
from datetime import datetime, timedelta

import pytest

from itinerary import PlanningRules, Screening, incompatible, load_highlights, solve


def screening(title, start, end, venue="Vue in the Light, Screen 7", film=None):
    return Screening(
        film=film or title,
        title=title,
        start=datetime.fromisoformat(f"2026-11-01 {start}"),
        end=datetime.fromisoformat(f"2026-11-01 {end}"),
        venue=venue,
        url=f"https://example.com/{film or title}",
    )


def test_solver_chooses_repeated_film_showing_that_fits_both_others():
    screenings = [
        screening("A", "10:00", "11:00"),
        screening("B", "10:30", "11:30"),
        screening("B", "12:00", "13:00"),
        screening("C", "11:00", "12:00"),
    ]
    chosen = solve(screenings)
    assert {item.film for item in chosen} == {"A", "B", "C"}
    assert [item.start.hour for item in chosen if item.film == "B"] == [12]


def test_transfer_applies_between_buildings_but_not_screens():
    vue_7 = screening("A", "10:00", "11:00")
    vue_12 = screening("B", "11:05", "12:00", "Vue in the Light, Screen 12")
    cottage = screening("C", "11:05", "12:00", "Cottage Road Cinema")
    assert not incompatible(vue_7, vue_12, timedelta(minutes=20))
    assert incompatible(vue_7, cottage, timedelta(minutes=20))


def test_unavailability_and_hyde_park_transfer_rules():
    rules = PlanningRules(
        unavailable=((datetime(2026, 11, 1, 9, 0), datetime(2026, 11, 1, 10, 30)),),
        venue_transfer_minutes={"Hyde Park Picture House": 60},
    )
    early = screening("A", "10:00", "11:00")
    late = screening("A", "12:00", "13:00")
    hyde = screening("B", "13:30", "14:30", "Hyde Park Picture House, Screen 1")
    hyde_later = screening("B", "14:00", "15:00", "Hyde Park Picture House, Screen 1")
    assert not incompatible(late, hyde, timedelta(minutes=20))
    assert incompatible(late, hyde, timedelta(minutes=20), rules.venue_transfer_minutes)
    chosen = solve([early, late, hyde, hyde_later], 20, rules)
    assert {item.title for item in chosen} == {
        "A",
        "B",
    }
    assert next(item for item in chosen if item.title == "B").start.hour == 14
    assert solve([early], 20, rules) == []


def test_only_highlighted_events_are_loaded(tmp_path):
    path = tmp_path / "highlights.json"
    path.write_text(
        json.dumps(
            {
                "gets": {"hl1": ["film01"]},
                "locations": [
                    {
                        "name": "Vue in the Light, Screen 7",
                        "events": [
                            {
                                "short": "film01(1)",
                                "hls": "1",
                                "name": "Film 1",
                                "start": "2026-11-01 10:00",
                                "end": "2026-11-01 11:00",
                                "url": "https://example.com/film1",
                            },
                            {
                                "short": "film02(1)",
                                "hls": "",
                                "name": "Film 2",
                                "start": "2026-11-01 11:00",
                                "end": "2026-11-01 12:00",
                                "url": "https://example.com/film2",
                            },
                        ],
                    }
                ],
            }
        )
    )
    assert [item.title for item in load_highlights(path)] == ["Film 1"]
    with pytest.raises(ValueError, match="Highlighted films have no screenings"):
        path.write_text(path.read_text().replace('"hls": "1"', '"hls": ""'))
        load_highlights(path)
