# liff-utils
A collection of tools for making LIFF-life easier

## General notes
These are designed to make life a bit easier. Things that would take ages (getting film details from the website, splitting PDF tickets into individual files) can be done quickly. Because they depend on the format of the Leeds Film website and the LCC Box Office, I have absolutely no control over whether they keep working. Each year, they'll probably need a tweak to make them better.

These are quick, cobbled together scripts. There's no real quality control here. Feel free to improve or change them as you wish.

## Usage
Python scripts. You'll need Python3 and ideally virtualenv to install dependencies.
- Clone repo
- Create virtualenv
- Install modules in requirements file
- Run scripts

## Scrape.py
This is designed to populate the (excellent) [Clashfinder website](https://clashfinder.com/). It reads the LIFF listings page, then visits each film for its screenings, runtime and venue. The output can be pasted into Clashfinder.

For 2026, first run `uv run python scrape.py --download-only --batch-size 10` to cache a small batch of missing film pages. Repeat with a larger batch after checking the result; each run skips pages already cached, waits one second between requests, and stops at the first HTTP error. Then run `uv run python scrape.py --offline` to extract the full programme without network requests. The script writes `2026/films.json` (film titles and URLs), `2026/clashfinder` (one line per screening), and `2026/duration-review.json` (runtimes needing review). The index HTML snapshot and film page cache stay local; three example film pages are checked in as references for future years. Where a short film programme has no total runtime, the script sums its listed shorts; this excludes breaks. Listings with no usable runtime have equal start and end times and are flagged in the review file. Each year's output goes in its own directory.

## Ticket-converter.py
The LIFF Box Office has a really irritating habbit of sending you one mega PDF of all your tickets. I'm sure this is fine (good, even) when you're ordering a pair of tickets for an event or maybe a couple of films. But when you're using your LIFF pass to go to 30+ films, it's pretty useless. You do not want to be the person at the door to the screening, desperately trying to find the 23rd ticket in your 30 page PDF. No.

This script eats the PDF, splits it by page, titling each file with the DATE, TIME and TITLE of your film. This makes finding your ticket Very Easy.

**NB. This has not been updated for 2023. No idea yet if the box office format has changed**
