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
This is designed to populate the (excellent) [Clashfinder website](https://clashfinder.com/). It hits the LIFF listings page, then goes to every film included, grabbing their times, runtimes and venues. Outputs the data in a format you can just paste into Clashfinder.

## Ticket-converter.py
The LIFF Box Office has a really irritating habbit of sending you one mega PDF of all your tickets. I'm sure this is fine (good, even) when you're ordering a pair of tickets for an event or maybe a couple of films. But when you're using your LIFF pass to go to 30+ films, it's pretty useless. You do not want to be the person at the door to the screening, desperately trying to find the 23rd ticket in your 30 page PDF. No.

This script eats the PDF, splits it by page, titling each file with the DATE, TIME and TITLE of your film. This makes finding your ticket Very Easy.

**NB. This has not been updated for 2023. No idea yet if the box office format has changed**
