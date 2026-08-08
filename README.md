# Kerala District Emergency Numbers Scraper — for mazha.live

Scrapes district-wise emergency / disaster-management contact numbers from
**official Kerala government sources only**:

- Each district's official `<district>.nic.in` portal (Disaster Management /
  Helpline page)
- KSDMA's consolidated state PDF directory (used as a cross-check + fallback)

## Why this isn't a "realtime" fetch

These numbers change rarely — a control room might get a new landline once a
year, if that. Hitting the government's site on every single mazha.live page
load would be slow, fragile (nic.in sites go down often), and unnecessary.
The right pattern is:

```
cron/scheduled job → scraper.py → district_emergency_numbers.json
                                        │
                                        ▼
                          commit to repo / upload to your DB
                                        │
                                        ▼
                       mazha.live serves it from your own backend
                          (instant, no dependency on gov uptime)
```

Run it **weekly year-round, daily during monsoon season (Jun–Nov)** when
control rooms are most likely to get updated/relocated.

## Setup

```bash
pip install -r requirements.txt
python scraper.py
```

Output: `district_emergency_numbers.json`

Options:

```bash
python scraper.py --district Idukki       # one district only, for testing
python scraper.py --pdf-only              # skip nic.in, just parse the KSDMA PDF
python scraper.py --no-verify-ssl         # some .nic.in certs are misconfigured
python scraper.py --output data/numbers.json
```

## ⚠️ Important: verify before you ship

Government HTML is inconsistent district to district, and this scraper's
extraction is regex/heuristic-based. **Do not pipe the output straight to
production.** Each district's result includes a `status` field:

- `"ok"` — numbers were found and categorized; still worth a quick glance
- `"not_found"` — none of the candidate URLs in `sources.py` worked for that
  district. Open the district's site by hand, find the real page, and add
  its path to `CANDIDATE_PATHS` (or a district-specific override) in
  `sources.py`.

The script prints a "needs manual review" summary at the end of every run.

Every extracted number also carries its `source_url`, so you (or a
contributor) can spot-check against the live page in one click.

## Output shape

```json
{
  "generated_at": "2026-08-08T12:00:00+0000",
  "state_level_numbers": {
    "kerala_emergency_112": "112",
    "kseoc_state_disaster_control_room": "1070 / 1079 / 0471-2778800",
    "...": "..."
  },
  "districts": {
    "Idukki": {
      "district": "Idukki",
      "source_url": "https://idukki.nic.in/en/helpline/",
      "status": "ok",
      "numbers": [
        {
          "category": "ambulance",
          "label": "Ambulance",
          "number": "108",
          "source_url": "https://idukki.nic.in/en/helpline/"
        },
        {
          "category": "control_room",
          "label": "District Disaster Management Control Room (Collectorate)",
          "number": "1077",
          "source_url": "https://idukki.nic.in/en/helpline/"
        }
      ]
    }
  },
  "ksdma_pdf_crosscheck": {
    "Idukki": ["1077", "1070", "9383463036", "04862233111", "04862233130"]
  }
}
```

`category` values: `control_room`, `deoc`, `police`, `fire`, `ambulance`,
`kseb`, `kwa`, `women_helpline`, `child_helpline`, `collector`,
`disaster_management_cell`, or `other` (uncategorized — check manually).

## Extending

- `sources.py` — add/fix district URLs, add new keyword categories.
- `scraper.py::extract_numbers_from_html` — tweak parsing if a district's
  page uses a layout the two current strategies (tables, then `<li>`/`<p>`)
  don't handle. Print the raw HTML for that page and adjust from there.

## Network note

This scraper needs outbound access to `*.nic.in` and `sdma.kerala.gov.in`.
If you're running it inside a sandboxed CI environment, make sure those
domains are allow-listed on egress, or run it from an unrestricted server /
your own machine.
