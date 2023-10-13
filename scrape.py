import logging
import requests
from bs4 import BeautifulSoup
import argparse
import os
import pickle
import json
import datetime
import re

parser=argparse.ArgumentParser()
parser.add_argument('--clean', help="clean", action="store_true")
args = parser.parse_args()

logging.basicConfig()
log = logging.getLogger()
log.setLevel("DEBUG")

output_file = open('clashfinder', 'w')

BASE_URL = "https://www.leedsfilm.com/"
DATE_FORMAT_IN = "%d %B %Y %H:%M" # 15 November 2022 13:15
DATE_FORMAT_OUT = "%Y-%m-%d %H:%M" # 2022-08-25 22:30

all_lengths = []

def get_main_page():
    URL = BASE_URL + "liff-2022-films/?Date=All+Dates&Strand=&Country=&Venue=&SortOrder=0&PageSize=10000&Page=1#festival-filter-form"
    FILE = 'allfilm.html'

    if not os.path.exists(FILE) or args.clean:
        log.debug("clean download")
        mainpage = requests.get(URL)
        with open(FILE, 'wb') as f:
            pickle.dump(mainpage, f)
    with open(FILE, 'rb') as f:
        return pickle.load(f)

def go():
    log.debug("hello")

    mainpage = get_main_page()
    
    soup = BeautifulSoup(mainpage.content, "html.parser")
    film_links = soup.find_all("a", class_="learn")
    
    film_links = film_links[:]
    for film_link in film_links:
        url = BASE_URL + film_link["href"]
        log.debug(url)
        handle_film(url)

def handle_film(url):
    film_page = requests.get(url)
    page = BeautifulSoup(film_page.content, "html.parser")
    section = page.find("section", class_="film-details")
    title_span = section.find("span", class_="title")
    title = title_span.text

    tag_list = section.find("div", class_="tag-list")
    tags = tag_list.find_all("span", class_="tag")
    if len(tags) >= 4:
        length_tag = tags[3]
        length = length_tag.text
        all_lengths.append(length)
    else:
        all_lengths.append("NONE")
        length = "1hr"

    length_parts = length.split(" ")
    hour_part = length_parts[0]
    hours = int(re.search(r"(\d+)hr", hour_part).group(1))
    minutes = 0
    if len(length_parts)>1:
        minute_part = length_parts[1]
        match = re.search(r"(\d+)min", minute_part)
        if match is not None:
            minutes = int(match.group(1))


    desc_section  =page.find("section", class_="main-content")
    desc_ps = desc_section.find_all("p")

    def skip_text(text):
        if "also be available to view on Leeds Film Player" in text:
            return True
        if text == "Save with a LIFF 2022 Pass":
            return True
        return False

    descs = [p.text for p in desc_ps if not skip_text(p.text)]
    desc = "\n".join(descs)
    
    book_section = page.find("section", class_="book-your-tickets")
    book_table = book_section.find("table")
    book_table_body = book_table.find("tbody")
    book_rows = book_table_body.find_all("tr")
    for book_row in book_rows:
        date_span = book_row.find("span", class_="date")
        time_span = book_row.find("span", class_="time")
        venue_span = book_row.find("span", class_="venue")
        
        date = date_span.text
        time = time_span.text
        venue = venue_span.text

        date_parts = date.split(" ")
        day_part = date_parts[0]
        day_part = "".join([x for x in day_part if not x.isalpha()])
        date_parts[0] = day_part
        date = " ".join(date_parts) + " " + time
        
        parsed_date = datetime.datetime.strptime(date, DATE_FORMAT_IN)
        parsed_end = parsed_date + datetime.timedelta(hours=hours, minutes=minutes)
        log.debug(f'{title} [{venue}] {date} {time}')

        item = {}
        item["start"] = parsed_date.strftime(DATE_FORMAT_OUT)
        item["end"] = parsed_end.strftime(DATE_FORMAT_OUT)
        item["stage"] = venue
        item["act"] = title
        item["type"] = "film"
        item["url"] = url
        item["blurb"] = desc
        item_json = json.dumps(item)
        out_line = f'act = {item_json}'
        log.debug(out_line)
        output_file.write(out_line + "\n")


if __name__ == '__main__':
    go()
output_file.close()

for x in all_lengths:
    log.debug(x)

