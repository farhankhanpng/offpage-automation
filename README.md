# IA Spaces Off-Page SEO Automation System 🚀

A Python-based Off-Page SEO & Opportunity Automation System built for **IA Spaces** (`https://iaspaces.co`), the coworking and managed office arm of **India Accelerator**.

This system runs on **Windows 11 (PowerShell)**, requires **zero paid APIs or services**, and automatically synchronizes with **Google Sheets** (with an automatic offline local CSV/JSON cache fallback).

---

## 📋 System Features

- **Module 1: Opportunity Discovery**  
  Monitors Google Alerts RSS feeds, public business feeds (Inc42, YourStory, Entrackr, LiveMint), GDELT 2.0 public document search, and manual verification search query generators.
- **Module 2: Brand Mention Monitor**  
  Tracks brand mentions (`IA Spaces`, `India Accelerator`, `India Accelerator Coworking`, `MySOHO`). Inspects live HTML to verify whether a hyperlink to `iaspaces.co` exists before labeling mentions as linked or unlinked.
- **Module 3: Backlink Health Monitor**  
  Checks verified backlink source pages, verifying target URL, HTTP status, anchor text, and `rel` attributes (`dofollow`, `nofollow`, `sponsored`, `ugc`).
- **Module 4: Competitor Opportunity Tracker**  
  Detects editorial coverage of competitors (*Awfis, Smartworks, Innov8, IndiQube, WeWork India*) and flags editorial angles (listicles, funding commentary, Tier-2 expansion narratives).
- **Module 5: Local Citation & Directory Tracker**  
  Audits directory listings (Justdial, IndiaMART, Sulekha, Coworker) against canonical master NAP data for 15+ hubs. Enforces strict 1-to-1 hub address/phone pairing.
- **Module 6: Transparent Opportunity Scoring (0–100)**  
  Calculates objective scores using 6 clear pillars: Coworking/CRE relevance (25 pts), India relevance (20 pts), Editorial authenticity (20 pts), Existing coverage (15 pts), Viability (10 pts), and Contact verification (10 pts). **Never fabricates DA/DR or traffic metrics.**
- **Module 7: Google Sheets Integration & Offline Resilience**  
  Syncs with Google Sheets via `gspread` across 8 dedicated tabs (`Dashboard`, `Opportunities`, `Backlinks`, `Brand_Mentions`, `Competitors`, `Outreach`, `Citations`, `Activity_Log`). If credentials are not present, seamlessly stores data in `data/sheets_offline_cache/*.csv`.
- **Module 8: Personalized Outreach Generator**  
  Drafts custom outreach templates for high-scoring prospects with default status **`Pending Approval`**. **Never dispatches emails automatically.**
- **Module 9: Executive Markdown Reporting**  
  Generates daily discovery and weekly audit reports formatted in Markdown under `reports/`.
- **Module 10: Security & Reliability**  
  Polite rate limiter (2.0s delay), `robots.txt` compliance, SSRF sanitization, credentials protected in `.gitignore`, and comprehensive unit tests.

---

## 🛠️ Prerequisites & Setup (Windows 11)

### 1. Requirements
- Python 3.12 (already installed on your machine)
- Windows PowerShell

### 2. Verify Your Python Environment
Open PowerShell and navigate to the project directory:
```powershell
cd C:\Users\kfarh\Downloads\claude-seo-main\claude-seo-main\offpage-automation
python --version
```

*(Optional)* Install external convenience packages:
```powershell
pip install -r requirements.txt
```
> **Note:** The entire system is architected with Python standard library fallbacks (`xml.etree.ElementTree`, `html.parser`, `urllib.request`). It runs and passes all tests even before installing external packages!

---

## ⚡ Quick Start: Running the System

### Run the Daily Pipeline (Discovery, Mentions, Backlinks, Outreach)
```powershell
python run_daily.py --dry-run
```
For live online web fetching:
```powershell
python run_daily.py
```

### Run the Weekly Pipeline (Citations Audit & Competitor Gaps)
```powershell
python run_weekly.py --dry-run
```
For live weekly audit:
```powershell
python run_weekly.py
```

### Run All Unit Tests
```powershell
python -m unittest discover -s tests
```

---

## 📊 Connecting to Google Sheets (Optional)

The system works out-of-the-box without credentials by saving all data to `data/sheets_offline_cache/`.

When you are ready to sync directly to live Google Sheets:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a free project and enable the **Google Sheets API** and **Google Drive API**.
3. Create a **Service Account** and download the credentials JSON key.
4. Rename the JSON key to `google-service-account.json` and save it to:
   ```
   offpage-automation/secrets/google-service-account.json
   ```
5. Create a new Google Spreadsheet named:
   `IA Spaces - Off-Page SEO Master`
6. Share the spreadsheet with the `client_email` listed inside your `google-service-account.json` giving it **Editor** permissions.
7. Next time you run `python run_daily.py`, it will automatically create and populate the 8 tabs!

---

## 📁 Folder Structure

```
offpage-automation/
├── config/
│   ├── settings.yaml          # Crawler user-agent, delay, RSS feeds, GDELT queries
│   ├── competitors.yaml       # Monitored competitors and domains
│   └── keywords.yaml          # Brand variations and CRE keywords
├── src/
│   ├── discovery/             # RSS parser, GDELT client, search query generator
│   ├── mentions/              # Brand mention detection & live hyperlink inspector
│   ├── backlinks/             # Source URL auditor, rel attributes & status checker
│   ├── competitors/           # Competitor coverage gap analyzer
│   ├── citations/             # Directory listing audit against 15 master hubs
│   ├── scoring/               # Transparent 0-100 opportunity scoring engine
│   ├── sheets/                # Google Sheets sync & offline local CSV cache
│   ├── reporting/             # Outreach generator & Markdown report creator
│   └── utils/                 # URL normalization, polite rate limiter, HTML parser
├── data/
│   ├── citations_seed.csv     # Seed directory listings
│   ├── backlinks_seed.csv     # Seed backlink sources
│   └── sheets_offline_cache/  # Persistent CSV copies of all 8 tabs
├── reports/                   # Daily & weekly Markdown reports
├── secrets/                   # (Ignored by git) Service account credentials
├── tests/                     # Automated unit test suite
├── run_daily.py               # Daily pipeline entrypoint
├── run_weekly.py              # Weekly pipeline entrypoint
└── requirements.txt           # Dependencies
```

---

## 🛡️ Ethical Guardrails & Compliance

- **No SERP Scraping:** Does not scrape Google search result pages. Uses Google Alerts RSS feeds, public news XML, and pre-formatted manual verification queries.
- **No Spam or Auto-Outreach:** Generates outreach drafts marked `Pending Approval`. Never sends emails or submits web forms automatically.
- **No Fabricated Metrics:** Uses documented, transparent factors instead of unverified DA/DR metrics.
- **Polite Crawling:** Enforces a 2.0-second delay per domain and checks `robots.txt`.
