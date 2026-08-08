#!/usr/bin/env python3
"""
scraper.py — Kerala District Emergency Numbers Scraper (for mazha.live)

Fetches emergency / disaster-management contact numbers for each of Kerala's
14 districts from official government sources:

  1. Each district's official NIC.in portal (tries several known page slugs).
  2. KSDMA's consolidated state PDF directory, as a cross-check / fallback.

Output: district_emergency_numbers.json — one entry per district, each number
tagged with a category (control_room, police, fire, ambulance, etc.), the raw
label text found next to it, and the source URL it was scraped from — so you
can audit anything before publishing it on mazha.live.

USAGE:
    pip install -r requirements.txt
    python scraper.py                  # scrape all districts
    python scraper.py --district Idukki  # scrape a single district
    python scraper.py --pdf-only       # only parse the KSDMA PDF fallback
    python scraper.py --no-verify-ssl  # some .nic.in sites have cert issues

NOTES:
  - Government sites change layout / URLs without notice. This script is
    written defensively (multiple candidate URLs, regex-based extraction)
    but you should spot-check results before they go live, especially the
    first time you run it or after a long gap.
  - Be a good citizen: this script uses polite delays and a real User-Agent,
    and caches PDF downloads locally to avoid hammering KSDMA's server.
  - Run this on a schedule (e.g. weekly, and daily during monsoon season,
    June-Nov) rather than fetching live on every mazha.live page load.
"""

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from sources import (
    DISTRICTS,
    CANDIDATE_PATHS,
    LABEL_KEYWORDS,
    STATE_LEVEL_NUMBERS,
    KSDMA_DIRECTORY_PDF,
)

USER_AGENT = (
    "Mozilla/5.0 (compatible; mazha-live-emergency-bot/1.0; "
    "+https://www.mazha.live; contact: your-email@example.com)"
)
REQUEST_TIMEOUT = 15
POLITE_DELAY_SECONDS = 1.5
CACHE_DIR = Path("./cache")

# Matches Indian phone numbers: toll-free (1077, 1070), landlines with STD
# code (0481-2568007 or 0481 2568007), and 10-digit mobiles, optionally
# comma/slash separated lists of the above.
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+91[-\s]?)?"
    r"(?:\d{2,4}[-\s]\d{6,8}"          # STD-code landline: 0481-2568007
    r"|\d{10}"                          # 10-digit mobile
    r"|1[89]00[-\s]?\d{3}[-\s]?\d{4}"   # 1800-xxx-xxxx toll free
    r"|1\d{3}"                          # 4-digit short codes: 1077, 1070, 1098
    r"|(?:100|101|102|108|109|112)"     # 3-digit national emergency codes
    r")(?!\d)"
)


@dataclass
class ContactNumber:
    category: str
    label: str
    number: str
    source_url: str


@dataclass
class DistrictResult:
    district: str
    source_url: Optional[str] = None
    numbers: list = field(default_factory=list)
    status: str = "pending"   # ok | not_found | error
    error: Optional[str] = None


def polite_get(session: requests.Session, url: str, verify_ssl: bool = True):
    try:
        resp = session.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            verify=verify_ssl,
        )
        time.sleep(POLITE_DELAY_SECONDS)
        if resp.status_code == 200:
            return resp
        return None
    except requests.RequestException:
        return None


def classify_label(label: str) -> str:
    label_lower = label.lower()
    for category, keywords in LABEL_KEYWORDS.items():
        for kw in keywords:
            if kw in label_lower:
                return category
    return "other"


