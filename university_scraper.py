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
from urllib.parse import urlparse

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
        "https://nu.edu.pk/Admissions/Scholarship",
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
    "UIT": [
        "https://uitu.edu.pk/faqs/",
        "https://uitu.edu.pk/information/",
        "https://uitu.edu.pk/fee-structure/",
        "https://uitu.edu.pk/how-to-apply/",
        "https://uitu.edu.pk/wp-content/uploads/2025/03/SAMPLE-PAPER-NEW.pdf",
        "https://uitu.edu.pk/fee-refund-policy/",
        "https://uitu.edu.pk/gat-results/",
        "https://uitu.edu.pk/prospectus/",
        "https://uitu.edu.pk/scholarship/",
        "https://uitu.edu.pk/outreach-program/",
        "https://uitu.edu.pk/rt-program/bs-computer-science/",
        "https://uitu.edu.pk/faculty-of-computing-sciences/department-of-computer-science/",
        "https://uitu.edu.pk/faculty-of-engineering-and-technology/department-of-electrical-engineering/",
        "https://uitu.edu.pk/faculty-of-engineering-and-technology/department-of-engineering-technology/",
        "https://uitu.edu.pk/faculty-of-management-and-social-sciences/department-of-management-and-social-sciences/",
        "https://uitu.edu.pk/student-affairs/",
        {
            "url": "manual://uit-entry-test",
            "page_title": "UIT University Entry Test (GAT) Format",
            "content": (
                "UIT University's own admission entry test is called the GAT (the university's own site "
                "uses this name throughout, e.g. GAT Results, without spelling out what it stands for). "
                "The GAT is a computer-based test with a duration of 60 minutes, covering three sections: "
                "English, Mathematics, and Analytical Skills. Applicants who have taken the SAT and scored "
                "at least 800 in SAT-I and 1500 in SAT-II (with Physics, Chemistry/Computer Science and "
                "Mathematics/Biology) are exempted from taking the GAT."
            ),
            "tables": [],
        },
    ],
    "Iqra University": [
        "https://iqra.edu.pk/admission-hub/",
        "https://iqra.edu.pk/life-at-iu/",
        {
            "url": "manual://iqra-fee-summary",
            "page_title": "Iqra University Fee Summary",
            "content": (
                "Iqra University fees in Karachi vary by program. Per-credit-hour tuition for standard "
                "undergraduate programs (Business, Computing, Social Sciences) ranges from approximately "
                "PKR 5,124 to PKR 7,100; specialized degrees like Law can charge higher per-credit rates, "
                "up to approximately PKR 18,750 before institutional discounts. Total semester costs "
                "generally fall between PKR 85,000 and PKR 150,000 or more depending on course load. "
                "There is a one-time admission fee of approximately PKR 15,000 to PKR 25,000, plus "
                "registration and miscellaneous charges of approximately PKR 6,800 to PKR 9,000 per "
                "semester for library, LMS, and extracurricular services. The university notes that "
                "tuition fees may increase by up to 10% each year."
            ),
            "tables": [],
        },
        {
            # admission-hub's own program names are scattered across dozens of
            # per-category eligibility paragraphs (e.g. "Bachelor's Programs
            # (BBA / BS Islamic Banking & Finance / BS Accounting & Finance /
            # BS Economics & Finance)"), not one clean "our programs" table -
            # extract_offered_courses can't isolate a title from a parenthesized
            # list buried in a requirements sentence. Every name below was
            # copied verbatim from that scattered admission-hub text (grepped
            # directly, not invented), just consolidated into one clean table
            # so the normal per-cell extraction path picks each one up as its
            # own program instead of losing them all to that prose.
            "url": "manual://iqra-programs",
            "page_title": "Iqra University Offered Programs",
            "content": "",
            "tables": [
                {
                    "headers": ["Program"],
                    "rows": [
                        ["Bachelor of Business Administration (BBA / BBA Honors)"],
                        ["BS Accounting & Finance"],
                        ["BS Economics & Finance"],
                        ["BS Islamic Banking & Finance"],
                        ["BS Computer Science"],
                        ["BS Software Engineering"],
                        ["BS Artificial Intelligence"],
                        ["BS Telecommunication"],
                        ["BS English (4-Year Program)"],
                        ["BS Fashion Design"],
                        ["BS Textile Design"],
                        ["BS Media Studies"],
                        ["BS Human Nutrition & Dietetics"],
                        ["Bachelor of Education (B.Ed)"],
                        ["Doctor of Pharmacy (Pharm.D.)"],
                        ["Doctor of Physical Therapy (DPT)"],
                        ["MBA (Master of Business Administration)"],
                        ["MS Computer Science"],
                        ["PhD in Computer Science"],
                        ["PhD in Business Administration"],
                    ],
                }
            ],
        },
    ],
    "Sir Syed University": [
        "https://www.ssuet.edu.pk/admissions/undergraduate-admissions/",
        "https://www.ssuet.edu.pk/admissions/postgraduate-admissions/",
        "https://www.ssuet.edu.pk/wp-content/uploads/UG-Admission-Policy-2025-26.pdf",
        "https://www.ssuet.edu.pk/wp-content/uploads/SSUET-FAQs.pdf",
        "https://www.ssuet.edu.pk/wp-content/uploads/HEC-Refund-Policy-Revised-2024.pdf",
        "https://www.ssuet.edu.pk/wp-content/uploads/SSUET-International-Students-Admissions.pdf",
        "https://www.ssuet.edu.pk/wp-content/uploads/SSUET-PhD-Policy-Ver-8-For-Batches-2024-Spring-and-Onwards.pdf",
        "https://www.ssuet.edu.pk/wp-content/uploads/SSUET-MS-Policy-Ver-4.pdf",
        {
            # Transcribed directly from a fee-structure image the user
            # provided (Fall 26 - Spring 27 admissions cycle) - not scraped
            # from a URL, since none of SSUET's 8 scraped pages contained
            # any actual PKR tuition figures. Every number here is copied
            # verbatim from that image, not invented or estimated.
            "url": "manual://ssuet-fee-structure-fall26-spr27",
            "page_title": "SSUET Undergraduate Fee Structure 2026-27",
            "content": (
                "Sir Syed University of Engineering & Technology (SSUET) undergraduate fee structure for "
                "Fall 2026 - Spring 2027. All fees are subject to annual revision. Self-Finance Admission Fee "
                "Policy: at admission, pay the full 1st semester fee plus PKR 250,000 (plus applicable taxes), "
                "via cash or pay order in favor of Sir Syed University of Engineering & Technology. A 5% "
                "withholding tax applies if the total fee paid during the year exceeds PKR 200,000. Refunds "
                "are processed in accordance with the HEC Refund Policy available on the SSUET website. "
                "Semester Freeze Policy (applicable from the 2nd semester onward): a semester can be frozen "
                "within 15 days of class start by paying the semester registration fee; if the student fails "
                "to freeze or register, the status is marked suspended, and reactivation requires paying the "
                "semester registration fee for each missed semester plus a PKR 10,000 reactivation charge. "
                "Extended Study (after the 4th year, applicable to Batch 2020 onward): for 9 or more credit "
                "hours, pay the semester registration fee plus the credit hour fee; for less than 9 credit "
                "hours, pay only the credit hour fee. For AIT graduates (BE Tech - Civil, Electrical, "
                "Electronics): the admission fee (PKR 15,000) is waived and there is a 30% tuition fee "
                "discount in BS programs (Civil, Electrical, Electronics & Biomedical Engineering); the entry "
                "application fee is PKR 1,000 across all programs. For industrial employees and their "
                "children: the same admission fee waiver and 30% tuition discount apply (Civil, Electrical, "
                "Electronics), with the same PKR 1,000 entry application fee."
            ),
            "tables": [
                {
                    "headers": [
                        "Program", "Admission (one time)", "Security Deposit (one time)", "Student Activity",
                        "Exam", "Semester Registration", "Tuition Fee (per Credit Hour)", "Credit Hours",
                        "Total Tuition Fee (1st Semester)", "Total Fee (1st Semester)",
                    ],
                    "rows": [
                        ["Electronic Engineering", "35,000", "5,000", "1,100", "5,200", "11,500", "6,600", "17", "112,200", "170,000"],
                        ["Biomedical Engineering", "35,000", "5,000", "1,100", "5,200", "11,500", "6,600", "16", "105,600", "163,400"],
                        ["Civil Engineering", "35,000", "5,000", "1,100", "5,200", "11,500", "6,600", "17", "112,200", "170,000"],
                        ["Electrical Engineering", "35,000", "5,000", "1,100", "5,200", "11,500", "6,600", "18", "118,800", "176,600"],
                        ["Computer Engineering", "35,000", "5,000", "1,100", "5,200", "11,500", "7,700", "16", "123,200", "181,000"],
                        ["Telecommunication Engineering", "35,000", "5,000", "1,100", "5,200", "5,750", "3,250", "16", "52,000", "104,050"],
                        ["Computer Science", "35,000", "5,000", "1,100", "5,200", "11,500", "7,700", "18", "138,600", "196,400"],
                        ["Information Technology", "35,000", "5,000", "1,100", "5,200", "11,500", "7,700", "18", "138,600", "196,400"],
                        ["Software Engineering", "35,000", "5,000", "1,100", "5,200", "11,500", "7,700", "18", "138,600", "196,400"],
                        ["Cyber Security", "35,000", "5,000", "1,100", "5,200", "11,500", "7,700", "18", "138,600", "196,400"],
                        ["Data Science", "35,000", "5,000", "1,100", "5,200", "11,500", "7,700", "17", "130,900", "188,700"],
                        ["Artificial Intelligence", "35,000", "5,000", "1,100", "5,200", "11,500", "7,700", "17", "130,900", "188,700"],
                        ["AI Security & Cyber Intelligence", "15,000", "5,000", "1,100", "3,000", "7,000", "4,600", "18", "78,200", "109,300"],
                        ["Internet of Things", "15,000", "5,000", "1,100", "3,000", "7,000", "4,600", "16", "73,600", "104,700"],
                        ["Intelligent Systems and Information Security", "15,000", "5,000", "1,100", "3,000", "7,000", "4,600", "17", "78,200", "109,300"],
                        ["Clinical Psychology", "35,000", "5,000", "1,100", "5,200", "11,500", "5,400", "18", "97,200", "155,000"],
                        ["Biotechnology", "35,000", "5,000", "1,100", "5,200", "5,750", "3,250", "18", "58,500", "110,550"],
                        ["Interior Design", "35,000", "5,000", "1,100", "5,200", "11,500", "6,600", "18", "118,800", "176,600"],
                        ["Computer Network & Security", "15,000", "5,000", "1,100", "3,000", "7,000", "4,600", "18", "82,800", "113,900"],
                        ["Medical Technology", "15,000", "5,000", "1,100", "3,000", "3,000", "3,500", "18", "63,000", "90,100"],
                        ["Robotics and Intelligent Machines", "15,000", "5,000", "1,100", "3,000", "7,000", "4,600", "16", "73,600", "104,700"],
                        ["Renewable Energy System", "15,000", "5,000", "1,100", "3,000", "7,000", "4,600", "18", "82,800", "113,900"],
                        ["Gaming and Animation", "15,000", "5,000", "1,100", "3,000", "7,000", "4,400", "17", "74,800", "105,900"],
                        ["Cloud Computing & Information Science", "15,000", "5,000", "1,100", "3,000", "7,000", "3,500", "17", "59,500", "90,600"],
                        ["Food Science & Tech.", "15,000", "5,000", "1,100", "3,000", "3,000", "3,500", "17", "59,500", "86,600"],
                        ["BBA", "15,000", "5,000", "1,100", "3,000", "7,000", "4,700", "17", "79,900", "111,000"],
                        ["Business & Information Technology", "15,000", "5,000", "1,100", "3,000", "7,000", "4,700", "18", "84,600", "115,700"],
                        ["Business Analytics", "15,000", "5,000", "1,100", "3,000", "7,000", "5,400", "17", "91,800", "122,900"],
                        ["Entrepreneurship", "15,000", "5,000", "1,100", "3,000", "7,000", "4,700", "17", "79,900", "111,000"],
                        ["BE Tech (Computer)", "15,000", "5,000", "1,100", "3,000", "5,000", "4,600", "18", "82,800", "111,900"],
                        ["BE Tech (Artificial Intelligence)", "15,000", "5,000", "1,100", "3,000", "5,000", "4,600", "17", "78,200", "107,300"],
                        ["BE Tech (Software)", "15,000", "5,000", "1,100", "3,000", "5,000", "4,600", "17", "78,200", "107,300"],
                        ["BE Tech (Electrical)", "15,000", "5,000", "1,100", "3,000", "5,000", "4,600", "16", "73,600", "102,700"],
                        ["BE Tech (Civil)", "15,000", "5,000", "1,100", "3,000", "5,000", "4,600", "18", "82,800", "111,900"],
                    ],
                },
                {
                    # Bachelor of Architecture has its own table in the source
                    # image, with an extra Studio Fee column - kept separate
                    # rather than jammed into the schema above and losing
                    # that figure.
                    "headers": [
                        "Program", "Admission (one time)", "Security Deposit (one time)", "Student Activity",
                        "Exam", "Semester Registration", "Studio Fee", "Tuition Fee (per Credit Hour)",
                        "Credit Hours", "Total Tuition Fee (1st Semester)", "Total Fee (1st Semester)",
                    ],
                    "rows": [
                        ["Bachelor of Architecture", "35,000", "5,000", "1,100", "5,200", "11,500", "20,500", "6,600", "18", "118,800", "197,100"],
                    ],
                },
            ],
        },
        {
            # None of SSUET's scraped pages mention hostel/accommodation at
            # all - confirmed directly by the user (who has closer knowledge
            # of the campus than anything scrapable) that SSUET has no
            # hostel, rather than leaving hostel_available as an unconfirmed
            # unknown.
            "url": "manual://ssuet-no-hostel",
            "page_title": "SSUET Hostel / Accommodation",
            "content": (
                "Sir Syed University of Engineering & Technology (SSUET) does not provide or operate an "
                "on-campus hostel or student housing facility."
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


# Only szabist.edu.pk is confirmed (independently, via openssl s_client) to
# send an incomplete intermediate cert chain rather than being genuinely
# untrusted. The verify=False retry below must stay scoped to that specific
# host - catching every SSLError regardless of host would silently downgrade
# to an insecure connection for a real cert problem (expired cert, wrong
# hostname, actual MITM) on any other site too.
_SSL_BYPASS_HOSTS = {"szabist.edu.pk", "www.szabist.edu.pk"}


def _get(url: str, timeout: int) -> requests.Response:
    """GET with a scoped fallback for szabist.edu.pk's incomplete cert chain.
    Every other host's SSL errors propagate normally instead of silently
    retrying without verification."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=True)
    except requests.exceptions.SSLError:
        host = urlparse(url).netloc.lower()
        if host not in _SSL_BYPASS_HOSTS:
            raise
        print(f"  [!] SSL verification failed for {url}; retrying without verification (known incomplete cert chain on {host}).")
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