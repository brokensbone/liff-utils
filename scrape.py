import logging
import sqlite3
import time
import requests
from bs4 import BeautifulSoup
import argparse
import os
import pickle
import json
import datetime
import re

parser = argparse.ArgumentParser()
parser.add_argument(
    "--clean", help="discard any previous cached html", action="store_true"
)
parser.add_argument("--single", help="run on a single film url", action="store")
args = parser.parse_args()

logging.basicConfig()
log = logging.getLogger()
log.setLevel("DEBUG")

err_handler = logging.FileHandler("errors.log")
err_handler.setLevel(logging.ERROR)
log.addHandler(err_handler)

output_file = open("clashfinder", "w")

BASE_URL = "https://www.leedsfilm.com"
DATE_FORMAT_IN = "%a %d %b %Y %H:%M"  # Fri 6 Nov 2022 13:15
DATE_FORMAT_OUT = "%Y-%m-%d %H:%M"  # 2022-08-25 22:30

all_lengths = []


def get_main_page(ix):
    # URL = BASE_URL + "liff-2022-films/?Date=All+Dates&Strand=&Country=&Venue=&SortOrder=0&PageSize=10000&Page=1#festival-filter-form"
    # URL = BASE_URL + "whats-on/?Date=All+Dates&Strand=&Country=&Venue=&SortOrder=0&PageSize=10000&Page=1#festival-filter-form"
    URL = BASE_URL + f"/whats-on?max=54&page={ix}#page_part_54"
    FILE = f"allfilm-{ix}.html"

    if not os.path.exists(FILE) or args.clean:
        log.debug("clean download")
        mainpage = requests.get(URL)
        with open(FILE, "wb") as f:
            pickle.dump(mainpage, f)
    with open(FILE, "rb") as f:
        return pickle.load(f)


def go():
    log.debug("hello")
    cx = sqlite3.connect("html.db")

    for ix in range(4):
        log.info(f"DOING PAGE {ix}")
        mainpage = get_main_page(ix + 1)

        soup = BeautifulSoup(mainpage.content, "html.parser")
        film_links = soup.find_all("a", class_="desc")

        film_links = film_links[:]
        for film_link in film_links:
            url = BASE_URL + film_link["href"]
            log.debug(url)
            handle_film(url, cx)


def skip_text(text):
    if "also be available to view on Leeds Film Player" in text:
        return True
    if text == "Save with a LIFF 2022 Pass":
        return True
    return False


def retrieve_film(db: sqlite3.Connection, url: str, backoff: int = 1):
    c = db.cursor()
    c.execute("SELECT html FROM cache WHERE url = ?", (url,))
    row = c.fetchone()
    if row:
        log.info(f"{url} from cache")
        c.close()
        return row[0]

    log.info(f"{url} needs retrieving")
    film_page = requests.get(url)
    if film_page.status_code == 429:
        c.close()
        if backoff < 60:
            logging.info(f"Backing off for {backoff}")
            time.sleep(backoff)
            retrieve_film(db, url, backoff=backoff * 2)
        else:
            logging.error("Giving up")
        return
    c.execute("INSERT INTO cache VALUES (?,?)", (url, film_page.content))
    db.commit()
    c.close()
    return film_page.content


