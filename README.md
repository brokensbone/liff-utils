# liff-utils
A collection of tools for making LIFF-life easier

## General notes
These are designed to make life a bit easier. Things that would take ages (getting film details from the website, splitting PDF tickets into individual files) can be done quickly. Because they depend on the format of the Leeds Film website and the LCC Box Office, I have absolutely no control over whether they keep working. Each year, they'll probably need a tweak to make them better.

These are small scripts. The test and lint checks cover the main paths, but the festival website and ticket layout can still change.

## Usage
Install [uv](https://docs.astral.sh/uv/) and run `uv sync --locked` after cloning. Use `uv run python scrape.py` or `uv run python ticket-split.py` to run the scripts. Check changes with `uv run pytest`, `uv run ruff check .`, and `uv run ruff format --check .`.

## Scrape.py
This is designed to populate the (excellent) [Clashfinder website](https://clashfinder.com/). It reads the LIFF listings page, then visits each film for its screenings, runtime and venue. The output can be pasted into Clashfinder.

For 2026, first run `uv run python scrape.py --download-only --batch-size 10` to cache a small batch of missing film pages. Repeat with a larger batch after checking the result; each run skips pages already cached, waits one second between requests, and stops at the first HTTP error. Then run `uv run python scrape.py --offline` to extract the full programme without network requests. The script writes `2026/films.json` (film titles and URLs), `2026/clashfinder` (one line per screening), and `2026/duration-review.json` (runtimes needing review). The index HTML snapshot and film page cache stay local; three example film pages are checked in as references for future years. `2026/index-exclusions.json` omits newly listed social events, quizzes and workshops from the film list. Where a short film programme has no total runtime, the script sums its listed shorts; this excludes breaks. `2026/runtime-overrides.json` records provisional estimates for listings with no usable runtime, including the evidence for each. `2026/marathon-groups.json` removes the Day of the Dead and Night of the Dead parent events and prefixes their constituent films with DOTD or NOTD. The Night of the Dead film pages all give the same 23:00 start, so their actual order and individual start times remain unconfirmed. Each year's output goes in its own directory.

## Highlighted film itinerary

`uv run python itinerary.py export.json --transfer-minutes 20 --rules 2026/itineraries/rules.json --output 2026/itineraries/plan.md` picks a clash-free set of highlighted films. Clashfinder highlight sets 1, 2 and 3 score one, two and three points per film by default. The solver maximizes points first, then film count to break ties. A rules file can list unavailable time ranges, a minimum gap between all screenings, longer transfer times for named venues, excluded venues, a daily screening limit, and a total film limit. The `--transfer-minutes` buffer applies between different cinema buildings. The script requires proof of the maximum before writing a plan. It lists unscheduled films and tight transfers.

For point changes or films missing from the highlighted export, pass `--scenario scenario.json --clashfinder 2026/clashfinder`. The scenario JSON can contain `highlight_points` (for example `{"3": 4}`), `additional_films` (film URL to points), and `preferred_showings` (film URL to a `YYYY-MM-DD HH:MM` start time). `--clashfinder` is needed only for additional films. An equally scoring plan can have different screening choices, so keep plans you want to compare as separate Markdown files.

`uv run python itinerary_calendar.py 2026` builds a standalone `2026/itineraries/calendar.html` from those Markdown files. Open it locally, tick plans to compare them, and rerun the command after editing or adding a plan. For another year, substitute that year; the calendar discovers its files from `<year>/itineraries/`. An optional `calendar-config.json` in that directory can set `order`, `labels`, `default`, `start`, and `end` for the view.

`uv run python clashfinder_highlight.py plan.md export.json --year 2026 --set 4 --output add-scheduled-set4.js` generates a browser-console script that replaces one highlight set with the plan's exact screening occurrences. If a film is missing from the export, add `--overrides short-overrides.json`; that JSON is a list of objects with `url`, `start`, `venue`, and `short` fields. The script must be run on your own logged-in Clashfinder page. Personal exports, rules, scenarios, itineraries, calendar output, and generated console scripts under `<year>/itineraries/` are ignored by Git.

## ticket-split.py
The LIFF Box Office has a really irritating habbit of sending you one mega PDF of all your tickets. I'm sure this is fine (good, even) when you're ordering a pair of tickets for an event or maybe a couple of films. But when you're using your LIFF pass to go to 30+ films, it's pretty useless. You do not want to be the person at the door to the screening, desperately trying to find the 23rd ticket in your 30 page PDF. No.

This script eats the PDF, splits it by page, naming each file `YYYYMMDD-HHMM-Title.pdf` so a phone shortcut can find the right ticket by date and time. This makes finding your ticket Very Easy.

The splitter reads PDFs from `ticket-split/in` and owner schedules from `ticket-split/schedules`. It writes one directory per owner under `ticket-split/out` and replaces any existing split PDFs there, so check the schedules and inputs before running it.
