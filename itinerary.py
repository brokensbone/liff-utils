"""Find the highest-scoring clash-free set of highlighted Clashfinder films.

Usage: uv run python itinerary.py ~/Downloads/liff26-edsalkeld.json
"""

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from ortools.sat.python import cp_model


@dataclass(frozen=True)
class Screening:
    film: str
    title: str
    start: datetime
    end: datetime
    venue: str
    url: str
    points: int = 1


@dataclass(frozen=True)
class PlanningRules:
    unavailable: tuple[tuple[datetime, datetime], ...] = ()
    venue_transfer_minutes: dict[str, int] = field(default_factory=dict)
    minimum_gap_minutes: int = 0
    max_screenings_per_day: int | None = None
    max_films: int | None = None
    excluded_venues: tuple[str, ...] = ()


def load_rules(path: Path) -> PlanningRules:
    data = json.loads(path.read_text())
    unavailable = []
    for entry in data.get("unavailable", []):
        start = datetime.fromisoformat(entry["start"])
        end = datetime.fromisoformat(entry["end"])
        if end <= start:
            raise ValueError(f"Invalid unavailable interval: {start}–{end}")
        unavailable.append((start, end))
    transfer = data.get("venue_transfer_minutes", {})
    if any(minutes < 0 for minutes in transfer.values()):
        raise ValueError("Venue transfer minutes must be nonnegative")
    minimum_gap = data.get("minimum_gap_minutes", 0)
    if minimum_gap < 0:
        raise ValueError("Minimum gap minutes must be nonnegative")
    daily_limit = data.get("max_screenings_per_day")
    if daily_limit is not None and daily_limit < 1:
        raise ValueError("Maximum screenings per day must be positive")
    film_limit = data.get("max_films")
    if film_limit is not None and film_limit < 1:
        raise ValueError("Maximum films must be positive")
    excluded_venues = tuple(data.get("excluded_venues", []))
    return PlanningRules(
        tuple(unavailable),
        transfer,
        minimum_gap,
        daily_limit,
        film_limit,
        excluded_venues,
    )


def load_highlights(
    path: Path, highlight_points: dict[str, int] | None = None
) -> list[Screening]:
    data = json.loads(path.read_text())
    if highlight_points is None:
        highlight_points = {"1": 1, "2": 2, "3": 3}
    screenings = []
    points_by_film = {}
    for location in data["locations"]:
        for event in location["events"]:
            highlights = str(event.get("hls", "")).split()
            scored = [group for group in highlights if group in highlight_points]
            if not scored:
                continue
            for group in scored:
                if f"hl{group}" not in data["gets"]:
                    raise ValueError(f"Highlight set hl{group} is missing from export")
            points = max(highlight_points[group] for group in scored)
            if points < 1:
                raise ValueError(f"Points for {event['name']} must be positive")
            start = datetime.fromisoformat(event["start"])
            end = datetime.fromisoformat(event["end"])
            if end <= start:
                raise ValueError(
                    f"Invalid time range for {event['name']}: {start}–{end}"
                )
            film = event["url"]
            if film in points_by_film and points_by_film[film] != points:
                raise ValueError(f"Conflicting points for {event['name']}")
            points_by_film[film] = points
            screenings.append(
                Screening(
                    film=film,
                    title=event["name"],
                    start=start,
                    end=end,
                    venue=location["name"],
                    url=film,
                    points=points,
                )
            )
    if not screenings:
        raise ValueError("No highlighted screenings found")
    return sorted(screenings, key=lambda item: (item.start, item.title, item.venue))


def load_extra_screenings(path: Path, points_by_url: dict[str, int]) -> list[Screening]:
    """Read selected films that were absent from a highlighted export."""
    if any(points < 1 for points in points_by_url.values()):
        raise ValueError("Extra film points must be positive")
    screenings = []
    found = set()
    for line in path.read_text().splitlines():
        if not line.startswith("act = "):
            continue
        event = json.loads(line.removeprefix("act = "))
        url = event["url"]
        if url not in points_by_url:
            continue
        start = datetime.fromisoformat(event["start"])
        end = datetime.fromisoformat(event["end"])
        if end <= start:
            raise ValueError(f"Invalid time range for {event['act']}: {start}–{end}")
        screenings.append(
            Screening(
                film=url,
                title=event["act"],
                start=start,
                end=end,
                venue=event["stage"],
                url=url,
                points=points_by_url[url],
            )
        )
        found.add(url)
    if missing := set(points_by_url) - found:
        raise ValueError(f"Extra films not found in {path}: {sorted(missing)}")
    return screenings


