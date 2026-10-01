"""Extract LIFF listings into a year-local Clashfinder file."""

import argparse
import datetime
import json
import logging
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.leedsfilm.com"
YEAR = 2026
PAGE_SIZE = 200
DATE_FORMAT_IN = "%a %d %b %Y %H:%M"
DATE_FORMAT_OUT = "%Y-%m-%d %H:%M"
log = logging.getLogger(__name__)


def fetch(url):
    # A failed request stops the run. Repeating it immediately is unhelpful to the site.
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    if not response.content:
        raise ValueError(f"Empty response from {url}")
    return response.content


def index_entries(html):
    soup = BeautifulSoup(html, "lxml")
    entries = []
    seen = set()
    for link in soup.select("a.desc[href]"):
        title = link.select_one("h3.title")
        url = urljoin(BASE_URL, link["href"])
        if not title or url in seen:
            continue
        seen.add(url)
        entries.append({"title": title.get_text(" ", strip=True), "url": url})
    return entries


def get_index(output_dir, clean=False, offline=False):
    entries = []
    seen = set()
    for page in range(1, 100):
        path = output_dir / f"allfilm-{page}.html"
        if clean or not path.exists():
            if offline:
                raise FileNotFoundError(f"Index page is not cached: {path}")
            url = f"{BASE_URL}/whats-on?max={PAGE_SIZE}&page={page}"
            path.write_bytes(fetch(url))
        current = index_entries(path.read_bytes())
        if not current:
            if page == 1:
                raise ValueError("No film links found on the index page")
            break
        added = [entry for entry in current if entry["url"] not in seen]
        if not added:
            break
        entries.extend(added)
        seen.update(entry["url"] for entry in added)
        log.info("Index page %s: %s entries", page, len(current))
        if len(current) < PAGE_SIZE:
            break
    else:
        raise RuntimeError("Index exceeded 99 pages")
    # The programme preview is an event, not a film.
    films = [entry for entry in entries if entry["title"] != f"LIFF {YEAR} Programme Preview"]
    (output_dir / "films.json").write_text(
        json.dumps(films, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log.info("Saved %s films from %s index entries", len(films), len(entries))
    return films


def retrieve_film(db, url, clean=False, offline=False):
    if not clean:
        row = db.execute("SELECT html FROM cache WHERE url = ?", (url,)).fetchone()
        if row:
            return row[0]
    if offline:
        raise FileNotFoundError(f"Film is not cached: {url}")
    html = fetch(url)
    db.execute("INSERT OR REPLACE INTO cache (url, html) VALUES (?, ?)", (url, html))
    db.commit()
    return html


def skip_text(text):
    return "also be available to view on Leeds Film Player" in text or text == "Save with a LIFF 2022 Pass"


def build_date_range(minutes, date_text, time_text, year=None):
    if year is None:
        year = YEAR
    start = datetime.datetime.strptime(f"{date_text} {year} {time_text}", DATE_FORMAT_IN)
    return start, start + datetime.timedelta(minutes=minutes)


def build_output(url, title, desc, parsed_date, parsed_end, venue):
    item = {
        "start": parsed_date.strftime(DATE_FORMAT_OUT),
        "end": parsed_end.strftime(DATE_FORMAT_OUT),
        "stage": venue,
        "act": title,
        "type": "film",
        "url": url,
        "blurb": desc,
    }
    return f"act = {json.dumps(item, ensure_ascii=False)}"


def remap_venue(venue):
    replacements = {
        "Everyman Cinema Leeds, Leeds": "Everyman Cinema",
        "Vue in the Light, Leeds Screen": "Vue in the Light, Screen",
        "Hyde Park Picture House, Leeds Screen": "Hyde Park Picture House, Screen",
        "Cottage Road Cinema, Leeds Screen 1": "Cottage Road Cinema",
    }
    for old, new in replacements.items():
        venue = venue.replace(old, new)
    return venue


def extract_venue(row):
    location = row.select_one("div.location")
    screen = row.select_one("div.venue")
    parts = [node.get_text(" ", strip=True) for node in (location, screen) if node]
    return remap_venue(" ".join(parts)) if parts else "Unknown"


def parse_film(html, url, review=None):
    page = BeautifulSoup(html, "lxml")
    title_node = page.select_one("div.desc h1")
    if not title_node:
        raise ValueError(f"No title on {url}")
    title = title_node.get_text(" ", strip=True)
    info = page.select_one("div.extraInfo")
    runtime = re.search(r"(?:Running time|Runtime)\s*:?\s*(\d+)", info.get_text(" ", strip=True), re.I) if info else None
    description = page.select_one("div.desc1")
    if runtime:
        minutes = int(runtime.group(1))
    else:
        listed_minutes = [
            int(value) for value in re.findall(
                r"\b(\d+)\s*(?:mins|minutes)\b",
                description.get_text(" ", strip=True) if description else "",
                re.I,
            )
        ] if "Competition" in title or "Panorama" in title else []
        minutes = sum(listed_minutes)
        source = "sum of listed shorts; breaks not included" if listed_minutes else "unknown; no runtime supplied"
        log.warning("%s: %s (%s minutes)", title, source, minutes)
        if review is not None:
            review.append({"title": title, "url": url, "minutes": minutes, "reason": source})
    desc = "\n".join(
        text for p in description.select("p")
        if (text := p.get_text(" ", strip=True)) and not skip_text(text)
    ) if description else ""
    rows = page.select('ul[id^="sub-show-list"] li')
    if not rows:
        top_date = page.select_one("div.top-date")
        date_node = top_date.select_one("span.start") if top_date else None
        time_node = top_date.select_one("span.time") if top_date else None
        time_match = re.search(r"\b\d{1,2}:\d{2}\b", time_node.get_text(" ", strip=True)) if time_node else None
        if not date_node or not time_match:
            raise ValueError(f"No screening date or time for {title}: {url}")
        start, end = build_date_range(minutes, date_node.get_text(" ", strip=True), time_match.group())
        return [build_output(url, title, desc, start, end, extract_venue(page))]
    output = []
    for row in rows:
        date_node = row.select_one("div.date div.start")
        time_node = row.select_one("div.time span.start")
        if not date_node or not time_node:
            raise ValueError(f"Incomplete screening for {title}: {url}")
        start, end = build_date_range(minutes, date_node.get_text(" ", strip=True), time_node.get_text(" ", strip=True))
        output.append(build_output(url, title, desc, start, end, extract_venue(row)))
    return output


def download_missing(db, films, batch_size=None, delay=1.0):
    cached = {row[0] for row in db.execute("SELECT url FROM cache")}
    missing = [film["url"] for film in films if film["url"] not in cached]
    missing_count = len(missing)
    if batch_size is not None:
        missing = missing[:batch_size]
    log.info("%s cached, %s of %s missing pages to fetch this run", len(films) - missing_count, len(missing), missing_count)
    for index, url in enumerate(missing, 1):
        if index > 1:
            time.sleep(delay)
        retrieve_film(db, url)
        log.info("Downloaded %s/%s: %s", index, len(missing), url)
    return len(missing)


def run(output_dir, clean=False, limit=None, single=None, download_only=False, offline=False, batch_size=None, delay=1.0):
    output_dir.mkdir(parents=True, exist_ok=True)
    films = [{"url": single}] if single else get_index(output_dir, clean, offline)
    if limit is not None:
        films = films[:limit]
    with sqlite3.connect(output_dir / "html.db") as db:
        db.execute("CREATE TABLE IF NOT EXISTS cache (url TEXT PRIMARY KEY, html BLOB)")
        if download_only:
            download_missing(db, films, batch_size, delay)
            return
        lines = []
        review = []
        for film in films:
            url = film["url"]
            log.info("Extracting %s", url)
            lines.extend(parse_film(retrieve_film(db, url, clean, offline), url, review))
    (output_dir / "clashfinder").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_dir / "duration-review.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log.info("Wrote %s screenings from %s films; %s runtimes need review", len(lines), len(films), len(review))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=YEAR)
    parser.add_argument("--clean", action="store_true", help="refresh cached HTML")
    parser.add_argument("--limit", type=int, help="extract the first N films from the index")
    parser.add_argument("--single", help="extract a single film URL")
    parser.add_argument("--download-only", action="store_true", help="cache missing film pages without extracting")
    parser.add_argument("--offline", action="store_true", help="extract using cached HTML only")
    parser.add_argument("--batch-size", type=int, help="maximum new film pages to download")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between film page requests")
    args = parser.parse_args()
    if args.clean and args.offline:
        parser.error("--clean and --offline cannot be combined")
    if args.download_only and args.offline:
        parser.error("--download-only and --offline cannot be combined")
    if args.batch_size is not None and args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if args.delay < 0:
        parser.error("--delay cannot be negative")
    YEAR = args.year
    logging.basicConfig(level=logging.INFO)
    run(Path(str(args.year)), args.clean, args.limit, args.single, args.download_only, args.offline, args.batch_size, args.delay)
