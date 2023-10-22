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
parser.add_argument('--schema', help="catalog to read", action="store", default=2015, type=int)
parser.add_argument('--test', help="page to do a test full text extract on", action="store_true")
parser.add_argument('--extract', help="page to do a test data extract on", action="store_true")
parser.add_argument('--page', help="page to do a tests on", action="store", type=int)
args = parser.parse_args()

class ExtractorBase:
    def get_film_bounds(self):
        raise NotImplementedError()
    
    def parse_ordered_elements_as_film(self, elements):
        raise NotImplementedError()
    def get_strand_mapping(self):
        raise NotImplementedError()
    
    def hash_elements_by_page_number(self, elements):
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
    
    def get_elements_in_y_order(self, elements):
        parts = { float(e.attrib['y0']) : e for e in elements if e.text is not None }
        keys = sorted(parts.keys())
        keys.reverse()
        return [ parts[k] for k in keys ]

    def safe_get_char_col(self, element):
        try:
            return next(e for e in element.layout).graphicstate.ncolor[0]
        except:
            logging.warn("Failed to read a char colour")
            return -1

    def process(self, fp):
        f = open(fp, 'rb')
        pdf = pdfquery.PDFQuery(f)
        if args.test:
            # in this mode, get all the text, sorted by y placement.
            self.extract_test_page(pdf)
            return
        

        if args.extract:

            self.films = []
            logging.info("Start load...")
            if args.page:
                pdf.load(args.page)
                self.parse_loaded_pages(pdf, "single page")
            else:
                for strand, page_range in self.get_strand_mapping().items():
                    pdf.load(list(range(page_range[0], page_range[1])))
                    self.parse_loaded_pages(pdf, strand)

            with open('./catalog/extractfilms.json', 'w') as json_out:
                json.dump(self.films, json_out, indent=4)

    def parse_loaded_pages(self, pdf, strand):
        schema = self.get_film_bounds()
        bounds = [ f"0,{d[0]},480,{d[1]}" for d in schema ]
        logging.info("Start parsing...")
        for ix, bound in enumerate(bounds):
            elements = pdf.pq(':in_bbox("{}")'.format(bound))
            elements_by_page = self.hash_elements_by_page_number(elements)
            for page_num, page_elements in elements_by_page.items():
                film_parts = self.get_elements_in_y_order(page_elements)
                film = self.parse_ordered_elements_as_film(film_parts)
                film['page_no'] = page_num
                film['strand'] = strand
                self.films.append(film)
        logging.info("End parsing...")

    def extract_test_page(self, pdf):
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
        

class Extractor2015(ExtractorBase):
    def get_film_bounds(self):
        return [
            [450, 590],
            [310, 450],
            [165, 310],
            [30, 165]
        ]
    def get_strand_mapping(self):
        return {
            "Official Selection" : [17, 26],
            "Retrospectives": [31, 39],
            "Cinema Versa": [43, 55],
            "Fanomenon": [59, 73],
            "Short Film City": [77, 83],
        }

    def parse_ordered_elements_as_film(self, elements):
        film = {'title' : None, 'info' : [], 'screenings': [], 'blurb': [], 'substrand': None}
        for element in elements:
            line = element.text
            char_col = self.safe_get_char_col(element)
            if re.search("^[A-Z ]*$", line) and not film['info']:
                film['substrand'] = line.strip()
            elif film['title'] is None:
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

def init_extractor():
    if args.schema == 2015:
        return Extractor2015()
    else:
        logging.error(f"No extractor available for [{args.schema}]")
        exit(1)

if __name__ == '__main__':
    extractor = init_extractor()
    extractor.process(args.file)
