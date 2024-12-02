import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
import logging
import os
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
HTML_FILE = os.path.join(OUTPUT_DIR, "index.html")

def fetch_page(month, year):
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

def parse_boats(html, month):
    """
    Parse the HTML content and extract boat information for a specific month.
    """
    logging.info(f"Parsing boats for month {month}...")
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
        #boat_days = row.find_all("td", class_=["CbgT", "CbgWE", "CbgM", "CbgB4Web"])
        boat_days = row.find_all("td")

        availability = []
        for cell in boat_days:
            day_text = cell.get_text(strip=True)
            if not day_text.isdigit():
                logging.warning(f"Skipping non-numeric day cell: {day_text}")
                continue

            day = int(day_text)

            # Categorize based on class
            if "CbgM" in cell["class"]:  # Off-season
                availability.append((datetime(2024, month, day), "Off-season"))
            elif "CbgB4Web" in cell["class"]:  # Unavailable
                availability.append((datetime(2024, month, day), "Unavailable"))
            elif "CbgWE" in cell["class"]:  # Weekend (assuming available by default)
                availability.append((datetime(2024, month, day), "Available"))
            elif "CbgT" in cell["class"]:  # Available
                availability.append((datetime(2024, month, day), "Available"))
            else:
                logging.debug(f"Unknown category for day {day}: {cell.get('class', [])}")

        if availability:
            boats[boat_name] = availability
            logging.info(f"Processed boat: {boat_name} for month {month}.")
    return boats
#
#
#
def group_consecutive_days(availability):
    grouped = []
    if not availability:
        return grouped

    # Initialize the first range
    start_date, status = availability[0]
    end_date = start_date

    for current_date, current_status in availability[1:]:
        if current_status == status and (current_date - end_date).days == 1:
            # Extend the current range
            end_date = current_date
        else:
            # Close the current range and start a new one
            grouped.append((start_date, end_date, status))
            start_date, end_date, status = current_date, current_date, current_status

    # Add the final range
    grouped.append((start_date, end_date, status))
    return grouped
#
#
#
def create_ics_files(boats):
    """
    Create a single ICS file for each boat based on availability.
    """
    logging.info("Creating ICS files...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ics_urls = []

    for boat, availability in boats.items():
        calendar = Calendar()

        # consecutive days of the same event type are one event
        grouped_availability = group_consecutive_days(availability)

        for start_date, end_date, status in grouped_availability:
            event = Event()
            event.name = f"{boat} - {status}"
            event.begin = start_date.isoformat()

            # Set the end time to the day after `end_date`, starting at midnight
            event.end = (end_date + timedelta(days=1)).replace(hour=0, minute=0, second=0).isoformat()
            event.created = datetime.utcnow()
            calendar.events.add(event)
        
        filename = f"{boat.replace(' ', '_')}.ics"
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "w") as f:
            f.writelines(calendar)
        logging.info(f"ICS file created: {filename}")
        ics_urls.append((boat, f"{GITHUB_PAGES_URL}/output/{filename}"))

    return ics_urls

def create_html(ics_urls):
    """
    Create an HTML file with links to all the ICS files.
    """
    logging.info("Creating HTML file...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(HTML_FILE, "w") as f:
        f.write("<html>\n<head>\n<title>Boat Calendars</title>\n</head>\n<body>\n")
        f.write("<h1>Subscribe to Boat Calendars</h1>\n<ul>\n")
        # sort the boats by name
        for boat_name, url in sorted(ics_urls, key=lambda x: x[0]):
            f.write(f'<li><a href="{url}">{boat_name} Calendar</a></li>\n')
        f.write("</ul>\n</body>\n</html>")
    logging.info(f"HTML file created: {HTML_FILE}")

def main():
    """
    Main function to orchestrate the scraping, ICS file creation, and HTML generation.
    """
    logging.info("Starting the scraping process.")
    all_boats = {}
    for month in range(3, 11):  # Loop thru march-october
        html = fetch_page(month, 2025)
        boats = parse_boats(html, month)
        for boat, avail_list in boats.items():
            if boat not in all_boats:
                all_boats[boat] = avail_list
            else:
                all_boats[boat].extend(avail_list)
    
    if not all_boats:
        logging.warning("No boats found. Exiting.")
        return
    
    ics_urls = create_ics_files(all_boats)
    create_html(ics_urls)
    logging.info("Scraping process completed.")

if __name__ == "__main__":
    main()
