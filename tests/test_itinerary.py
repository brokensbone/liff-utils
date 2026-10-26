import json
from datetime import datetime, timedelta

import pytest

from itinerary import (
    PlanningRules,
    Screening,
    apply_preferred_showings,
    incompatible,
    load_extra_screenings,
    load_highlights,
    load_rules,
    render,
    solve,
)


def screening(
    title, start, end, venue="Vue in the Light, Screen 7", film=None, points=1
):
    return Screening(
        film=film or title,
        title=title,
        start=datetime.fromisoformat(f"2026-11-01 {start}"),
        end=datetime.fromisoformat(f"2026-11-01 {end}"),
        venue=venue,
        url=f"https://example.com/{film or title}",
        points=points,
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


def test_points_win_first_and_film_count_breaks_ties():
    a = screening("A", "10:00", "12:00", points=3)
    b = screening("B", "10:00", "11:00")
    c = screening("C", "11:00", "12:00")
    assert [item.title for item in solve([a, b, c])] == ["A"]
    a_tied = screening("A", "10:00", "12:00", points=2)
    assert {item.title for item in solve([a_tied, b, c])} == {"B", "C"}


def test_unscheduled_films_are_grouped_by_points():
    screenings = [
        screening("Low", "10:00", "11:00"),
        screening("High", "10:00", "11:00", points=3),
        screening("Medium", "10:00", "11:00", points=2),
    ]
    missing = render(screenings, [], 20).split("## Unscheduled highlights")[1]
    assert missing.index("### 3 points") < missing.index("### 2 points")
    assert missing.index("### 2 points") < missing.index("### 1 point")
    assert missing.index("High") < missing.index("Medium") < missing.index("Low")


def test_transfer_applies_between_buildings_but_not_screens():
    vue_7 = screening("A", "10:00", "11:00")
    vue_12 = screening("B", "11:05", "12:00", "Vue in the Light, Screen 12")
    cottage = screening("C", "11:05", "12:00", "Cottage Road Cinema")
    assert not incompatible(vue_7, vue_12, timedelta(minutes=20))
    assert incompatible(
        vue_7, vue_12, timedelta(minutes=20), minimum_gap=timedelta(minutes=20)
    )
    assert incompatible(vue_7, cottage, timedelta(minutes=20))


def test_solver_enforces_minimum_gap_within_one_cinema():
    first = screening("A", "18:00", "19:31", "Vue in the Light, Screen 7")
    second = screening("B", "19:45", "21:00", "Vue in the Light, Screen 12")
    assert len(solve([first, second], 20)) == 2
    assert len(solve([first, second], 20, PlanningRules(minimum_gap_minutes=20))) == 1


def test_solver_limits_screenings_per_day():
    films = [
        screening("A", "10:00", "11:00", points=1),
        screening("B", "12:00", "13:00", points=3),
        screening("C", "14:00", "15:00", points=2),
    ]
    chosen = solve(films, rules=PlanningRules(max_screenings_per_day=2))
    assert {item.title for item in chosen} == {"B", "C"}


def test_solver_limits_total_films_while_maximizing_points():
    films = [
        screening("A", "10:00", "11:00", points=1),
        screening("B", "12:00", "13:00", points=3),
        screening("C", "14:00", "15:00", points=2),
    ]
    chosen = solve(films, rules=PlanningRules(max_films=2))
    assert {item.title for item in chosen} == {"B", "C"}


def test_solver_excludes_named_venue():
    bradford = screening("A", "10:00", "11:00", "Pictureville, Bradford Screen 1")
    leeds = screening("B", "12:00", "13:00")
    chosen = solve(
        [bradford, leeds],
        rules=PlanningRules(excluded_venues=("Pictureville, Bradford",)),
    )
    assert [item.title for item in chosen] == ["B"]


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
    with pytest.raises(ValueError, match="No highlighted screenings found"):
        path.write_text(path.read_text().replace('"hls": "1"', '"hls": ""'))
        load_highlights(path)


def test_three_highlight_sets_become_points(tmp_path):
    path = tmp_path / "highlights.json"
    path.write_text(
        json.dumps(
            {
                "gets": {"hl1": [], "hl2": [], "hl3": []},
                "locations": [
                    {
                        "name": "Vue in the Light, Screen 7",
                        "events": [
                            {
                                "name": f"Film {points}",
                                "hls": str(points),
                                "start": "2026-11-01 10:00",
                                "end": "2026-11-01 11:00",
                                "url": f"https://example.com/{points}",
                            }
                            for points in (1, 2, 3)
                        ],
                    }
                ],
            }
        )
    )
    assert {item.title: item.points for item in load_highlights(path)} == {
        "Film 1": 1,
        "Film 2": 2,
        "Film 3": 3,
    }
    assert {
        item.title: item.points
        for item in load_highlights(path, {"1": 1, "2": 2, "3": 4})
    }["Film 3"] == 4


def test_scheduled_highlight_overlay_does_not_change_points(tmp_path):
    path = tmp_path / "highlights.json"
    path.write_text(
        json.dumps(
            {
                "gets": {"hl2": [], "hl4": []},
                "locations": [
                    {
                        "name": "Vue",
                        "events": [
                            {
                                "name": "Wanted",
                                "hls": "2 4",
                                "start": "2026-11-01 10:00",
                                "end": "2026-11-01 11:00",
                                "url": "https://example.com/wanted",
                            },
                            {
                                "name": "Scheduled only",
                                "hls": "4",
                                "start": "2026-11-01 12:00",
                                "end": "2026-11-01 13:00",
                                "url": "https://example.com/scheduled-only",
                            },
                        ],
                    }
                ],
            }
        )
    )
    assert [(item.title, item.points) for item in load_highlights(path)] == [
        ("Wanted", 2)
    ]


def test_additional_films_and_preferred_showing(tmp_path):
    path = tmp_path / "clashfinder"
    path.write_text(
        "act = "
        + json.dumps(
            {
                "act": "Animation",
                "url": "https://example.com/animation",
                "start": "2026-11-06 11:45",
                "end": "2026-11-06 13:24",
                "stage": "Vue, Screen 7",
            }
        )
        + "\nact = "
        + json.dumps(
            {
                "act": "Animation",
                "url": "https://example.com/animation",
                "start": "2026-11-08 11:30",
                "end": "2026-11-08 13:09",
                "stage": "Everyman Cinema",
            }
        )
        + "\n"
    )
    screenings = load_extra_screenings(path, {"https://example.com/animation": 4})
    assert len(screenings) == 2
    assert {item.points for item in screenings} == {4}
    preferred = apply_preferred_showings(
        screenings, {"https://example.com/animation": "2026-11-06 11:45"}
    )
    assert [item.start.day for item in preferred] == [6]


@pytest.mark.parametrize(
    ("rules", "message"),
    [
        (
            {"unavailable": [{"start": "2026-11-01T12:00", "end": "2026-11-01T10:00"}]},
            "Invalid unavailable interval",
        ),
        ({"venue_transfer_minutes": {"Cottage Road": -5}}, "nonnegative"),
        ({"minimum_gap_minutes": -1}, "nonnegative"),
        ({"max_screenings_per_day": 0}, "per day must be positive"),
        ({"max_films": 0}, "Maximum films must be positive"),
    ],
)
def test_invalid_rules_are_rejected(tmp_path, rules, message):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(rules))
    with pytest.raises(ValueError, match=message):
        load_rules(path)
