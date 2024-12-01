import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
import logging
import os
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Base URL for scraping
BASE_URL = "https://jibe.sanjuansailing.com/a-vesseloverview.asp"

# GitHub Pages base URL
GITHUB_PAGES_URL = "https://sjs-calendar.github.io/ical"

# Directory to save output files
OUTPUT_DIR = "output"
HTML_FILE = os.path.join(OUTPUT_DIR, "index.html")

def fetch_page():
    logging.info("Fetching the webpage...")
    response = requests.get(BASE_URL)
    if response.status_code != 200:
        logging.error(f"Failed to fetch the page. Status code: {response.status_code}")
        response.raise_for_status()
    logging.info("Page fetched successfully.")
    return response.text

def parse_boats(html):
    logging.info("Parsing boats...")
    soup = BeautifulSoup(html, "html.parser")
    boats = []
    rows = soup.select("tr")

    for row in rows:
        boat_info = row.select_one(".fixedcol-a")
        if not boat_info:
            logging.warning("Skipping row without boat information.")
            continue
        
        link_tag = boat_info.find("a")
        if not link_tag:
            logging.warning(f"Skipping row; no link found in boat info: {boat_info}")
            continue

        boat_name = link_tag.text.strip()
        boat_link = link_tag["href"]
        boat_days = row.find_all("td", class_=["CbgT", "CbgWE", "CbgM"])
        
        availability = []
        for day, cell in enumerate(boat_days, start=1):
            if "CbgM" in cell["class"]:
                availability.append((day, "Booked"))
            elif "CbgT" in cell["class"] or "CbgWE" in cell["class"]:
                availability.append((day, "Available"))

        boats.append({"name": boat_name, "link": boat_link, "availability": availability})
        logging.info(f"Processed boat: {boat_name}")
    return boats

def create_ics_files(boats):
    logging.info("Creating ICS files...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ics_urls = []

    for boat in boats:
        calendar = Calendar()
        for day, status in boat["availability"]:
            if status == "Booked":
                event = Event()
                event.name = f"{boat['name']} - Booked"
                event.begin = f"2024-12-{day:02d}T00:00:00"
                event.end = f"2024-12-{day:02d}T23:59:59"
                event.created = datetime.utcnow()  # Add DTSTAMP
                calendar.events.add(event)
        
        filename = f"{boat['name'].replace(' ', '_')}.ics"
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "w") as f:
            f.writelines(calendar)
        logging.info(f"ICS file created: {filename}")
        ics_urls.append((boat["name"], f"{GITHUB_PAGES_URL}/output/{filename}"))

    return ics_urls

def create_html(ics_urls):
    logging.info("Creating HTML file...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)  # Ensure output directory exists
    with open(HTML_FILE, "w") as f:
        f.write("<html>\n<head>\n<title>Boat Calendars</title>\n</head>\n<body>\n")
        f.write("<h1>Subscribe to Boat Calendars</h1>\n<ul>\n")
        for boat_name, url in ics_urls:
            f.write(f'<li><a href="{url}">{boat_name} Calendar</a></li>\n')
        f.write("</ul>\n</body>\n</html>")
    logging.info(f"HTML file created: {HTML_FILE}")

def main():
    logging.info("Starting the scraping process.")
    html = fetch_page()
    boats = parse_boats(html)
    if not boats:
        logging.warning("No boats found. Exiting.")
        return
    ics_urls = create_ics_files(boats)
    create_html(ics_urls)
    logging.info("Scraping process completed.")

if __name__ == "__main__":
    main()