def extract_numbers_from_html(html: str, source_url: str) -> list:
    """
    Walk table rows and list items, pairing a label (preceding text cell /
    text) with any phone numbers found in the same row/item.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Strategy 1: table rows — common on nic.in "helpline"/"disaster
    # management" pages, e.g. <tr><td>District Control Room</td><td>1077</td></tr>
    for row in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if not cells:
            continue
        row_text = " | ".join(cells)
        phones = PHONE_RE.findall(row_text)
        if not phones:
            continue
        # Label = the longest non-numeric-looking cell in the row
        label_candidates = [c for c in cells if not PHONE_RE.fullmatch(c.strip())]
        label = max(label_candidates, key=len) if label_candidates else "Unlabeled"
        for phone in phones:
            results.append(
                ContactNumber(
                    category=classify_label(label),
                    label=label,
                    number=phone.strip(),
                    source_url=source_url,
                )
            )

    # Strategy 2: list items / paragraphs, e.g. <li>Ambulance: 108</li>
    # Always run (not just when Strategy 1 is empty) — many nic.in pages mix
    # a table for some fields with plain <p>/<li> text for others.
    if True:
        for tag in soup.find_all(["li", "p"]):
            text = tag.get_text(" ", strip=True)
            phones = PHONE_RE.findall(text)
            if not phones:
                continue
            label = re.split(r":|-\s*\d", text)[0].strip()
            for phone in phones:
                results.append(
                    ContactNumber(
                        category=classify_label(label),
                        label=label or "Unlabeled",
                        number=phone.strip(),
                        source_url=source_url,
                    )
                )

    # De-duplicate identical (category, number) pairs
    seen = set()
    deduped = []
    for r in results:
        key = (r.category, r.number)
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


def scrape_district(session: requests.Session, district: str, domain: str, verify_ssl: bool) -> DistrictResult:
    result = DistrictResult(district=district)
    for path in CANDIDATE_PATHS:
        url = f"https://{domain}/{path}"
        resp = polite_get(session, url, verify_ssl=verify_ssl)
        if resp is None:
            continue
        numbers = extract_numbers_from_html(resp.text, url)
        if numbers:
            result.source_url = url
            result.numbers = [asdict(n) for n in numbers]
            result.status = "ok"
            return result
    result.status = "not_found"
    result.error = "No candidate page yielded phone numbers. Check DISTRICTS/CANDIDATE_PATHS in sources.py manually."
    return result


def parse_ksdma_pdf(pdf_path: Path) -> dict:
    """
    Cross-check / fallback source: KSDMA's consolidated PDF directory.
    Requires: pip install pdfplumber
    """
    try:
        import pdfplumber
    except ImportError:
        print("pdfplumber not installed — skipping PDF parse. Run: pip install pdfplumber --break-system-packages", file=sys.stderr)
        return {}

    district_names = list(DISTRICTS.keys())
    text_by_page = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text_by_page.append(page.extract_text() or "")
    except Exception as e:
        print(f"WARNING: could not parse KSDMA PDF ({e}) — skipping PDF cross-check.", file=sys.stderr)
        return {}

    full_text = "\n".join(text_by_page)

    # Very rough split: chunk the PDF text between one district name (in caps)
    # and the next, then regex out phone numbers from each chunk.
    results = {}
    upper_names = [d.upper() for d in district_names]
    positions = []
    for name in upper_names:
        for m in re.finditer(re.escape(name), full_text):
            positions.append((m.start(), name))
    positions.sort()

    for i, (start, name) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(full_text)
        chunk = full_text[start:end]
        phones = sorted(set(PHONE_RE.findall(chunk)))
        district_key = district_names[upper_names.index(name)]
        results.setdefault(district_key, set()).update(phones)

    return {k: sorted(v) for k, v in results.items()}


def download_pdf(session: requests.Session, url: str, dest: Path, verify_ssl: bool) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return True
    resp = polite_get(session, url, verify_ssl=verify_ssl)
    if resp is None:
        return False
    dest.write_bytes(resp.content)
    return True


def main():
    parser = argparse.ArgumentParser(description="Scrape Kerala district emergency numbers from official sources.")
    parser.add_argument("--district", help="Scrape only this district (e.g. Idukki)")
    parser.add_argument("--pdf-only", action="store_true", help="Only parse the KSDMA state PDF, skip nic.in scraping")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL verification (some .nic.in certs are misconfigured)")
    parser.add_argument("--output", default="district_emergency_numbers.json", help="Output JSON path")
    args = parser.parse_args()

    verify_ssl = not args.no_verify_ssl
    session = requests.Session()

    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "state_level_numbers": STATE_LEVEL_NUMBERS,
        "districts": {},
        "ksdma_pdf_crosscheck": {},
    }

    # --- PDF cross-check (always attempted, cheap and useful even alone) ---
    CACHE_DIR.mkdir(exist_ok=True)
    pdf_path = CACHE_DIR / "ksdma-dm-directory.pdf"
    if download_pdf(session, KSDMA_DIRECTORY_PDF, pdf_path, verify_ssl):
        output["ksdma_pdf_crosscheck"] = parse_ksdma_pdf(pdf_path)
    else:
        print(f"WARNING: could not download KSDMA PDF from {KSDMA_DIRECTORY_PDF}", file=sys.stderr)

    if args.pdf_only:
        Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False))
        print(f"Wrote {args.output} (PDF cross-check only)")
        return

    # --- Per-district nic.in scraping ---
    targets = {args.district: DISTRICTS[args.district]} if args.district else DISTRICTS
    for district, domain in targets.items():
        print(f"Scraping {district} ({domain})...", file=sys.stderr)
        result = scrape_district(session, district, domain, verify_ssl)
        output["districts"][district] = asdict(result)
        status_note = "OK" if result.status == "ok" else f"NEEDS REVIEW ({result.status})"
        print(f"  -> {status_note}", file=sys.stderr)

    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False))
    ok_count = sum(1 for d in output["districts"].values() if d["status"] == "ok")
    print(f"\nDone. {ok_count}/{len(targets)} districts scraped successfully.")
    print(f"Output written to {args.output}")
    needs_review = [d for d, v in output["districts"].items() if v["status"] != "ok"]
    if needs_review:
        print(f"Needs manual review (add correct URL to sources.py CANDIDATE_PATHS or DISTRICTS): {', '.join(needs_review)}")


if __name__ == "__main__":
    main()
