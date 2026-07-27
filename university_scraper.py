"""
university_scraper.py

Scrapes a set of pages per university and saves the cleaned text
into one JSON file per university, ready for chunking/embedding in a RAG pipeline.

Usage:
    python university_scraper.py

Edit the UNIVERSITIES dict below with the URLs you want to scrape for each school.
"""

import json
import time
import re
from pathlib import Path
from datetime import date

import sys

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from parsers import parse_pdf  # noqa: E402

# -----------------------------
# 1. CONFIGURE YOUR TARGETS
# -----------------------------
UNIVERSITIES = {
    "NED University": [
        "https://www.neduet.edu.pk/admission",
        "https://www.neduet.edu.pk/sites/default/files/Admissions-2026/Distribution_of_Seats.pdf",
        "https://www.neduet.edu.pk/sites/default/files/Admissions-2023/GuideLines.pdf",
        "https://www.neduet.edu.pk/sites/default/files/Admissions-2026/FAQ.pdf",
        "https://www.neduet.edu.pk/sites/default/files/Admissions-2025/sample_test_paper.pdf",
        "https://www.neduet.edu.pk/sites/default/files/Admissions-2026/Brochure_International_Students.pdf",
        "https://www.neduet.edu.pk/search/node?keys=scholarship",
        "https://www.neduet.edu.pk/sites/default/files/users/student_affairs/List%20of%20Scholarship.pdf",
        "https://www.neduet.edu.pk/academic_programmes",
        "https://www.neduet.edu.pk/hostel-facilities-students",
    ],
    "FAST University": [
        "https://www.nu.edu.pk/Admissions/EligibilityCriteria",
        "https://www.nu.edu.pk/Admissions/Schedule",
        "https://www.nu.edu.pk/Admissions/TestPattern",
        "https://www.nu.edu.pk/Admissions/FeeStructure",
        "https://cfd.nu.edu.pk/facilities/",
    ],
    "HABIB University": [
        "https://habib.edu.pk/admissions/student-finance/",
        "https://habib.edu.pk/admissions/admissions-faqs/",
        "https://habib.edu.pk/academics/sse/computer-science/",
        "https://habib.edu.pk/wp-content/uploads/2025/07/HU-Course-Catalog-2024-25.pdf",
        "https://habib.edu.pk/welcome-class/information-about-accommodation/",
    ],
    "IBA": [
        "https://cs.iba.edu.pk/bscs/eligibility-criteria.php",
        "https://www.iba.edu.pk/fee-structure.php",
        "https://cs.iba.edu.pk/bscs/courseoutline.php",
        "https://www.iba.edu.pk/News/past_entry_test/Past_Entry_Test_BS.html",
        "https://admissions.iba.edu.pk/pdf/test-syllabus-passing-criteria.pdf",
        "https://www.iba.edu.pk/scholarships.php",
        "https://www.iba.edu.pk/financialassistance/punjab-educational-endowment-fund2025-26.php",
        "https://www.iba.edu.pk/financialassistance/needbased.php",
        "https://iba.edu.pk/News/past_entry_test/BS_ecomth_EntryTestSyllabus.htm",
        "https://www.iba.edu.pk/student-residences.php",
    ],
    "SZABIST": [
        "https://szabist.edu.pk/admission-requirements/",
        "https://szabist.edu.pk/scholarships/",
        "https://szabist.edu.pk/fee-structure/",
        "https://szabist.edu.pk/programs/",
        {
            "url": "manual://szabist-bscs-entrance-test",
            "page_title": "SZABIST BS(CS) Entrance Test Pattern",
            "content": (
                "SZABIST's BS(CS) entrance test is a 90-minute, computer-based exam consisting of 100 "
                "multiple-choice questions (MCQs). The test is divided into four sections: English (30 marks), "
                "General Math (20 marks), IQ/Analytical (20 marks), and Basic Computer Knowledge (30 marks). "
                "English (30 Marks): Tests vocabulary (synonyms, antonyms), grammar, sentence completion, and "
                "reading comprehension. General Math (20 Marks): Focuses on basic arithmetic, ratios, percentages, "
                "algebra, and word problems. IQ and Analytical Skills (20 Marks): Measures logical reasoning, "
                "pattern recognition, and problem-solving. Computer Science (30 Marks): Tests fundamental IT "
                "concepts, including basic hardware, software, number systems, and programming logic."
            ),
            "tables": [],
        },
        {
            "url": "manual://szabist-hostel-info",
            "page_title": "SZABIST Hostel / Accommodation Information",
            "content": (
                "SZABIST University in Clifton, Karachi does not operate its own on-campus student housing. "
                "However, multiple highly-rated private hostels are located within a 5-to-10-minute walk or a "
                "short commute from the main campus. Monthly rents generally range from Rs. 15,000 to Rs. 35,000, "
                "depending on the room type (AC vs. non-AC) and mess facilities."
            ),
            "tables": [],
        },
    ],
    "DHA Suffa": [
        "https://www.dsu.edu.pk/wp-content/uploads/2024/08/sample_tes_paper_2024-UPDATE.pdf",
        "https://www.dsu.edu.pk/wp-content/uploads/2024/08/SCHOLARSHIP-AND-FEE-CONESSIION.pdf",
        "https://www.dsu.edu.pk/fee-structure/",
        "https://www.dsu.edu.pk/admission-merit-criteria/",
        "https://www.dsu.edu.pk/dck-hostel-facilities/",
        {
            "url": "manual://dsu-dck-hostel",
            "page_title": "DHA Suffa University DCK Girls Hostel",
            "content": (
                "DHA Suffa University operates a dedicated Girls Hostel located in Sector 3, DHA City Karachi "
                "(DCK), connected to the DSU DCK campus. It offers secure, furnished residential facilities for "
                "female students with 24/7 active security monitoring, modern living spaces, basic utilities, "
                "and a supportive study environment. For inquiries, contact DHA Suffa University at 111-178-332 "
                "or 0324-2444595."
            ),
            "tables": [],
        },
        {
            "url": "manual://dsu-phase7-hostel",
            "page_title": "DHA Suffa University Phase 7 Ext Hostel Options",
            "content": (
                "The DHA Suffa University Main Campus in DHA Phase 7 Extension does not have its own on-campus "
                "hostel. Several private girls' hostels operate nearby: Sayaban Girls Hostels (21-C 15th "
                "Commercial Street, DHA Phase 2 Extension) offers furnished AC/Non-AC rooms with meals and "
                "internet starting around Rs. 18,000 per month. H Girls Hostel (Street 4, Sector B, Akhtar "
                "Colony) offers attached bathrooms and independent kitchens. AL Safa Girls Hostel (Plot 58, "
                "Street No. 2, Sector D, Akhtar Colony) offers fully furnished rooms with dedicated female "
                "management."
            ),
            "tables": [],
        },
    ],
}

