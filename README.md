# IA Spaces Off-Page SEO Automation

Python automation for **IA Spaces** (`https://iaspaces.co`), the coworking network of **India Accelerator**.
It finds coverage and outreach opportunities, checks brand mentions, backlinks, competitor coverage and
directory listings, drafts outreach emails for human approval, and syncs everything to Google Sheets.
No paid APIs. Runs on Windows (PowerShell) and in GitHub Actions.

> **Nothing is ever sent.** Outreach drafts are created with status `Pending Approval`.
> Sending is a separate, manual step (`scripts/send_outreach_smtp.py` in the main project).

---

## What runs

### Daily (`run_daily.py`, 09:00 IST)
1. **Discovery**: public RSS feeds (Inc42, YourStory, Entrackr, Mint) and GDELT, plus the pages in
   `data/competitors_seed.csv`. Feed items are only kept if the headline/summary mentions a tracked brand,
   a competitor or a coworking/CRE term.
2. **Each candidate page is fetched once** by a shared polite fetcher (robots.txt respected, 3 s per site,
   retries on 429/503).
3. **Brand mentions** (whole-word match) and **competitor coverage** are read from the fetched page.
4. **Scoring** (0-100, documented below). Pages that couldn't be fetched are marked *Unverified* and can't
   get an outreach draft.
5. **Outreach drafts** for strong, fetched pages, plus link-request drafts for every known article that
   mentions the brand without linking to iaspaces.co (`data/mentions_seed.csv`). Contact emails are only
   filled in when they are published on the page.
6. **Backlink checks** for `data/backlinks_seed.csv`. Links that still point at the legacy
   `indiaaccelerator.co/ia-spaces/` page are flagged.
7. **Sync** to Google Sheets and the local cache, then a Markdown report in `reports/`.

### Weekly (`run_weekly.py`, Mondays 09:30 IST)
1. **Directory listings**: each URL in `data/citations_seed.csv` is fetched and checked against the master
   NAP (`data/ia-spaces-nap-master.csv`) for the phone number, PIN code and a link to iaspaces.co.
   Listings that block bots are marked *Could Not Verify* (check them by hand); placeholder URLs are
   marked *Placeholder URL*.
2. **Competitor coverage** on the pages in `data/competitors_seed.csv` (fetched pages only).
3. **Backlink checks**, sync, and `reports/weekly-report-YYYY-MM-DD.md`.

### Run health
Every report starts with a **Run Health** section, and the Dashboard tab shows `Healthy`, `Degraded` or
`Failing` with the number of successful checks. Exit codes: `0` ok/degraded, `1` a required integration
failed (Sheets in GitHub Actions), `2` no check succeeded. A failed scheduled run makes GitHub email the
repository owner.

---

## Google Sheets

Tabs: `Dashboard`, `Opportunities`, `Backlinks`, `Brand_Mentions`, `Competitors`, `Outreach`,
`Citations`, `Activity_Log` (created automatically).

- **Your edits are kept.** `Approval Status` (Outreach tab) and `Team Notes` (every data tab) belong to
  your team: the pipeline never overwrites a value you set there.
- **Rows are merged, not wiped.** Each run combines the Sheet, the local cache and new results by ID, so
  local runs and GitHub runs don't erase each other.
- **Removing rows:** add the ID to `data/purged_ids.txt`. It disappears from the Sheet and cache on the next
  run and is never re-added.
- **Retention:** rows not seen for `retention_days` (90) are removed unless someone annotated them.
- Rows written before v1.1.0 (no `Last Seen` value) are removed automatically on the first v1.1.0 run,
  unless they were annotated. This clears the test data and duplicates found in the 2026-11-17 audit.

### Setup
1. In Google Cloud, enable the **Google Sheets API** (and the **Google Drive API** only if you open the
   Sheet by name), and create a service account with a JSON key.
2. Save the key as `secrets/google-service-account.json` (git-ignored).
3. Create a spreadsheet named `IA Spaces - Off-Page SEO Master` and share it with the service account's
   `client_email` as **Editor**.
4. Recommended: copy the Sheet ID from its URL (`docs.google.com/spreadsheets/d/<ID>/edit`) into
   `GOOGLE_SHEET_ID` in `.env` (and as a GitHub Actions *variable*, see below).

### GitHub Actions
- Secret `GOOGLE_SERVICE_ACCOUNT_JSON`: the full JSON key contents.
- Variable `GOOGLE_SHEET_ID` (Settings → Secrets and variables → Actions → Variables): the Sheet ID.
- Both workflows run the tests first, share one queue (they never push at the same time), fail if Sheets
  can't be reached, and commit `reports/` and the cache back to `main`.
- **Run it in one place.** If you also run locally, `git pull` before you start and push right after.
  The Sheet is the shared copy either way.

---

## Running locally (Windows PowerShell)

