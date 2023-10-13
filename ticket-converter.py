import os
import logging
import PyPDF2
import re
import shutil

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()

def run(return_first=False):
    log.debug("Runnning now")

    for path, dirnames, filenames in os.walk('data'):
        #log.debug("{}".format(path))
        #log.debug("{}".format(dirnames))
        #log.debug("{}".format(filenames))
        for fn in filenames:
            fp = os.path.join(path, fn)
            log.debug("{}".format(fp))
            ret = process(fp)
            if return_first:
                return ret
            log.debug("{}".format(ret))
    log.info("Complete")

def process(fp):
    f = open(fp, 'rb')
    pdf = PyPDF2.PdfFileReader(f)
    txts = []

    ticket_count = pdf.numPages
    page = pdf.getPage(0)
    txt = page.extractText()
    title  = txt.split("Leeds")[0]
    #start = re.findall('Screening Start:(.+?)Certificate',txt)
    #if len(start) > 0:
    #    start = start[0].strip()
    #else:
    #    log.error("HMMMMMM: {}".format(txt))  
    #return [title, start, ticket_count]
    if ticket_count > 1:
        title  = "{} ({} tickets)".format(title, ticket_count)
    
    title = title + ".pdf"
    dst_path = os.path.join("output", title)
    shutil.copy2(fp, dst_path)    
    return title

def do_one():
    return run(return_first=True)

if __name__ == '__main__':
    run()
