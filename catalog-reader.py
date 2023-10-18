import os
import logging
import pdfquery
import re
import argparse
import shutil
import json

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()

logging.getLogger('pdfminer').setLevel(logging.INFO)

parser=argparse.ArgumentParser()
parser.add_argument('--file', help="catalog to read", action="store", default='/Users/edward/develop/liff-utils/catalog/liff2015-guide.pdf')
parser.add_argument('--schema', help="catalog to read", action="store", default='/Users/edward/develop/liff-utils/catalog/schema/2015.json')
parser.add_argument('--test', help="page to do a test full text extract on", action="store_true")
parser.add_argument('--extract', help="page to do a test data extract on", action="store_true")
parser.add_argument('--page', help="page to do a tests on", action="store", type=int)
args = parser.parse_args()

def process(fp):
    f = open(fp, 'rb')
    pdf = pdfquery.PDFQuery(f)
    if args.test:
        # in this mode, get all the text, sorted by y placement.
        parts = {}
        pdf.load(args.page)
        elements = pdf.pq(':in_bbox("0,0,480,630")')
        parts = { float(e.attrib['y0']) : e for e in elements }

        # dump as csv.
        with open('./catalog/testpage.csv', 'w') as outfile:
            keys = sorted(parts.keys())
            keys.reverse()
            for k in keys:
                v = parts[k]
                outfile.write(f"{k},{v.attrib['y1']},{v.text}\n")
        return
    
    with open(args.schema) as json_file:
        schema = json.load(json_file)
    
    if args.extract:

        logging.info("Start load...")
        if args.page:
            pdf.load(args.page)
        else:
            pdf.load()
        logging.info("End load")

        def hash_elements_by_page_number(elements):
            ret = {}
            for e in elements:
                page_pq = next(e.iterancestors('LTPage'))
                page_num = int(page_pq.layout.pageid)
                items = ret.get(page_num, None)
                if items is None:
                    items = []
                    ret[page_num] = items
                items.append(e)
            return ret
        
        def get_elements_in_y_order(elements):
            parts = { float(e.attrib['y0']) : e for e in page_elements if e.text is not None }
            keys = sorted(parts.keys())
            keys.reverse()
            return [ parts[k] for k in keys ]
    
        def safe_get_char_col(element):
            try:
                return next(e for e in element.layout).graphicstate.ncolor[0]
            except:
                logging.warn("Failed to read a char colour")
                return -1
    
        def parse_ordered_elements_as_film(elements):
            film = {'title' : None, 'info' : [], 'screenings': [], 'blurb': []}
            for element in elements:
                line = element.text
                char_col = safe_get_char_col(element)
                if film['title'] is None:
                    film['title'] = line
                elif char_col == 0.429:
                    film['info'].append(line)
                elif char_col == 0.024:
                    film['screenings'].append(line)
                elif char_col == 0:
                    film['blurb'].append(line)
                else:
                    logging.warning(f"Unexpected line colour {char_col} [{line}]")
                    film['blurb'].append(line)
            validate = all([(film[k]) for k in film.keys()])
            film['full_read'] = validate
            return film
        
        
        bounds = [ f"0,{d[0]},480,{d[1]}" for d in schema ]
        films = []
        logging.info("Start parsing...")
        for ix, bound in enumerate(bounds):
            elements = pdf.pq(':in_bbox("{}")'.format(bound))
            elements_by_page = hash_elements_by_page_number(elements)
            for page_num, page_elements in elements_by_page.items():
                film_parts = get_elements_in_y_order(page_elements)
                film = parse_ordered_elements_as_film(film_parts)
                film['page_no'] = page_num
                films.append(film)
        logging.info("End parsing...")

        with open('./catalog/extractfilms.json', 'w') as json_out:
            json.dump(films, json_out, indent=4)

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
