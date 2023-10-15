import os
import logging
import PyPDF2
import re
import argparse
import shutil
import json

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()

parser=argparse.ArgumentParser()
parser.add_argument('--file', help="catalog to read", action="store", default='/Users/edward/develop/liff-utils/catalog/liff2015-guide.pdf')
parser.add_argument('--schema', help="catalog to read", action="store", default='/Users/edward/develop/liff-utils/catalog/schema/2015.json')
parser.add_argument('--testpage', help="page to do a test full text extract on", action="store", type=int)
parser.add_argument('--extractpage', help="page to do a test data extract on", action="store", type=int)
args = parser.parse_args()

def process(fp):
    f = open(fp, 'rb')
    pdf = PyPDF2.PdfReader(f)
    page_count = len(pdf.pages)

    logging.info(f"Read {page_count} pages from {fp}")
    if args.testpage:
        # in this mode, get all the text, sorted by y placement.
        parts = {}
        def hash_by_y_placement(text, cm, tm, fontDict, fontSize):
            y = tm[5]
            if len(text.strip()) > 0:
                parts[y] = text.strip()
        pdf.pages[args.testpage].extract_text(visitor_text=hash_by_y_placement)

        # dump as csv.
        with open('./catalog/testpage.csv', 'w') as outfile:
            keys = sorted(parts.keys())
            keys.reverse()
            for k in keys:
                v = parts[k]
                outfile.write(f"{k},{v}\n")
        return
    
    with open(args.schema) as json_file:
        schema = json.load(json_file)
    parsed = [ {} for x in schema ]
    if args.extractpage:
        def visitor_body(text, cm, tm, fontDict, fontSize):
            y = tm[5]
            if len(text.strip()) == 0:
                return
            text = text.strip()
            for ix, container in enumerate(schema):
                for item, location in container.items():
                    if location[0] < y and y <=location[1]:
                        if parsed[ix].get(item, None) is None:
                            parsed[ix][item] = []
                        parsed[ix][item].append(text)

        pdf.pages[args.extractpage].extract_text(visitor_text=visitor_body)
        with open('./catalog/extractpage.json', 'w') as json_out:
            json.dump(parsed, json_out, indent=4)

    else:

        locations = [
            [450, 590],
            [307, 450],
            [165, 307],
            [25, 165]
        ]
        parts = []
        films = [ {} for x in locations]
        def visitor_body(text, cm, tm, fontDict, fontSize):
            y = tm[5]
            for ix, loc in enumerate(locations):
                if y>loc[0] and y<loc[1]:
                    films[ix][y] = text

            if y > 25 and y < 590:
                parts.append(text)

        pdf.pages[19].extract_text(visitor_text=visitor_body)
        text = "".join(parts)
        logging.info(text)

        logging.info("How does it look?")

        for ix, page in enumerate(pdf.pages):
            logging.info(f"reading page {ix}/{page_count}")
            text = page.extract_text()
            logging.info(text)
            if 'Guanajuato' in text:
                logging.info("pause")
            if ix > 30:
                return
    




if __name__ == '__main__':
    process(args.file)
