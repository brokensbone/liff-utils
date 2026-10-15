"""Generate a browser-console script for one Clashfinder highlight set.

Usage: python clashfinder_highlight.py PLAN.md EXPORT.json --set 4
"""

import argparse
import json
import re
from pathlib import Path

from itinerary_calendar import parse_itinerary

TEMPLATE = Path(__file__).with_suffix(".template.js")
SHORT = re.compile(r"^[a-z0-9]+\([1-9][0-9]*\)$")


def scheduled_shorts(
    itinerary: Path,
    export: Path,
    year: int,
    overrides: Path | None = None,
) -> tuple[str, list[str]]:
    """Match each scheduled screening to its exact Clashfinder occurrence."""
    data = json.loads(export.read_text())
    by_showing = {}
    for location in data["locations"]:
        for event in location["events"]:
            key = (event["url"], event["start"], location["name"])
            by_showing[key] = event["short"]
    if overrides:
        for item in json.loads(overrides.read_text()):
            key = (item["url"], item["start"], item["venue"])
            by_showing[key] = item["short"]
    shorts = []
    for event in parse_itinerary(itinerary, year)["events"]:
        key = (event["url"], f"{event['date']} {event['start']}", event["venue"])
        if key not in by_showing:
            raise ValueError(
                f"No Clashfinder short ID for {event['title']} at {key[1]}"
            )
        short = by_showing[key]
        if not SHORT.fullmatch(short):
            raise ValueError(f"Invalid Clashfinder short ID: {short}")
        shorts.append(short)
    if len(shorts) != len(set(shorts)):
        raise ValueError("Two scheduled screenings have the same Clashfinder short ID")
    return data["id"], shorts


def render_script(festival: str, shorts: list[str], set_number: int, name: str) -> str:
    if set_number < 1:
        raise ValueError("Highlight set number must be positive")
    replacements = {
        "__DESIRED__": json.dumps(shorts, ensure_ascii=False),
        "__FESTIVAL__": json.dumps(festival),
        "__SET__": str(set_number),
        "__NAME__": json.dumps(name),
    }
    script = TEMPLATE.read_text()
    for placeholder, value in replacements.items():
        script = script.replace(placeholder, value)
    return script


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("itinerary", type=Path)
    parser.add_argument("export", type=Path, help="Clashfinder JSON export")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--set", type=int, default=4)
    parser.add_argument("--name", default="Scheduled")
    parser.add_argument(
        "--overrides", type=Path, help="JSON short IDs missing from export"
    )
    parser.add_argument("--output", type=Path, help="Output JavaScript path")
    args = parser.parse_args()
    festival, shorts = scheduled_shorts(
        args.itinerary, args.export, args.year, args.overrides
    )
    output = args.output or args.itinerary.with_suffix(".js")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_script(festival, shorts, args.set, args.name))
    print(f"Wrote {output} for {len(shorts)} scheduled screenings")


if __name__ == "__main__":
    main()