def handle_film(url: str, cx: sqlite3.Connection):
    film_page = retrieve_film(cx, url)
    if not film_page:
        return
    page = BeautifulSoup(film_page, "html.parser")

    # sort the title out
    section = page.find("div", class_="desc")
    title_span = None
    if section:
        title_span = section.find("h1", class_="with-supertitle")
        if not title_span:
            title_span = section.find("h1")

    if not title_span:
        log.error(f"{url} has no obvious title. Skipping")
        return
    title = title_span.text

    # get the running time
    extra_info = page.find("div", class_="extraInfo")
    if extra_info is None:
        logging.error(f"{url} has no info. Skipping")
        return

    log.info(f"DEBUG EXTRAINFO {extra_info.text}")
    run_time_match = re.search(
        r"(?:Running time|Runtime|runtime):*\s([0-9]*) (?:[Mm]inutes|[Mm]ins)",
        extra_info.text,
    )
    run_time_match_loose = re.search(
        r"(?:Running time|Runtime|runtime):*\s([0-9]*)", extra_info.text
    )
    if run_time_match is None and run_time_match_loose is None:
        logging.error(f"{url} Failed to get length for film {title}")
        minutes = 240  # Just make it mad long so I can spot it and fix it.
    elif run_time_match is None and run_time_match_loose is not None:
        minutes = int(run_time_match_loose.group(1))
        logging.error(f"{url} has badly formatted duration. Reading as {minutes}")
    else:
        minutes = int(run_time_match.group(1))

    # get a description (not strictly necessary...)
    desc_section = page.find("div", class_="desc1")
    desc_ps = desc_section.find_all("p")
    descs = [p.text for p in desc_ps if not skip_text(p.text)]
    desc = "\n".join(descs)

    book_section = page.find("ul", {"id": re.compile("sub-show-list[0-9]*")})

    if book_section is not None:
        book_rows = book_section.find_all("li")
        for book_row in book_rows:
            # find the date and time
            date_div = book_row.find("div", class_="date").find("div", class_="start")
            time_div = book_row.find("div", class_="time").find("span", class_="start")
            date_text = date_div.text.strip()
            time_text = time_div.text.strip()

            # bash 'em together, then parse as one
            parsed_date, parsed_end = build_date_range(minutes, date_text, time_text)

            # Do Venues
            venue = extract_venue(book_row)

            # Log it
            log.debug(f"{title} [venue] {date_text} {time_text}")

            # And finally build our output
            out_line = build_output(url, title, desc, parsed_date, parsed_end, venue)
            log.debug(out_line)
            output_file.write(out_line + "\n")
        # we out.
        return

    # ok, try another way to get the same info
    top_date = page.find("div", class_="top-date")
    if top_date is not None:
        date_text = top_date.find("span", class_="start").text.strip()
        time_text = top_date.find("span", class_="time").text.strip()
        time_text = time_text.splitlines()[1].strip()
        parsed_date, parsed_end = build_date_range(minutes, date_text, time_text)

        venue = extract_venue(page)

        out_line = build_output(url, title, desc, parsed_date, parsed_end, venue)
        log.debug(out_line)
        output_file.write(out_line + "\n")

        # and done
        return

    # hmm. no idea.
    logging.error(f"{url} Film {title} has no show times. Skipping")


def build_date_range(minutes, date_text, time_text):
    date = f"{date_text} 2025 {time_text}"
    parsed_date = datetime.datetime.strptime(date, DATE_FORMAT_IN)
    parsed_end = parsed_date + datetime.timedelta(minutes=minutes)
    return parsed_date, parsed_end


def build_output(url, title, desc, parsed_date, parsed_end, venue):
    item = {}
    item["start"] = parsed_date.strftime(DATE_FORMAT_OUT)
    item["end"] = parsed_end.strftime(DATE_FORMAT_OUT)
    item["stage"] = venue
    item["act"] = title
    item["type"] = "film"
    item["url"] = url
    item["blurb"] = desc
    item_json = json.dumps(item)
    out_line = f"act = {item_json}"
    return out_line


def extract_venue(book_row):
    location_div = book_row.find("div", class_="location")
    screen_div = book_row.find("div", class_="venue")
    venue = f"{location_div.text.strip()} {screen_div.text.strip()}"

    remap_venues = {
        "Everyman Cinema Leeds, Leeds": "Everyman Cinema",
        "Vue in the Light, Leeds Screen": "Vue in the Light, Screen",
        "Hyde Park Picture House, Leeds Screen": "Hyde Park Picture House, Screen",
        "Cottage Road Cinema,  Leeds Screen 1": "Cottage Road Cinema",
    }

    for key, value in remap_venues.items():
        venue = venue.replace(key, value)

    return venue


if __name__ == "__main__":
    if args.single:
        handle_film(args.single)
    else:
        go()
output_file.close()

for x in all_lengths:
    log.debug(x)
