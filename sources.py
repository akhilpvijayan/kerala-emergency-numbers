"""
sources.py
Authoritative source configuration for Kerala district emergency numbers.

Every district in Kerala has an official NIC.in portal (https://<district>.nic.in)
which usually publishes a "Disaster Management" or "Helpline" page. The exact
slug varies district to district, so for each district we list several
candidate paths and the scraper tries them in order, keeping the first one
that actually contains phone numbers.

We also keep the KSDMA state-level PDF directory as a secondary/cross-check
source, since it lists district + taluk level numbers in one document (updated
less frequently, but useful as a fallback / sanity check).
"""

STATE_LEVEL_NUMBERS = {
    "kerala_emergency_112": "112",
    "kseoc_state_disaster_control_room": "1070 / 1079 / 0471-2778800",
    "police": "100",
    "fire": "101",
    "ambulance": "108",
    "women_helpline": "1091 / 181",
    "child_helpline": "1098",
    "highway_accident_helpline": "1033",
    "kseb_helpline": "1912",
    "kerala_water_authority_helpline": "1916",
}

KSDMA_DIRECTORY_PDF = "https://sdma.kerala.gov.in/wp-content/uploads/2023/05/DM-DIRECTORY.pdf"
KSDMA_CONTACT_PAGE = "https://sdma.kerala.gov.in/contact/"

# Candidate relative paths to try on each district's nic.in domain, in priority order.
CANDIDATE_PATHS = [
    "en/disaster-management/",
    "en/helpline/",
    "en/department/state-emergency-contact-numbers/",
    "en/district-emergency-operations-centre/",
    "en/contact-us/",
]

# district_key -> nic.in base domain
DISTRICTS = {
    "Thiruvananthapuram": "thiruvananthapuram.nic.in",
    "Kollam": "kollam.nic.in",
    "Pathanamthitta": "pathanamthitta.nic.in",
    "Alappuzha": "alappuzha.nic.in",
    "Kottayam": "kottayam.nic.in",
    "Idukki": "idukki.nic.in",
    "Ernakulam": "ernakulam.nic.in",
    "Thrissur": "thrissur.nic.in",
    "Palakkad": "palakkad.nic.in",
    "Malappuram": "malappuram.nic.in",
    "Kozhikode": "kozhikode.nic.in",
    "Wayanad": "wayanad.nic.in",
    "Kannur": "kannur.nic.in",
    "Kasaragod": "kasaragod.nic.in",
}

# Keywords used to classify a phone number by what it's for, based on the
# label text found near it in the page (case-insensitive substring match).
LABEL_KEYWORDS = {
    "control_room": ["control room", "district control room", "collectorate control room"],
    "deoc": ["district emergency operation", "deoc", "emergency operations centre"],
    "police": ["police helpline", "police control", "police station"],
    "fire": ["fire service", "fire station", "fire force"],
    "ambulance": ["ambulance"],
    "kseb": ["kseb", "electricity"],
    "kwa": ["water authority", "kwa"],
    "women_helpline": ["women helpline", "women's helpline"],
    "child_helpline": ["child helpline", "childline"],
    "collector": ["collector"],
    "disaster_management_cell": ["disaster management cell", "dm section", "disaster management section"],
}
