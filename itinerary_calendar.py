"""Build a standalone calendar from a year's local itinerary Markdown files.

Usage: python itinerary_calendar.py 2026
"""

import argparse
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

TEMPLATE = Path(__file__).with_suffix(".template.html")
DAY = re.compile(
    r"^## (?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) "
    r"(\d{1,2}) ([A-Za-z]+)$"
)
SCREENING = re.compile(
    r"^- (\d{2}:\d{2})–(\d{2}:\d{2}) \[(.*?)\]\((https?://[^)]+)\)"
    r" — (.*?)(?: \((\d+) pts?\))?$"
)
HEADER = re.compile(r"^# Highlighted film itinerary: (.*)$")


def parse_itinerary(path: Path, year: int) -> dict:
    """Extract scheduled screenings, without the unscheduled appendix."""
    events = []
    day = None
    summary = ""
    for line in path.read_text().splitlines():
        if match := HEADER.match(line):
            summary = match.group(1)
        if line.startswith("## Unscheduled highlights"):
            break
        if match := DAY.match(line):
            day = datetime.strptime(
                f"{match.group(1)} {match.group(2)} {year}", "%d %B %Y"
            )
            continue
        if line.startswith("## "):
            day = None
        if day is None:
            continue
        match = SCREENING.match(line)
        if not match:
            if line.startswith("- "):
                raise ValueError(f"Unrecognised screening in {path}: {line}")
            continue
        start = datetime.combine(
            day.date(), datetime.strptime(match.group(1), "%H:%M").time()
        )
        end = datetime.combine(
            day.date(), datetime.strptime(match.group(2), "%H:%M").time()
        )
        if end <= start:
            end += timedelta(days=1)
        events.append(
            {
                "date": start.date().isoformat(),
                "start": start.strftime("%H:%M"),
                "end_date": end.date().isoformat(),
                "end": end.strftime("%H:%M"),
                "title": match.group(3),
                "url": match.group(4),
                "venue": match.group(5),
                "points": int(match.group(6)) if match.group(6) else None,
            }
        )
    if not events:
        raise ValueError(f"No scheduled screenings in {path}")
    return {
        "id": path.stem,
        "file": path.name,
        "label": path.stem.replace("-", " "),
        "summary": summary,
        "family": "weighted" if path.name.startswith("weighted-") else "earlier",
        "events": events,
    }


def build_calendar(directory: Path, year: int, output: Path | None = None) -> Path:
    """Embed the local plans in a single HTML file that works without a server."""
    config_path = directory / "calendar-config.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    files = list(directory.glob("*.md"))
    if not files:
        raise ValueError(f"No itinerary Markdown files in {directory}")
    preferred = {name: index for index, name in enumerate(config.get("order", []))}
    files.sort(
        key=lambda path: (
            preferred.get(path.name, len(preferred)),
            -path.stat().st_mtime,
            path.name,
        )
    )
    plans = [parse_itinerary(path, year) for path in files]
    for plan in plans:
        plan["label"] = config.get("labels", {}).get(plan["file"], plan["label"])
    all_days = [event["date"] for plan in plans for event in plan["events"]]
    default_file = config.get("default", files[0].name)
    default_id = next(
        (plan["id"] for plan in plans if plan["file"] == default_file),
        plans[0]["id"],
    )
    data = {
        "year": year,
        "start": config.get("start", min(all_days)),
        "end": config.get("end", max(all_days)),
        "default": default_id,
        "plans": plans,
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c"
    )
    html = TEMPLATE.read_text().replace("__PLAN_DATA__", payload)
    html = html.replace("__YEAR__", str(year))
    output = output or directory / "calendar.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int, nargs="?", default=date.today().year)
    parser.add_argument(
        "--directory", type=Path, help="Directory containing itinerary Markdown files"
    )
    parser.add_argument("--output", type=Path, help="Output HTML path")
    args = parser.parse_args()
    directory = (
        args.directory
        or Path(__file__).resolve().parent / str(args.year) / "itineraries"
    )
    output = build_calendar(directory, args.year, args.output)
    print(f"Wrote {output} from {len(list(directory.glob('*.md')))} itineraries")


if __name__ == "__main__":
    main()
