
import logging
import os
import pypdf
import datetime
from pathlib import Path
import json
import itertools
import glob

import sys

import unicodedata

def strip_diacritics(text):
    """Removes diacritics from a string."""
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')


logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

DIRECTORY = "./ticket-split/in"
SCHEDULES = "./ticket-split/schedules"
OUTDIR = "./ticket-split/out"


def load_schedules(schedules_dir):
    """Loads all schedules from the given directory."""
    schedules = {}
    for fname in os.listdir(schedules_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(schedules_dir, fname)
        owner = Path(fpath).stem
        with open(fpath, "r") as f:
            schedules[owner] = json.load(f)
    return schedules


def parse_film_details(page_text):
    """Parses film details from a single page of a PDF."""
    lines = page_text.splitlines()
    film_name, film_place, film_date, film_time = None, None, None, None
    try:
        # Find film name and venue
        for i, line in enumerate(lines):
            if "LIFF 2025" in line:
                film_name = lines[i - 1]
                film_place = lines[i + 2]
                break

        # Find date and time
        for i, line in enumerate(lines):
            try:
                film_date = datetime.datetime.strptime(line, "%d %B %Y")
                film_time_str = lines[i + 1]
                film_time = datetime.datetime.strptime(film_time_str, "%I:%M %p").time()
                break
            except ValueError:
                continue

    except (IndexError, ValueError) as e:
        logging.error(f"Could not parse film details: {e}")
    return film_name, film_place, film_date, film_time


import sys

def find_owner(schedules, film_name, film_place, film_date, film_time):
    """Finds the owner of a film based on the schedules and removes the event."""
    logging.debug(f"Searching for: {film_name} @ {film_date.strftime('%Y-%m-%d')} {film_time.strftime('%H:%M')}")
    for owner, schedule in schedules.items():
        for location in schedule.get("locations", []):
            for event in location.get("events", []):
                event_name = event.get("name", "").strip().lower()
                event_start_str = event.get("start", "")
                logging.debug(f"  Checking against: {event_name} @ {event_start_str} for {owner}")
                if strip_diacritics(film_name.strip().lower()) in strip_diacritics(event_name):
                    try:
                        event_start = datetime.datetime.fromisoformat(event_start_str)
                        if (
                            event_start.date() == film_date.date()
                            and event_start.time() == film_time
                        ):
                            logging.info(f"Found match for {film_name} for {owner}")
                            location["events"].remove(event)
                            return owner, schedules
                    except ValueError:
                        continue
    logging.warning(f"No match found for {film_name}")
    return "unknown", schedules


def process_pdfs(in_dir, out_dir, schedules):


    """Processes all PDFs in the input directory."""


    if not os.path.exists(out_dir):


        os.makedirs(out_dir)





    unclaimed_tickets = []





    for fname in os.listdir(in_dir):


        if not fname.endswith(".pdf"):


            continue


        fpath = os.path.join(in_dir, fname)


        reader = pypdf.PdfReader(fpath)


        for i, page in enumerate(reader.pages):


            page_text = page.extract_text()


            film_name, film_place, film_date, film_time = parse_film_details(page_text)


            if not all([film_name, film_place, film_date, film_time]):


                logging.warning(f"Could not parse details for page {i+1} of {fname}")


                unclaimed_tickets.append((page, film_name, film_date, film_time))


                continue





            owner, new_schedules = find_owner(schedules, film_name, film_place, film_date, film_time)


            schedules = new_schedules


            


            date_str = film_date.strftime("%Y%m%d")


            time_str = film_time.strftime("%H%M")


            safe_title = "".join(c for c in film_name if c.isalnum() or c in " -_").rstrip()


            out_fname = f"{date_str}-{time_str}-{safe_title}.pdf"


            


            owner_dir = os.path.join(out_dir, owner)


            if not os.path.exists(owner_dir):


                os.makedirs(owner_dir)


                


            out_fpath = os.path.join(owner_dir, out_fname)





            writer = pypdf.PdfWriter()


            writer.add_page(page)


            with open(out_fpath, "wb") as out_f:


                writer.write(out_f)


            logging.info(f"Wrote {out_fpath}")





    write_unclaimed_tickets(out_dir, unclaimed_tickets)





def write_unclaimed_tickets(out_dir, unclaimed_tickets):





    """Writes unclaimed tickets to the unknown folder."""





    if not unclaimed_tickets:





        return











    unknown_dir = os.path.join(out_dir, "unknown")





    if not os.path.exists(unknown_dir):





        os.makedirs(unknown_dir)











    for i, (page, film_name, film_date, film_time) in enumerate(unclaimed_tickets):





        if film_date and film_time and film_name:





            date_str = film_date.strftime("%Y%m%d")





            time_str = film_time.strftime("%H%M")





            safe_title = "".join(c for c in film_name if c.isalnum() or c in " -_").rstrip()





            out_fname = f"{date_str}-{time_str}-{safe_title}.pdf"





        else:





            out_fname = f"unclaimed_{i+1}.pdf"











        out_fpath = os.path.join(unknown_dir, out_fname)





        writer = pypdf.PdfWriter()





        writer.add_page(page)





        with open(out_fpath, "wb") as out_f:





            writer.write(out_f)





        logging.info(f"Wrote {out_fpath}")


import copy

def main():
    """Main function."""
    schedules = load_schedules(SCHEDULES)
    process_pdfs(DIRECTORY, OUTDIR, copy.deepcopy(schedules))


if __name__ == "__main__":
    main()