def apply_preferred_showings(
    screenings: list[Screening], preferred: dict[str, str]
) -> list[Screening]:
    """Limit named films to one showing when a particular time is preferred."""
    times = {url: datetime.fromisoformat(start) for url, start in preferred.items()}
    available = {(item.film, item.start) for item in screenings}
    if missing := {(url, start) for url, start in times.items()} - available:
        raise ValueError(f"Preferred showings not found: {sorted(missing)}")
    return [
        item
        for item in screenings
        if item.film not in times or item.start == times[item.film]
    ]


def incompatible(
    a: Screening,
    b: Screening,
    transfer: timedelta,
    venue_transfer_minutes: dict[str, int] | None = None,
    minimum_gap: timedelta = timedelta(),
) -> bool:
    if a.start < b.end and b.start < a.end:
        return True
    first_building = venue_building(a.venue)
    second_building = venue_building(b.venue)
    required_gap = minimum_gap
    if first_building != second_building:
        venue_transfer_minutes = venue_transfer_minutes or {}
        required_gap = max(
            required_gap,
            transfer,
            timedelta(minutes=venue_transfer_minutes.get(first_building, 0)),
            timedelta(minutes=venue_transfer_minutes.get(second_building, 0)),
        )
    return (a.end <= b.start and b.start - a.end < required_gap) or (
        b.end <= a.start and a.start - b.end < required_gap
    )


def venue_building(venue: str) -> str:
    return re.sub(r",? Screen \d+$", "", venue)


def solve(
    screenings: list[Screening],
    transfer_minutes: int = 0,
    rules: PlanningRules | None = None,
) -> list[Screening]:
    if transfer_minutes < 0:
        raise ValueError("Transfer minutes must be nonnegative")
    rules = rules or PlanningRules()
    model = cp_model.CpModel()
    picks = [model.new_bool_var(f"screening_{i}") for i in range(len(screenings))]
    by_film = defaultdict(list)
    for i, screening in enumerate(screenings):
        by_film[screening.film].append(picks[i])
        if (
            any(
                screening.start < end and start < screening.end
                for start, end in rules.unavailable
            )
            or venue_building(screening.venue) in rules.excluded_venues
        ):
            model.add(picks[i] == 0)
    for choices in by_film.values():
        model.add(sum(choices) <= 1)
    if rules.max_films is not None:
        model.add(sum(picks) <= rules.max_films)
    if rules.max_screenings_per_day is not None:
        by_day = defaultdict(list)
        for screening, pick in zip(screenings, picks, strict=True):
            by_day[screening.start.date()].append(pick)
        for day_picks in by_day.values():
            model.add(sum(day_picks) <= rules.max_screenings_per_day)
    transfer = timedelta(minutes=transfer_minutes)
    for i, first in enumerate(screenings):
        for j in range(i + 1, len(screenings)):
            second = screenings[j]
            if incompatible(
                first,
                second,
                transfer,
                rules.venue_transfer_minutes,
                timedelta(minutes=rules.minimum_gap_minutes),
            ):
                model.add(picks[i] + picks[j] <= 1)
    # One extra film cannot outweigh one point, even in a tie between many films.
    point_multiplier = len(by_film) + 1
    model.maximize(
        sum(
            (screening.points * point_multiplier + 1) * pick
            for screening, pick in zip(screenings, picks, strict=True)
        )
    )
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    if status != cp_model.OPTIMAL:
        raise RuntimeError(
            f"Could not prove optimal schedule: {solver.status_name(status)}"
        )
    return [
        screening for i, screening in enumerate(screenings) if solver.value(picks[i])
    ]


