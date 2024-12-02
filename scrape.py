import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
import logging
import os
import json
from datetime import datetime
from datetime import timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Base URL for scraping
BASE_URL = "https://jibe.sanjuansailing.com/a-vesseloverview.asp"

# GitHub Pages base URL
GITHUB_PAGES_URL = "https://sjs-calendar.github.io/ical"

# Directory to save output files
OUTPUT_DIR = "output"
ARCHIVE_DIR = os.path.join(OUTPUT_DIR, "archive")
HTML_FILE = os.path.join(OUTPUT_DIR, "index.html")

os.makedirs(ARCHIVE_DIR, exist_ok=True)

def fetch_page(year, month):
    """
    Fetch the webpage for a specific month and return its HTML content.
    """
    logging.info(f"Fetching the webpage for month {month}...")
    payload = {"DisplayMonth": month, "DisplayYear": year}  # POST parameter to change month
    response = requests.post(BASE_URL, data=payload)
    if response.status_code != 200:
        logging.error(f"Failed to fetch the page for month {month}. Status code: {response.status_code}")
        response.raise_for_status()
    logging.info(f"Page for month {month} fetched successfully.")
    return response.text

def parse_boats(html, year, month):
    """
    Parse the HTML content and extract boat information for a specific month.
    """
    logging.info(f"Parsing boats for month {year}/{month}...")
    soup = BeautifulSoup(html, "html.parser")
    boats = {}
    rows = soup.select("tr")

    for row in rows:
        # Find boat information
        boat_info = row.select_one(".fixedcol-a")
        if not boat_info:
            continue
        
        link_tag = boat_info.find("a")
        if not link_tag:
            continue

        boat_name = link_tag.text.strip()
        boat_days = row.find_all("td", class_=["CbgT", "CbgWE", "CbgM", "CbgB4Web"])
        #boat_days = row.find_all("td")

        availability = []
        for cell in boat_days:
            day_text = cell.get_text(strip=True)
            if not day_text.isdigit():
                logging.warning(f"Skipping non-numeric day cell: {day_text}")
                continue

            day = int(day_text)
            iso_date = datetime(year, month, day).isoformat()

            # Categorize based on class
            if "CbgM" in cell["class"]:  # Off-season or otherwise unavailable
                availability.append((iso_date, "Unavailable"))
            elif "CbgB4Web" in cell["class"]: # Booked
                availability.append((iso_date, "Booked"))
            #elif "CbgWE" in cell["class"]:  # Weekend (assuming available by default)
            #    availability.append((iso_date, "Available"))
            #elif "CbgT" in cell["class"]:  # Available
            #    availability.append((iso_date, "Available"))
            else:
                logging.debug(f"Unknown category for day {day}: {cell.get('class', [])}")

        if availability:
            boats[boat_name] = availability
            logging.info(f"Processed boat: {boat_name} for {year}/{month}")
    return boats
#
#
#
def get_range_status(day_status):
    grouped = []
    if not day_status:
        return grouped

    # sort the day_status by date
    day_status = sorted(day_status, key=lambda x: x[0])

    # Initialize the first range
    iso_start_date, status = day_status[0]

    # Convert iso_start_date to a datetime object for calculations
    start_date = datetime.fromisoformat(iso_start_date)
    end_date = start_date

    for current_date_str, current_status in day_status[1:]:
        current_date = datetime.fromisoformat(current_date_str)

        if current_status == status and (current_date - end_date).days == 1:
            # Extend the current range
            end_date = current_date
        else:
            # Close the current range and start a new one
            grouped.append((start_date.isoformat(), end_date.isoformat(), status))
            start_date, end_date, status = current_date, current_date, current_status

    # Add the final range
    grouped.append((start_date.isoformat(), end_date.isoformat(), status))

    # modify the beginning of year off-season unavailable to "last day off-season last"
    iso_start_date, iso_end_date, status = grouped[0]
    if status == "Unavailable":
        grouped[0] = (iso_end_date, iso_end_date, 'Last Day Off-Season')

    # do comparable for the end of year off-season unavailable
    iso_start_date, iso_end_date, status = grouped[-1]
    if status == "Unavailable":
        grouped[-1] = (iso_start_date, iso_start_date, 'First Day Off-Season')

    return grouped
