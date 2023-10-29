import logging
import os
import PyPDF2
import datetime

logging.basicConfig(level=logging.DEBUG)

DIRECTORY = "./ticket-split/in"
OUTDIR = "./ticket-split/out"


def parse_film(lines):
    filmdate = lines[11]
    filmtime = lines[12]
    filmname = lines[10]
    filmplace = lines[15]
    try:
        parse_date = datetime.datetime.strptime(filmdate, "%a %d %B %Y")
        parse_time = datetime.datetime.strptime(filmtime, "%I:%M %p").time()
    except:
        return parse_old_film(lines)
    return [filmname, filmplace, parse_date, parse_time]

def parse_old_film(lines):
    filmdate = lines[22]
    filmtime = lines[23]
    filmname = lines[31]
    filmplace = lines[32]
    try:
        parse_date = datetime.datetime.strptime(filmdate, "%a %d %B %Y")
        parse_time = datetime.datetime.strptime(filmtime, "%I:%M %p").time()
    except:
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

                outfdir = os.path.join(OUTDIR, fmt_date)
                outfname = "{} {} ({}).pdf".format(fmt_time, filmname, filmplace)
                outfpath = os.path.join(outfdir, outfname)

                logging.info("{} at {} {} {}".format(filmname, filmplace, fmt_date, fmt_time))
                #logging.info(outfpath)

                os.makedirs(outfdir, exist_ok=True)
                
                writer = PyPDF2.PdfWriter()
                writer.add_page(page)
                with open(outfpath, 'wb') as outf:
                    writer.write(outf)
                    logging.info("Wrote " + outfpath)
                


if __name__ == "__main__":
    task = Task()
    task.run()

logging.info("EXIT")