def render(
    screenings: list[Screening],
    selected: list[Screening],
    transfer_minutes: int,
    rules: PlanningRules | None = None,
) -> str:
    rules = rules or PlanningRules()
    chosen = {screening.film for screening in selected}
    by_film = {screening.film: screening.title for screening in screenings}
    by_points = {screening.film: screening.points for screening in screenings}
    earned_points = sum(screening.points for screening in selected)
    possible_points = sum(by_points.values())
    lines = [
        f"# Highlighted film itinerary: {earned_points} of {possible_points} points",
        "",
        f"Selected {len(chosen)} of {len(by_film)} films from {len(screenings)} highlighted showings.",
        "Times are as exported by Clashfinder.",
        f"Minimum transfer between cinema buildings: {transfer_minutes} minutes.",
        "",
    ]
    if rules.minimum_gap_minutes:
        lines += [
            f"Minimum gap between all screenings: {rules.minimum_gap_minutes} minutes.",
            "",
        ]
    if rules.max_screenings_per_day is not None:
        lines += [
            f"Maximum screenings per day: {rules.max_screenings_per_day}.",
            "",
        ]
    if rules.max_films is not None:
        lines += [f"Maximum films: {rules.max_films}.", ""]
    same_day_gaps = [
        int((second.start - first.end).total_seconds() / 60)
        for first, second in zip(selected, selected[1:], strict=False)
        if first.start.date() == second.start.date()
    ]
    if same_day_gaps:
        lines += [f"Shortest gap in this plan: {min(same_day_gaps)} minutes.", ""]
    if rules.unavailable:
        lines += ["Unavailable:", ""]
        lines += [
            f"- {start:%a %-d %b %H:%M}–{end:%H:%M}" for start, end in rules.unavailable
        ]
        lines.append("")
    if rules.venue_transfer_minutes:
        lines += [
            f"Transfer to/from {venue}: at least {minutes} minutes."
            for venue, minutes in rules.venue_transfer_minutes.items()
        ]
        lines.append("")
    if rules.excluded_venues:
        lines += ["Excluded venues: " + ", ".join(rules.excluded_venues) + ".", ""]
    by_day = defaultdict(list)
    for screening in selected:
        by_day[screening.start.date()].append(screening)
    for day, events in sorted(by_day.items()):
        lines += [f"## {day:%A %-d %B}", ""]
        for event in events:
            lines.append(
                f"- {event.start:%H:%M}–{event.end:%H:%M} "
                f"[{event.title}]({event.url}) — {event.venue} ({event.points} pt{'s' if event.points != 1 else ''})"
            )
        lines.append("")
    tight = []
    for events in by_day.values():
        for first, second in zip(events, events[1:], strict=False):
            gap = second.start - first.end
            if venue_building(first.venue) != venue_building(
                second.venue
            ) and gap < timedelta(minutes=30):
                tight.append((first, second, int(gap.total_seconds() / 60)))
    if tight:
        lines += ["## Tight transfers between buildings", ""]
        lines += [
            f"- {first.start:%a %-d %b}: {first.title} → {second.title}: {minutes} minutes"
            for first, second, minutes in tight
        ]
        lines.append("")
    missing = sorted(set(by_film) - chosen, key=lambda film: by_film[film])
    lines += [f"## Unscheduled highlights ({len(missing)})", ""]
    if missing:
        for points in sorted({by_points[film] for film in missing}, reverse=True):
            group = [film for film in missing if by_points[film] == points]
            lines += [
                f"### {points} point{'s' if points != 1 else ''} ({len(group)})",
                "",
            ]
            lines += [f"- [{by_film[film]}]({film})" for film in group]
            lines.append("")
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "highlights", type=Path, help="Clashfinder highlighted JSON export"
    )
    parser.add_argument("--transfer-minutes", type=int, default=0)
    parser.add_argument("--rules", type=Path, help="JSON availability and venue rules")
    parser.add_argument(
        "--scenario", type=Path, help="JSON point overrides and additional film URLs"
    )
    parser.add_argument(
        "--clashfinder", type=Path, help="Clashfinder schedule for additional films"
    )
    parser.add_argument(
        "--output", type=Path, help="Write the Markdown plan to this path"
    )
    args = parser.parse_args()
    scenario = json.loads(args.scenario.read_text()) if args.scenario else {}
    highlight_points = {"1": 1, "2": 2, "3": 3}
    highlight_points.update(scenario.get("highlight_points", {}))
    screenings = load_highlights(args.highlights, highlight_points)
    extra = scenario.get("additional_films", {})
    if extra:
        if not args.clashfinder:
            parser.error("--clashfinder is required for additional films")
        if duplicate := set(extra) & {item.film for item in screenings}:
            raise ValueError(
                f"Additional films already highlighted: {sorted(duplicate)}"
            )
        screenings += load_extra_screenings(args.clashfinder, extra)
    screenings = apply_preferred_showings(
        screenings, scenario.get("preferred_showings", {})
    )
    screenings.sort(key=lambda item: (item.start, item.title, item.venue))
    rules = load_rules(args.rules) if args.rules else PlanningRules()
    selected = solve(screenings, args.transfer_minutes, rules)
    result = render(screenings, selected, args.transfer_minutes, rules)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result)
        earned_points = sum(screening.points for screening in selected)
        print(
            f"Wrote {args.output}: {earned_points} points, "
            f"{len(selected)} of {len({s.film for s in screenings})} films"
        )
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