#
#
#
def create_ics_files(range_boats):
    """
    Create a single ICS file for each boat based on availability.
    """
    logging.info("Creating ICS files...")
    ics_urls = []

    for boat, range_status in range_boats.items():
        calendar = Calendar()

        for start_date_iso, end_date_iso, status in range_status:
            # Convert ISO strings to datetime for operations
            start_date = datetime.fromisoformat(start_date_iso).date()
            end_date = datetime.fromisoformat(end_date_iso).date()

            event = Event()
            event.name = f"{boat} - {status}"
            event.begin = start_date
            event.end = end_date + timedelta(days=1)  # Add 1 day, DTEND is exclusive
            event.make_all_day()
            event.created = datetime.utcnow()
            calendar.events.add(event)

        # Generate file path
        filename = f"{boat.replace(' ', '_')}.ics"
        filepath = os.path.join(OUTPUT_DIR, filename)

        # Write the calendar to a file
        os.makedirs(OUTPUT_DIR, exist_ok=True)  # Ensure the output directory exists
        with open(filepath, "w") as f:
            f.writelines(calendar)
        
        logging.info(f"ICS file created: {filename}")
        ics_urls.append((boat, f"{GITHUB_PAGES_URL}/output/{filename}"))

    return ics_urls
#
#
#
def create_html(ics_urls):
    """
    Create an HTML file with links to all the ICS files.
    """
    logging.info("Creating HTML file...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(HTML_FILE, "w") as f:
        f.write("<html>\n<head>\n<title>Boat Calendars</title>\n</head>\n<body>\n")
        f.write("<h1>Subscribe to Boat Calendars</h1>\n")
        f.write('Use the urls below to subscribe to a calendar, e.g. for:<a href="https://calendar.google.com/calendar/u/0/r/settings/addbyurl">google calendar</a>\n<ul>\n')
        # sort the boats by name
        for boat_name, url in sorted(ics_urls, key=lambda x: x[0]):
            f.write(f'<li><code>{url}</code></li>\n')
        f.write("</ul>\n</body>\n</html>")
    logging.info(f"HTML file created: {HTML_FILE}")
#
#
#
def collect_boats(year, month, out_boats):
    # first look for boats.YYYY.MM.jsonl in output directory
    file = os.path.join(ARCHIVE_DIR, f"boats.{year}.{month:02d}.json")
    if os.path.exists(file):
        logging.info(f"Reading boat data from {file}")
        with open(file, "r") as f:
            boats = json.load(f)

    else:
        # if the file doesn't exist, fetch the page and parse the boats
        html = fetch_page(year, month)
        boats = parse_boats(html, year, month)

        # if year/month are in the past, save the data to a file
        curr_year = datetime.now().year
        curr_month = datetime.now().month
        if year < curr_year or (year == curr_year and month < curr_month):
            with open(file, "w") as f:
                json.dump(boats, f)
            logging.info(f"Boat data saved to {file}")

    for boat, day_status in boats.items():
        if boat not in out_boats:
            out_boats[boat] = day_status
        else:
            out_boats[boat].extend(day_status)
#
#     
#
def main():
    """
    Main function to orchestrate the scraping, ICS file creation, and HTML generation.
    """
    logging.info("Starting the scraping process.")

    year_boats = {}
    range_boats = {}
    current_year = datetime.now().year
    for year in range(current_year-1, current_year + 2):
        for month in range(3, 11):  # Loop thru march-october
            collect_boats(year, month, year_boats)

        # consolidate per year as range status
        for boat, day_status in year_boats.items():
            range_status = get_range_status(day_status)
            if boat not in range_boats:
                range_boats[boat] = range_status
            else:
                range_boats[boat].extend(range_status)
    
    if not range_boats:
        logging.warning("No boats found. Exiting.")
        return
    
    ics_urls = create_ics_files(range_boats)
    create_html(ics_urls)
    logging.info("Scraping process completed.")

if __name__ == "__main__":
    main()
