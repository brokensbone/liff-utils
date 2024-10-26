import logging
import os
import PyPDF2
import datetime
from pathlib import Path
import json
import itertools
import glob

logging.basicConfig(level=logging.DEBUG)

DIRECTORY = "./ticket-split/in"
SCHEDULES = "./ticket-split/schedules"
OUTDIR = "./ticket-split/out"


def parse_film(lines):
    filmdate = lines[17]
    filmtime = lines[18]
    filmname = lines[4]
    filmplace = lines[6]
    try:
        parse_date = datetime.datetime.strptime(filmdate, "%d %B %Y")
        parse_time = datetime.datetime.strptime(filmtime, "%I:%M %p").time()
    except:
        logging.debug("Error parsing date")
        return dump_all_details(lines)
    
    return [filmname, filmplace, parse_date, parse_time]


def dump_all_details(lines):
    i = 0
    for line in lines:
        logging.info("{} {}".format(i, line))
        i += 1
    raise Exception("Can't parse this")

class Task:
    def run(self):
        logging.info("GO")
        existing_files = glob.glob(f"{OUTDIR}/*/*/*.pdf")
        for existing_file in existing_files:
            os.remove(existing_file)
        self.load_schedules()
        for fname in os.listdir(DIRECTORY):
            if fname.startswith('.'):
                continue
            fpath = os.path.join(DIRECTORY, fname)

            reader = PyPDF2.PdfReader(fpath)

            pages = len(reader.pages)
            logging.info("{} has {} pages".format(fname, pages))

            for pagen in range(pages):
                page = reader.pages[pagen]
                txt = page.extract_text()
                lines = txt.splitlines()

                try:
                    filmname, filmplace, parse_date, parse_time = parse_film(lines)
                except:
                    logging.error(f"FILE: [{fname}] [{pagen}]")
                    raise

                fmt_date = parse_date.strftime("%d")
                fmt_time = parse_time.strftime("%H%M")
                owner = self.calculate_owner(filmname, filmplace, parse_date, parse_time)
                outfdir = os.path.join(OUTDIR, owner, fmt_date)
                outfname = "{} {} ({}).pdf".format(fmt_time, filmname, filmplace)
                outfpath = os.path.join(outfdir, outfname)

                logging.info("{} at {} {} {}".format(filmname, filmplace, fmt_date, fmt_time))
                if os.path.isfile(outfpath):
                    raise Exception("About to write the same file")

                os.makedirs(outfdir, exist_ok=True)
                
                writer = PyPDF2.PdfWriter()
                writer.add_page(page)
                with open(outfpath, 'wb') as outf:
                    writer.write(outf)
                    logging.info("Wrote " + outfpath)
        self.check_schedules_for_events_not_found()

    def load_schedules(self): 
        schedule_map = {}          
        for fname in os.listdir(SCHEDULES):
            if fname.startswith('.'):
                continue
            fpath = os.path.join(SCHEDULES, fname)
            owner = Path(fpath).stem
            with open(fpath, 'r') as f:
                schedule_map[owner] = json.load(f)
        self.schedule_map = schedule_map

    def calculate_owner(self, title, place, fdate, ftime):
        title = title.lower()
        fmt_date = fdate.strftime("%Y-%m-%d")
        fmt_time = ftime.strftime("%H:%M")
        expected_desc = f"{fmt_date} {fmt_time}"

        for owner, data in self.schedule_map.items():
            for location in data['locations']:
                for event in location['events']:
                    if event.get('found', False):
                        continue
                    if event['name'].strip().lower() == title:
                        if event['start'] == expected_desc:
                            logging.debug(f"Found {title}. Taking ownership for {owner}")
                            event['found'] = True
                            return owner
                        logging.debug(f"Found {title} but wrong time")
            print("Hmm")
        logging.debug(f"No owner for {title}.")

        return "unknown"
    
    def check_schedules_for_events_not_found(self):
        for owner, data in self.schedule_map.items():
            all_films = [loc['events'] for loc in data['locations']]
            all_films = list(itertools.chain.from_iterable(all_films))
            for film in all_films:
                if film.get('found', False):
                        continue
                title = film['name']
                start = film['start']
                logging.warning(f"{owner} is missing {title} at {start}")

if __name__ == "__main__":
    task = Task()
    task.run()

logging.info("EXIT")
