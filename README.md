# Northern Data Studio Lead Scraper

Python scraper for finding public company leads for Northern Data Studio.

It searches public pages, visits company websites, looks for contact/about pages, extracts emails and phone numbers, detects likely industry from keywords, and saves the final leads to `leads.csv`.

## Target Leads

Default target:

- Logistics
- Construction
- Marketing agencies
- Property management companies
- E-commerce companies

Location priority:

- Ottawa first
- Canada
- USA

## Output Columns

The CSV includes:

- `company_name`
- `industry`
- `city`
- `country`
- `website`
- `email`
- `phone`
- `source_url`
- `notes`

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

This saves results to:

```bash
leads.csv
```

The project includes a starter `seeds.txt` file. When `seeds.txt` exists, `python main.py` uses those company websites directly instead of spending time on blocked search-result pages.

You should see progress messages like:

```bash
Discovery page found 8 candidate URLs: ...
Scraping company site: https://example.com
Saved lead 1: Example Company
```

If it says `Saved 0 leads`, the search or directory pages were probably blocked or disallowed. Use manual seed URLs for better results:

```bash
python main.py --seed-url https://example-company.com
```

Directory pages are not included by default because many of them block automated requests. To try them anyway:

```bash
python main.py --include-directories
```

## Useful Options

Run with a different target count:

```bash
python main.py --target-count 50
```

Use a custom output file:

```bash
python main.py --output ottawa_leads.csv
```

Add a manual seed URL:

```bash
python main.py --seed-url https://example-company.com
```

Use a seed file:

```bash
python main.py --seed-file seeds.txt
```

Use only your provided seed URLs and skip default search URLs:

```bash
python main.py --no-default-search --seed-file seeds.txt
```

Force default search pages in addition to `seeds.txt`:

```bash
python main.py --include-default-search
```

Pass a public search-result URL manually:

```bash
python main.py --search-url "https://www.bing.com/search?q=Ottawa+construction+company+contact"
```

## Notes On Responsible Use

This scraper is designed for public webpages only.

It:

- checks `robots.txt` where possible
- adds a delay between requests
- skips LinkedIn, Facebook, Instagram, X/Twitter, TikTok, YouTube, login pages, checkout pages, and admin pages
- does not use private APIs
- does not bypass authentication

Search engines and company sites can change their HTML or block automated traffic. For best results, combine default search discovery with a curated `seeds.txt` file containing company or directory URLs.