OUTPUT_DIR = Path("output_json")
OUTPUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (research/educational scraping bot; contact: you@example.com)"
}

REQUEST_DELAY_SECONDS = 2  # be polite, avoid hammering servers


# -----------------------------
# 2. HELPERS
# -----------------------------
def clean_text(text: str) -> str:
    """Collapse whitespace and strip junk."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_tables(soup: BeautifulSoup) -> list[dict]:
    """Extract data from tables found on the page."""
    tables = []
    for table in soup.find_all("table"):
        headers = []
        header_trs = []
        thead = table.find("thead")
        if thead:
            header_trs = thead.find_all("tr")
            # A grouped/spanning header (e.g. "Programs | One Time Charges |
            # Per Semester" as parent headers over several sub-columns) can
            # span multiple <tr> inside <thead> - flatten all of them into
            # one header list rather than only reading the first row.
            for tr in header_trs:
                headers.extend(clean_text(th.get_text(separator=" ")) for th in tr.find_all(["th", "td"]))
        else:
            first_row = table.find("tr")
            if first_row:
                header_trs = [first_row]
                headers = [clean_text(cell.get_text(separator=" ")) for cell in first_row.find_all(["th", "td"])]

        header_tr_ids = {id(tr) for tr in header_trs}
        rows = []
        for tr in table.find_all("tr"):
            # table.find_all("tr") isn't scoped to <tbody>, so a <tr> already
            # consumed above as a header row would otherwise ALSO be counted
            # as a data row here - that's what made a column header like
            # "Tuition Fee (Per Crd Hr.)" show up looking like a program name.
            if id(tr) in header_tr_ids:
                continue
            cells = tr.find_all(["th", "td"])
            if not cells:
                continue
            rows.append([clean_text(cell.get_text(separator=" ")) for cell in cells])

        tables.append({
            "headers": headers,
            "rows": rows,
        })
    return tables


def parse_panels(soup: BeautifulSoup) -> list[dict]:
    """Extract accordion/panel sections from the page."""
    panels = []
    for panel in soup.select("div.panel"):
        heading = panel.select_one(".panel-heading, .panel-title")
        body = panel.select_one(".panel-body")
        title = clean_text(heading.get_text(separator=" ")) if heading else ""
        body_text = clean_text(body.get_text(separator=" ")) if body else ""
        panel_tables = parse_tables(body) if body else []

        panels.append({
            "title": title,
            "content": body_text,
            "tables": panel_tables,
        })
    return panels


def _get(url: str, timeout: int) -> requests.Response:
    """GET with a scoped fallback for hosts whose server sends an incomplete
    cert chain (missing intermediate) rather than being genuinely untrusted -
    verified independently via openssl for szabist.edu.pk. Retrying with
    verify=False only on an SSL failure keeps default requests verified."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=True)
    except requests.exceptions.SSLError:
        print(f"  [!] SSL verification failed for {url}; retrying without verification (server has an incomplete cert chain).")
        resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=False)
    resp.raise_for_status()
    return resp


