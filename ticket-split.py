import datetime
import glob
import itertools
import json
import logging
import os
from pathlib import Path

from pypdf import PdfReader, PdfWriter

DIRECTORY = "./ticket-split/in"
SCHEDULES = "./ticket-split/schedules"
OUTDIR = "./ticket-split/out"


def parse_film(lines):
    try:
        order_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.strip().startswith("Order No:")
            ),
            2,
        )
        filmname = lines[order_index + 2].strip()
        filmplace = lines[order_index + 4].strip()
        parse_date = parse_last_date(lines, "%d %B %Y")
        parse_time = parse_last_date(lines, "%I:%M %p").time()
    except (IndexError, ValueError):
        logging.debug("Error parsing date")
        return dump_all_details(lines)

    return [filmname, filmplace, parse_date, parse_time]


def parse_last_date(lines, date_format):
    for line in reversed(lines):
        try:
            return datetime.datetime.strptime(line.strip(), date_format)
        except ValueError:
            continue
    raise ValueError(f"No date matching {date_format}")


def dump_all_details(lines):
    for index, line in enumerate(lines):
        logging.info("%s %s", index, line)
    raise ValueError("Can't parse this ticket")


class Task:
    def run(self):
        logging.info("GO")
        self.load_schedules()
        existing_files = glob.glob(f"{OUTDIR}/*/*/*.pdf")
        for existing_file in existing_files:
            os.remove(existing_file)
        for fname in os.listdir(DIRECTORY):
            if fname.startswith(".") or not fname.lower().endswith(".pdf"):
                continue
            fpath = os.path.join(DIRECTORY, fname)

            reader = PdfReader(fpath)

            pages = len(reader.pages)
            logging.info(f"{fname} has {pages} pages")

            for pagen in range(pages):
                page = reader.pages[pagen]
                txt = page.extract_text()
                lines = txt.splitlines()

                try:
                    filmname, filmplace, parse_date, parse_time = parse_film(lines)
                except Exception:
                    logging.exception("FILE: [%s] [%s]", fname, pagen)
                    raise

                fmt_date = parse_date.strftime("%d")
                fmt_time = parse_time.strftime("%H%M")
                owner = self.calculate_owner(
                    filmname, filmplace, parse_date, parse_time
                )
                outfdir = os.path.join(OUTDIR, owner, fmt_date)
                outfname = f"{fmt_time} {filmname} ({filmplace}).pdf"
                outfpath = os.path.join(outfdir, outfname)

                logging.info(f"{filmname} at {filmplace} {fmt_date} {fmt_time}")
                if os.path.isfile(outfpath):
                    raise Exception("About to write the same file")

                os.makedirs(outfdir, exist_ok=True)

                writer = PdfWriter()
                writer.add_page(page)
                with open(outfpath, "wb") as outf:
                    writer.write(outf)
                    logging.info("Wrote " + outfpath)
        self.check_schedules_for_events_not_found()

    def load_schedules(self):
        schedule_map = {}
        for fname in os.listdir(SCHEDULES):
            if fname.startswith("."):
                continue
            fpath = os.path.join(SCHEDULES, fname)
            owner = Path(fpath).stem
            with open(fpath) as f:
                schedule_map[owner] = json.load(f)
        self.schedule_map = schedule_map

    def calculate_owner(self, title, place, fdate, ftime):
        title = title.lower()
        fmt_date = fdate.strftime("%Y-%m-%d")
        fmt_time = ftime.strftime("%H:%M")
        expected_desc = f"{fmt_date} {fmt_time}"

        for owner, data in self.schedule_map.items():
            for location in data["locations"]:
                for event in location["events"]:
                    if event.get("found", False):
                        continue
                    if event["name"].strip().lower() == title:
                        if event["start"] == expected_desc:
                            logging.debug(
                                f"Found {title}. Taking ownership for {owner}"
                            )
                            event["found"] = True
                            return owner
                        logging.debug(f"Found {title} but wrong time")
        logging.debug(f"No owner for {title}.")

        return "unknown"

    def check_schedules_for_events_not_found(self):
        for owner, data in self.schedule_map.items():
            all_films = [loc["events"] for loc in data["locations"]]
            all_films = list(itertools.chain.from_iterable(all_films))
            for film in all_films:
                if film.get("found", False):
                    continue
                title = film["name"]
                start = film["start"]
                logging.warning(f"{owner} is missing {title} at {start}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    task = Task()
    task.run()
    logging.info("EXIT")
