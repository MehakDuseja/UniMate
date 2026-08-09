"""parsers.py

PDF parsing utilities: extract text and tables from PDFs using pdfplumber
with an optional PyMuPDF (fitz) fallback for text extraction when needed.

Functions:
 - parse_pdf(path_or_bytes) -> dict with keys: text, tables, metadata
 - extract_text_pdf_pdfplumber(path) -> str
 - extract_text_pdf_fitz(path) -> str
 - extract_tables_pdfplumber(path) -> list[dict]
"""
from __future__ import annotations

import io
import logging
import re
from typing import List, Dict, Any

try:
    import pdfplumber
except Exception:  # pragma: no cover - imported at runtime
    pdfplumber = None

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

logger = logging.getLogger(__name__)


def _as_pdfplumber_source(path: str | bytes):
    """pdfplumber.open() accepts a file path or an actual file-like object,
    but NOT a raw bytes object - passed straight through, it fails inside
    pdfplumber with "'bytes' object has no attribute 'seek'" (unlike fitz,
    which explicitly supports bytes via stream=path, filetype="pdf"). Wrap
    bytes/bytearray in BytesIO so callers can keep passing scrape_pdf's raw
    resp.content straight through."""
    if isinstance(path, (bytes, bytearray)):
        return io.BytesIO(path)
    return path