```powershell
cd C:\Users\kfarh\Downloads\claude-seo-main\claude-seo-main\offpage-automation
pip install -r requirements.txt
copy .env.example .env        # optional: adjust settings
python run_daily.py --dry-run # fixtures only: no network, nothing written to the Sheet
python run_daily.py           # live
python run_weekly.py          # live
python -m pytest -q           # tests
```

Dry runs use built-in fixture pages and write only to `data/dry_run_cache/` and `reports/dry-run/`
(both git-ignored). They never touch the Sheet or the real cache.

---

## Scoring (0-100)

| Pillar | Points | Signal (whole-word matches on the page's title and text) |
|---|---|---|
| Coworking / CRE relevance | 0-30 | coworking, managed office, flexible workspace, office space, ... |
| India relevance | 0-15 | India and city names; Indian publication domains get a small boost |
| Editorial content | 0-15 | the page was fetched and looks editorial (news, feature, guide, ...) |
| Coverage gap | 0-20 | competitor named/linked on the page, or a list-style headline |
| Contribution route | 0-10 | contributor / guest post / submit wording |
| Contact on page | 0-10 | an email address on the publication's own domain |

Gates: no coworking/CRE term → capped at 25 (*Not Relevant*); page not fetched → capped at 49
(*Unverified*); spam signals → 0 (*Rejected*). Drafts need *High/Medium* and at least
`outreach.min_score` (65). No third-party authority metrics are estimated.

---

## Configuration

| File | What it holds |
|---|---|
| `config/settings.yaml` | crawler, Sheets, outreach threshold, feeds/GDELT queries, `brand_facts` used in drafts |
| `config/keywords.yaml` | brand terms (whole-word) and target publications |
| `config/competitors.yaml` | competitors tracked (name + domain) |
| `.env` | optional overrides (see `.env.example`) |
| `data/*_seed.csv` | pages to monitor; URLs checked on 2026-11-17/18. Citation rows with no URL mean no listing was found: create one |
| `data/ia-spaces-nap-master.csv` | NAP for the 32 hubs on iaspaces.co (rebuilt 2026-11-18; column "Team Confirmed" shows whether operations has checked each row) |
| `data/purged_ids.txt` | IDs to remove permanently |

`brand_facts` (hub and city counts in drafts) must match iaspaces.co. Update the `checked` note whenever
you change them.

---

## Ethics and compliance
- No scraping of Google results; manual search queries are in `src/discovery/manual_queries.py`.
- Honest bot user agent with contact details; robots.txt followed (4xx robots files mean "allowed" and
  5xx means "wait", as Google does).
- No automatic sending or form submission. No invented metrics or statistics in drafts.

---

## Changelog

### 1.1.3 (2026-11-23)
- No drafts for daily news roundups and trackers (YourStory's roundup was creating a new draft every day). Two roundup drafts retired.

### 1.1.2 (2026-11-19)
- Link requests are only drafted for mentions about coworking. India Accelerator mentions in funding or startup news are still recorded, marked "not about coworking, no link request".
- Link-request drafts name IA Spaces in the subject, and India Accelerator ahead of the old MySOHO name.
- Two drafts that should not be sent (YourStory roundups) are retired.

### 1.1.1 (2026-11-18)
- Hub list rebuilt from the 32 hub pages on iaspaces.co (the old 15-hub file was wrong for 10 hubs).
- Citations: real listing URLs from myHQ, CoworkingCafe and Houssed; "No Listing Found" status for directories without a listing; listings still named "India Accelerator" are flagged.
- Mention snippets come from the article text, not the site menu.
- Hub & Oak (a competitor operator) removed from the competitor seed list.

### 1.1.0 (2026-11-17), fixes from the project audit
- Dry runs no longer write to the Sheet or the real cache.
- The weekly run no longer invents competitor rows when a page fails to load.
- Citation checks now fetch each listing and compare it with the master NAP.
- Stable IDs everywhere (no more duplicates from Python's `hash()`).
- Sheets sync keeps team edits, merges rows from both runners, grows the grid, batches the activity log,
  and uses narrower scopes.
- Brand Mentions "Mentioned URL"/"Page Title" and Opportunities "Discovery Date" are now filled.
- Scoring uses whole-word matches; no more hard-coded contact/editorial points.
- Drafts only for fetched pages, with contacts taken from the page; the unsourced "40% YoY" claim was removed.
- One shared fetcher: per-site delay across modules, robots.txt fetched with our user agent and a timeout,
  retries on 429/503, `.env` honoured.
- Run Health in reports and the Dashboard, non-zero exit codes, IST timestamps everywhere.
- Workflows: tests first, shared concurrency queue, rebase-and-retry push, pinned actions, Dependabot.
- Seed files replaced with pages confirmed to exist; placeholder directory URLs are labelled.
- HTML text extraction no longer runs words together across tags.