def scrape_pdf(url: str) -> dict:
    """Download a PDF and extract real text/tables via pdfplumber/fitz.

    BeautifulSoup can't parse PDF binary as HTML (it just yields garbage), so
    PDF URLs need their own path.
    """
    resp = _get(url, timeout=30)
    parsed = parse_pdf(resp.content)
    tables = [
        {"headers": t.get("header", []), "rows": t.get("rows", [])}
        for t in parsed.get("tables", [])
    ]
    return {
        "url": url,
        "page_title": url.split("/")[-1].split("?")[0],
        "content": clean_text(parsed.get("text", "")),
        "tables": tables,
        "panels": [],
    }


def scrape_page(url: str) -> dict:
    """Fetch a single page and extract title + main text content."""
    if url.lower().split("?")[0].endswith(".pdf"):
        return scrape_pdf(url)

    resp = _get(url, timeout=15)

    soup = BeautifulSoup(resp.text, "lxml")

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else url

    # Grab main content -- adjust selector per site if needed
    main = soup.find("main") or soup.find("article") or soup.body
    content = clean_text(main.get_text(separator=" ")) if main else ""
    tables = parse_tables(soup)
    panels = parse_panels(soup)

    return {
        "url": url,
        "page_title": title,
        "content": content,
        "tables": tables,
        "panels": panels,
    }


def get_extra_university_data(name: str) -> dict:
    """Provide supplemental data for specific universities."""
    if name != "NED University":
        return {}

    return {
        "test_pattern": {
            "title": "Pre-Admission Entry Test Subjects and Sections",
            "groups": [
                {
                    "name": "Pre-Engineering Group / DAE",
                    "hsc_subjects": ["Mathematics", "Physics", "Chemistry"],
                    "sections": ["English", "Mathematics", "Physics", "Chemistry"],
                },
                {
                    "name": "Pre-Medical Group",
                    "hsc_subjects": ["Biology", "Physics", "Chemistry"],
                    "sections": ["English", "Biology", "Physics", "Chemistry"],
                },
                {
                    "name": "Computer Science Group",
                    "hsc_subjects": ["Mathematics", "Physics", "Computer Science"],
                    "sections": ["English", "Mathematics", "Physics", "Computer Science"],
                },
                {
                    "name": "Computer Science Group (Mathematics, Statistics, Computer Science)",
                    "hsc_subjects": ["Mathematics", "Statistics", "Computer Science"],
                    "sections": ["English", "Mathematics", "Statistics", "Computer Science"],
                },
                {
                    "name": "Commerce Group",
                    "hsc_subjects": [],
                    "sections": ["English", "Accounting", "Economics", "Business Mathematics"],
                },
                {
                    "name": "Arts Group",
                    "hsc_subjects": [],
                    "sections": ["English 1", "English 2", "Basic Mathematics", "General Knowledge"],
                },
                {
                    "name": "Arts (Mathematics) Group",
                    "hsc_subjects": [],
                    "sections": ["English 1", "English 2", "Mathematics", "General Knowledge"],
                },
            ],
        }
    }


def scrape_university(name: str, sources: list) -> dict:
    """sources may mix plain URL strings (live-scraped) with pre-built page
    dicts (manually supplied content, e.g. test-pattern details given
    directly rather than published on any single page)."""
    pages = []
    for src in tqdm(sources, desc=f"Scraping {name}"):
        if isinstance(src, dict):
            pages.append(src)
            continue
        url = src
        try:
            page_data = scrape_page(url)
            pages.append(page_data)
        except Exception as e:
            print(f"  [!] Failed to scrape {url}: {e}")
        time.sleep(REQUEST_DELAY_SECONDS)

    return {
        "university": name,
        "scraped_at": str(date.today()),
        "pages": pages,
        **get_extra_university_data(name),
    }

def main():
    for name, urls in UNIVERSITIES.items():
        data = scrape_university(name, urls)

        safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower()).strip("_")
        out_path = OUTPUT_DIR / f"{safe_name}.json"

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()