def extract_text_pdf_pdfplumber(path: str | bytes) -> str:
    """Extract plain text from a PDF using pdfplumber.

    Accepts a file path or bytes object. Returns extracted text as a single string.
    """
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is not installed")

    text_parts: List[str] = []
    with pdfplumber.open(_as_pdfplumber_source(path)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

    return "\n\n".join(text_parts).strip()


def extract_text_pdf_fitz(path: str | bytes) -> str:
    """Fallback text extraction using PyMuPDF (fitz).

    Returns the concatenated text of all pages.
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed")

    # fitz.open can accept bytes or a filename
    doc = fitz.open(stream=path, filetype="pdf") if isinstance(path, (bytes, bytearray)) else fitz.open(path)
    parts: List[str] = []
    for page in doc:
        parts.append(page.get_text())
    doc.close()
    return "\n\n".join(parts).strip()


def extract_tables_pdfplumber(path: str | bytes) -> List[Dict[str, Any]]:
    """Extract tables from a PDF using pdfplumber.

    Returns a list of tables. Each table is a dict with keys: page (int), rows (list[list[str]]).
    """
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is not installed")

    tables: List[Dict[str, Any]] = []
    with pdfplumber.open(_as_pdfplumber_source(path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            try:
                page_tables = page.extract_tables()
            except Exception:
                page_tables = []

            for table in page_tables:
                # table is a list of rows; each row is a list of cell strings (or None)
                rows = [[(cell or "").strip() for cell in row] for row in table]
                tables.append({"page": i, "rows": rows})

    return tables


def guess_table_headers(table_rows: List[List[str]]) -> List[str] | None:
    """Simple heuristic to decide if first row is header-like.

    Returns header list or None if unclear.
    """
    if not table_rows:
        return None
    first = table_rows[0]
    # heuristic: if most cells in first row are non-numeric and non-empty
    non_empty = sum(1 for c in first if c and not c.strip().replace("%", "").replace(".", "").isdigit())
    if non_empty >= max(1, len(first) // 2):
        return first
    return None


def parse_pdf(path: str | bytes) -> Dict[str, Any]:
    """High-level PDF parse: extract text + tables + metadata where possible.

    Returns dict: {"text": str, "tables": [...], "metadata": {...}}
    """
    result: Dict[str, Any] = {"text": "", "tables": [], "metadata": {}}

    # Try pdfplumber text extraction first
    if pdfplumber is not None:
        try:
            result["text"] = extract_text_pdf_pdfplumber(path)
        except Exception as e:
            logger.warning("pdfplumber text extraction failed: %s", e)

    # If text is empty and fitz is available, try fallback
    if (not result["text"].strip()) and fitz is not None:
        try:
            result["text"] = extract_text_pdf_fitz(path)
        except Exception as e:
            logger.warning("fitz text extraction failed: %s", e)

    # Extract tables with pdfplumber when available
    if pdfplumber is not None:
        try:
            raw_tables = extract_tables_pdfplumber(path)
            # add simple header guesses
            tables_with_meta = []
            for t in raw_tables:
                header = guess_table_headers(t["rows"]) or []
                tables_with_meta.append({"page": t["page"], "header": header, "rows": t["rows"]})
            result["tables"] = tables_with_meta
        except Exception as e:
            logger.warning("pdfplumber table extraction failed: %s", e)

    # minimal metadata placeholder
    result["metadata"] = {"parser": "pdfplumber+fitz", "pages_extracted": len(result["text"].split('\f'))}

    return result


NOISE_PATTERNS = [
    "home about", "menu", "search close menu", "faculty students alumni staff", "copyright", "privacy policy", "terms of use",
    "apply online", "program planning guide", "financial assistance", "admissions undergraduate programs", "postgraduate programs",
    "centers of excellence", "student portal", "faculty portal", "office of the registrar", "academic calendar", "social networks",
    "view other fee structures", "download"  # common header/footer noise
]


def clean_page_text(raw_text: str) -> str:
    text = raw_text.replace("\u2028", " ").replace("\u2029", " ").replace("\ufeff", " ")
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_noise_text(text: str) -> bool:
    lower = text.lower()
    if any(pattern in lower for pattern in NOISE_PATTERNS):
        return True
    # noise often contains repeated university/site navigation terms
    repeated_tokens = sum(lower.count(token) for token in ["admissions", "programs", "undergraduate", "graduate", "mba", "fee structure"])
    if repeated_tokens >= 2 and len(text) > 50:
        return True
    # discard lines with too little alphabetic content
    alpha = len(re.findall(r"[A-Za-z]", text))
    if alpha < max(10, len(text) * 0.4):
        return True
    # PDFs with undecodable custom font encodings sometimes yield raw
    # control-byte garbage that still has enough scattered ASCII letters to
    # pass the alpha-ratio check above; catch it separately.
    control_chars = sum(1 for ch in text if ord(ch) < 32 and ch not in "\n\t\r")
    if control_chars > len(text) * 0.05:
        return True
    # The more common failure mode: undecodable bytes surface as the Unicode
    # replacement character (U+FFFD) rather than low control codes, and can
    # be a small fraction of a long snippet while still marking the whole
    # thing as corrupted (e.g. one garbled PDF section merged into an
    # otherwise-readable multi-KB snippet by weak sentence splitting).
    if text.count("�") > len(text) * 0.02:
        return True
    return False


def split_text_snippets(text: str) -> list[str]:
    text = clean_page_text(text)
    parts = re.split(r'(?<=[.!?])\s+|\n+', text)
    snippets = [p.strip() for p in parts if p.strip()]
    return [snippet for snippet in snippets if not is_noise_text(snippet)]


def classify_page_types(url: str | None, title: str | None) -> set[str]:
    value = " ".join([url or "", title or ""]).lower()
    types: set[str] = set()
    if any(token in value for token in ["eligibil", "eligible"]):
        types.add("eligibility")
    if any(token in value for token in ["test pattern", "entry test", "past entry", "admissions/testpattern", "aptitude"]):
        types.add("test_pattern")
    if any(token in value for token in ["fee", "tuition", "hostel", "transport", "finance"]):
        types.add("fee")
    if any(token in value for token in ["scholar", "financial assistance", "bursary", "grant"]):
        types.add("scholarship")
    if any(token in value for token in ["course", "program", "curriculum", "offeredprogram", "courseoutline"]):
        types.add("courses")
    if not types:
        types.add("all")
    return types


def contains_program_indicator(text: str) -> bool:
    lower = text.lower()
    return bool(re.search(r"\b(?:bs|b\.s\.|bsc|ms|m\.s\.|phd|ph\.d|bachelor|master|doctor|pharm\.?d|dpt|engineering|computer science|software engineering|data science|cyber security|business administration|accounting and finance|economics|mathematics|information technology)\b", lower))


def extract_snippets(text: str, keywords: list[str], max_snippets: int = 5) -> list[str]:
    # Word-boundary match, not substring: plain "in" checks let e.g. "support"
    # match inside "air-supported" (a reading-comprehension passage in a
    # sample test PDF), misclassifying unrelated prose as scholarship info.
    # Trailing "s?" allows simple plurals ("scholarship" -> "scholarships")
    # without reopening the door to prefix matches like "support" in
    # "supported" (which has more than just a trailing "s" after it).
    patterns = [re.compile(r"\b" + re.escape(keyword.lower()) + r"s?\b") for keyword in keywords]
    snippets: list[str] = []
    for snippet in split_text_snippets(text):
        lower = snippet.lower()
        if any(p.search(lower) for p in patterns):
            snippets.append(snippet)
            if len(snippets) >= max_snippets:
                break
    return snippets


def extract_eligibility(content: str) -> list[str]:
    keywords = ["eligibility", "minimum marks", "must have", "required to apply", "eligible", "merit list", "admission test"]
    return extract_snippets(content, keywords, max_snippets=8)


def extract_test_pattern(content: str) -> list[str]:
    keywords = ["test pattern", "aptitude test", "admission test", "entry test", "sat", "interview", "weightage", "negative marking", "section"]
    return extract_snippets(content, keywords, max_snippets=8)


def extract_scholarships(content: str) -> list[str]:
    keywords = ["scholarship", "financial aid", "fee concession", "funding", "support", "grant", "bursary", "assistance"]
    return extract_snippets(content, keywords, max_snippets=6)


def extract_hostel_info(content: str) -> list[str]:
    keywords = ["hostel", "dormitory", "student housing", "accommodation", "residence", "boarding"]
    return extract_snippets(content, keywords, max_snippets=6)


def is_course_catalog_line(text: str) -> bool:
    if re.search(r"\b(CSE|MTS|SSC|SCI|HUM|ENG|PHY|MATH|BIO|ECE|EEE)\d{2,3}\b", text):
        return True
    if re.search(r"\b(Course Code|Credit hours|Semester|Program Core|General Education|CS Core|Elective|Required Courses|Course Title|Duration|Total)\b", text, re.I):
        return True
    if re.search(r"\b(Section/Topic|Grade|Course Category|Hours|Prerequisite|Pre-requisite|Category)\b", text, re.I):
        return True
    return False


def contains_cost_info(text: str) -> bool:
    lower = text.lower()
    return bool(re.search(r"\b(rs|pkr|rupees|fee|fee per credit hour|student activity charges|hostel|transport|amount|admission charges|security deposit|transfer fee|refund|credit hour|per semester)\b", lower))


NON_COURSE_MARKERS = [
    "weightage", "selection criteria", "courses studied at", "admission test",
    "merit list", "negative marking", "past academic record", "cut-off",
    # No trailing space on "eligibility" - a program name never legitimately
    # contains that word, but a sentence describing one might phrase it any
    # number of ways ("Eligibility:", "eligibility criteria", "not eligible
    # for"), and a hardcoded "eligibility " (space-terminated) missed cases
    # like "...Eligibility: Candidate must have..." where a colon follows
    # instead of a space, letting that whole sentence through as a fake
    # "course name".
    "eligibility", "ibcc", "hssc", "selection weightage",
]

GENERIC_CATEGORY_LABELS = {"engineering", "business administration", "computing", "computer science", "science"}

# A real program name is a short title that *starts* with a degree marker
# (e.g. "Bachelor of Science (Civil Engineering)", "BS-Computer Sciences").
# contains_program_indicator alone is too loose: prose like "Habib University's
# Bachelors of Computer Science degree cultivates..." or FAQ text ("What is the
# job of Computer Science graduates?") mentions the same keywords without being
# a course title, so it must anchor at the start, not match anywhere.
PROGRAM_START_RE = re.compile(
    r"^(bachelor\b(?:'s)?(?:\s+of)?|master\b(?:'s)?(?:\s+of)?|doctor\s+of|associate\s+of|"
    r"bs[\s\-(]|bs$|b\.s\.|bba\b|ms[\s\-(]|ms$|m\.s\.|mba\b|phd\b|ph\.d\.?|be\b|b\.e\.|"
    r"m\.?engg\.?\b|mem\b)",
    re.I,
)

# PDF/table extraction sometimes appends a section-boundary heading straight
# onto a real program name with no separator (e.g. Habib's course catalog PDF
# yields "BS in Computer Science Faculty Faculty Designation Dr."). Truncate
# at the marker instead of rejecting the whole candidate - the prefix is
# usually a genuine program name.
_GARBLE_SUFFIX_RE = re.compile(r"\b(faculty|designation)\b", re.I)

# Some program tables pack multiple degrees into one cell as repeated
# "<N> years <Degree> Programme <name(s)>" blocks (e.g. NED's department ->
# programmes table). Split on the duration marker that precedes each block.
_DURATION_SPLIT_RE = re.compile(r"(?=\d+(?:\.\d+)?\s*years?\b)", re.I)
_DURATION_PREFIX_RE = re.compile(r"^\d+(?:\.\d+)?\s*years?\s*", re.I)


def _split_program_blocks(cell: str) -> list[str]:
    blocks = _DURATION_SPLIT_RE.split(cell)
    return [_DURATION_PREFIX_RE.sub("", b).strip() for b in blocks if b.strip()]


def looks_like_program_name(candidate: str) -> bool:
    lower = candidate.lower()
    if any(marker in lower for marker in NON_COURSE_MARKERS):
        return False
    if lower in GENERIC_CATEGORY_LABELS:
        return False
    if re.match(r"^\d", candidate) or candidate.startswith((")", "(", "-", "/")):
        return False
    if "?" in candidate:
        return False
    # PDF table extraction sometimes flattens multiple columns into one line
    # of text, jumbling several unrelated program names together (e.g. "BS in
    # Development Equivalent) Studies, (Maths, Statistics, ...) Management
    # Sciences, ..."). A real single program title rarely has this many
    # commas or mismatched parens, so treat that as a sign of garbled text
    # rather than a real course - better to have no entry than a fabricated
    # one.
    if candidate.count(",") > 2 or candidate.count("(") != candidate.count(")"):
        return False
    return bool(PROGRAM_START_RE.match(candidate.strip()))


def extract_offered_courses(content: str, tables: list[dict]) -> list[str]:
    courses: list[str] = []

    def add_course(candidate: str) -> None:
        candidate = re.sub(r"^(degree)\s+", "", candidate.strip(), flags=re.I).strip()
        garble = _GARBLE_SUFFIX_RE.search(candidate)
        if garble and garble.start() > 10:
            candidate = candidate[: garble.start()].strip()
        if len(candidate) < 5 or is_noise_text(candidate) or is_course_catalog_line(candidate) or contains_cost_info(candidate):
            return
        if not looks_like_program_name(candidate):
            return
        if len(candidate.split()) > 30:
            return
        if candidate not in courses:
            courses.append(candidate)

    for table in tables:
        for row in table.get("rows", []):
            # Try each cell on its own FIRST - a program name sitting in its
            # own column (e.g. a fee table's "Programs" column, separate from
            # "Admission Fee"/"Security Deposit"/... columns) is the cleanest
            # possible candidate, and the row-joined fallback below would
            # otherwise swallow it: joining a whole fee-table row pulls in
            # every price figure too, and enough comma-formatted PKR amounts
            # (25,000 | 15,000 | 9,000 | ...) push the joined string over
            # looks_like_program_name's comma-count guard, silently
            # discarding a program name that was perfectly extractable on
            # its own. Only fall back to the row-joined text (needed for a
            # name that's split across cells with no single cell matching
            # alone) when no cell in this row matched by itself.
            matched_cell = False
            for cell in row:
                if not isinstance(cell, str):
                    continue
                cell = cell.strip()
                if contains_program_indicator(cell):
                    for block in _split_program_blocks(cell):
                        add_course(block)
                    matched_cell = True
            if matched_cell:
                continue
            joined = " ".join(cell.strip() for cell in row if isinstance(cell, str) and cell.strip())
            if joined and contains_program_indicator(joined):
                for block in _split_program_blocks(joined):
                    add_course(block)
    if len(courses) >= 10:
        return courses[:20]

    for snippet in split_text_snippets(content):
        if contains_program_indicator(snippet):
            add_course(snippet)
            if len(courses) >= 20:
                break
    return courses


_FEE_LABEL_STOPWORDS = {
    "program", "amount in pkr", "fee", "fee per credit hour",
    "student activity charges", "timeline", "one-time charges",
}

# A table with no real <thead> falls back to treating its literal first <tr>
# as the header (see parse_tables()) - for a plain two-column "label | amount"
# list table, that first row is really just the first data entry, not column
# labels. A genuine header cell reads as text ("Tuition Fee (Per Crd Hr.)");
# a data cell reads as a bare amount ("Rs. 2,000", "30,000"). If most of the
# "header" row looks like amounts, it's not a header at all - don't use it to
# label other rows' values.
_AMOUNT_LIKE_RE = re.compile(r"^(rs\.?|pkr|us\s*\$|\$|£)?\s*[\d,]+(\.\d+)?%?/?-?$", re.I)

# A real currency mention has "Rs"/"PKR" adjacent to a number - unlike a bare
# "rs" substring check, this doesn't false-positive on ordinary words like
# "scholarships" or "years" that merely happen to contain that letter pair.
_FEE_CURRENCY_RE = re.compile(r"\bpkr\b|\brupees\b|\bsemester\b|\bcredit\b|\brs\.?\s*[\d,]", re.I)


def _looks_like_real_header(headers: list[str]) -> bool:
    if not headers:
        return False
    amount_like = sum(1 for h in headers if _AMOUNT_LIKE_RE.match(h.strip()))
    return amount_like <= len(headers) * 0.3


def _is_noise_fee_label(text: str) -> bool:
    """is_noise_text()'s alpha-count floor (>=10 letters, or 40% of length)
    is tuned for filtering short prose/navigation fragments and incorrectly
    rejects legitimate short fee-table labels like "BBA / BS", "MS", or
    "PhD" - a table cell is a structurally different context from running
    text, so labels get the noise-pattern and garbled-encoding checks only,
    not the length-based prose heuristics."""
    lower = text.lower()
    if any(pattern in lower for pattern in NOISE_PATTERNS):
        return True
    if text.count("�") > len(text) * 0.02:
        return True
    return False


def extract_fee_structure(content: str, tables: list[dict]) -> dict[str, list[dict[str, str]]]:
    fee_entries: list[dict[str, str]] = []
    for table in tables:
        raw_headers = [h.strip() for h in table.get("headers", []) if isinstance(h, str) and h.strip()]
        headers_lower = [h.lower() for h in raw_headers]
        # "program" alone is too loose a trigger - admission-schedule and
        # test-weightage tables also use headers like "Undergraduate
        # Programs | Graduate Programs" with no fee data at all. Every real
        # fee table observed so far already has "fee" or "amount" in at
        # least one header cell (e.g. "Admission Fee"), so dropping the
        # standalone "program" trigger doesn't lose real fee tables.
        if not (any("fee" in h for h in headers_lower) or any("amount" in h for h in headers_lower)):
            continue
        header_is_real = _looks_like_real_header(raw_headers)
        for row in table.get("rows", []):
            cells = [c.strip() if isinstance(c, str) else "" for c in row]
            non_empty = [c for c in cells if c]
            if len(non_empty) < 2:
                continue
            label = non_empty[0]
            if not _is_noise_fee_label(label) and label.lower() not in _FEE_LABEL_STOPWORDS:
                # When the row lines up 1:1 with a genuine header row, pair
                # each value with its column header ("Tuition Fee (Per Crd
                # Hr.): 6,270") instead of a blind " | "-joined blob, so the
                # billing period (per semester vs. per credit hour vs. gross
                # vs. net) survives instead of collapsing into an unlabeled
                # string of numbers.
                if header_is_real and len(raw_headers) == len(cells):
                    value = " | ".join(f"{h}: {v}" for h, v in zip(raw_headers[1:], cells[1:]) if v)
                else:
                    value = " | ".join(non_empty[1:])
                if value and value.lower().strip() not in {"fee", "amount in pkr", "program"}:
                    fee_entries.append({"label": label, "value": value})
    if not fee_entries:
        for snippet in split_text_snippets(content):
            lower = snippet.lower()
            # Bare "rs" as a substring check matches inside ordinary words
            # like "schola-RS-hips" or "yea-RS" - that previously let
            # scholarship-policy prose ("The Scholarships and Fee Concession
            # Policy...") through as if it were a real fee figure. Require
            # "Rs" to actually be followed by a number, as in a real currency
            # mention ("Rs. 500", "Rs 30,000").
            has_currency = bool(_FEE_CURRENCY_RE.search(lower))
            if "fee" in lower and has_currency:
                fee_entries.append({"label": "fee_snippet", "value": snippet})
                if len(fee_entries) >= 5:
                    break
    return {"fees": fee_entries}


def parse_scraped_page(page: dict) -> dict:
    content = page.get("content", "") or ""
    tables = page.get("tables", []) or []
    page_types = classify_page_types(page.get("url"), page.get("page_title"))
    include_all = "all" in page_types

    # Only eligibility vs. test_pattern actually duplicate each other: both
    # extractors key off overlapping phrases like "admission test", so a page
    # that's clearly *one* of the two shouldn't also feed the other. Courses
    # and scholarships don't have that collision and are frequently embedded
    # inside the eligibility/fee pages rather than on their own dedicated
    # page, so they stay unconditional.
    return {
        "url": page.get("url"),
        "page_title": page.get("page_title"),
        "eligibility_criteria": extract_eligibility(content) if (include_all or "eligibility" in page_types) else [],
        "test_pattern": extract_test_pattern(content) if (include_all or "test_pattern" in page_types) else [],
        "scholarships": extract_scholarships(content),
        "offered_courses": extract_offered_courses(content, tables),
        "fee_structure": extract_fee_structure(content, tables),
        "hostel_info": extract_hostel_info(content),
        "raw_text": content[:2000],
    }


def parse_scraped_university(data: dict, location: str | None = None) -> dict:
    parsed_pages = [parse_scraped_page(page) for page in data.get("pages", [])]
    combined = {
        "university": data.get("university"),
        "scraped_at": data.get("scraped_at"),
        "location": location,
        "pages": parsed_pages,
        "aggregated": {
            "eligibility_criteria": [],
            "test_pattern": [],
            "scholarships": [],
            "offered_courses": [],
            "fee_structure": [],
            "hostel_info": [],
        },
    }
    for page in parsed_pages:
        combined["aggregated"]["eligibility_criteria"].extend(page["eligibility_criteria"])
        combined["aggregated"]["test_pattern"].extend(page["test_pattern"])
        combined["aggregated"]["scholarships"].extend(page["scholarships"])
        combined["aggregated"]["offered_courses"].extend(page["offered_courses"])
        combined["aggregated"]["fee_structure"].append(page["fee_structure"])
        combined["aggregated"]["hostel_info"].extend(page["hostel_info"])
    # dedupe aggregated lists
    for key in ["eligibility_criteria", "test_pattern", "scholarships", "offered_courses", "hostel_info"]:
        combined["aggregated"][key] = list(dict.fromkeys(combined["aggregated"][key]))
    return combined
