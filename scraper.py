import time
from collections import deque
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from utils import (
    CONTACT_LINK_KEYWORDS,
    detect_city_country,
    detect_industry,
    dedupe_leads,
    domain_from_url,
    extract_company_name,
    extract_emails,
    extract_phone_numbers,
    is_blocked_url,
    is_directory_url,
    is_likely_company_url,
    is_private_or_login_url,
    normalize_url,
    same_domain,
    unwrap_search_url,
)


class LeadScraper:
    def __init__(
        self,
        target_count: int = 50,
        delay: float = 2.0,
        timeout: float = 15.0,
        max_pages_per_site: int = 4,
        verbose: bool = True,
    ) -> None:
        self.target_count = target_count
        self.delay = delay
        self.timeout = timeout
        self.max_pages_per_site = max_pages_per_site
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "NorthernDataStudioLeadResearch/1.0 "
                    "(public webpages only; contact: info@northerndatastudio.com)"
                )
            }
        )
        self.robot_cache: dict[str, RobotFileParser | None] = {}
        self.page_cache: dict[str, str] = {}
        self.visited_urls: set[str] = set()
        self.visited_domains: set[str] = set()

    def run(self, search_urls: list[str], seed_urls: list[str]) -> list[dict[str, str]]:
        candidate_urls = deque()

        for search_url in search_urls:
            discovered = self.discover_from_search_page(search_url)
            self.log(f"Discovery page found {len(discovered)} candidate URLs: {search_url}")
            candidate_urls.extend(discovered)

        for seed_url in seed_urls:
            normalized = normalize_url(seed_url)
            if normalized:
                candidate_urls.append(normalized)

        leads = []
        while candidate_urls and len(leads) < self.target_count:
            candidate = candidate_urls.popleft()
            website = normalize_url(candidate, root_only=True)

            if not website or domain_from_url(website) in self.visited_domains:
                continue
            if is_directory_url(candidate):
                discovered = self.discover_from_search_page(candidate)
                self.log(f"Directory page found {len(discovered)} candidate URLs: {candidate}")
                candidate_urls.extend(discovered)
                continue
            if not is_likely_company_url(website) or is_blocked_url(website):
                continue

            self.visited_domains.add(domain_from_url(website))
            self.log(f"Scraping company site: {website}")
            lead = self.scrape_company_site(website)

            if lead:
                leads.append(lead)
                leads = dedupe_leads(leads)
                self.log(f"Saved lead {len(leads)}: {lead['company_name']}")

        return leads[: self.target_count]

    def discover_from_search_page(self, search_url: str) -> list[str]:
        if is_blocked_url(search_url) or is_private_or_login_url(search_url):
            return []

        html = self.fetch(search_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        discovered = []

        for anchor in soup.find_all("a", href=True):
            href = unwrap_search_url(anchor.get("href", ""))
            raw_url = normalize_url(urljoin(search_url, href))
            url = raw_url if is_directory_url(raw_url) else normalize_url(raw_url, root_only=True)

            if not url:
                continue
            if is_blocked_url(url) or is_private_or_login_url(url):
                continue
            if is_likely_company_url(url) or is_directory_url(url):
                discovered.append(url)

        return list(dict.fromkeys(discovered))

    def scrape_company_site(self, website: str) -> dict[str, str] | None:
        pages = self.find_contact_pages(website)
        if website not in pages:
            pages.insert(0, website)

        collected_text = []
        emails = []
        phones = []
        company_name = ""
        source_url = website
        pages_checked = 0

        for page_url in pages[: self.max_pages_per_site]:
            html = self.fetch(page_url)
            if not html:
                continue

            pages_checked += 1
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(" ", strip=True)
            collected_text.append(text)

            if not company_name:
                company_name = extract_company_name(soup, website)

            page_emails = extract_emails(html + " " + text)
            page_phones = extract_phone_numbers(html + " " + text)

            if page_emails and not emails:
                source_url = page_url
            emails.extend(page_emails)
            phones.extend(page_phones)

        if not pages_checked:
            return None

        combined_text = " ".join(collected_text)
        city, country = detect_city_country(combined_text)
        industry = detect_industry(combined_text + " " + company_name + " " + website)

        emails = list(dict.fromkeys(emails))
        phones = list(dict.fromkeys(phones))
        notes = []

        if not emails:
            notes.append("email_not_found")
        if not phones:
            notes.append("phone_not_found")
        if industry == "Unknown":
            notes.append("industry_uncertain")

        return {
            "company_name": company_name or domain_from_url(website),
            "industry": industry,
            "city": city,
            "country": country,
            "website": website,
            "email": emails[0] if emails else "",
            "phone": phones[0] if phones else "",
            "source_url": source_url,
            "notes": "; ".join(notes),
        }

    def find_contact_pages(self, website: str) -> list[str]:
        html = self.fetch(website)
        if not html:
            return [website]

        soup = BeautifulSoup(html, "html.parser")
        links = []

        for anchor in soup.find_all("a", href=True):
            label = " ".join(anchor.get_text(" ", strip=True).lower().split())
            href = anchor.get("href", "")
            absolute = normalize_url(urljoin(website, href))

            if not absolute or not same_domain(website, absolute):
                continue
            if is_private_or_login_url(absolute):
                continue

            haystack = f"{label} {absolute}".lower()
            if any(keyword in haystack for keyword in CONTACT_LINK_KEYWORDS):
                links.append(absolute)

        links = list(dict.fromkeys(links))
        return [website] + links

    def fetch(self, url: str) -> str | None:
        url = normalize_url(url)
        if not url:
            return None
        if url in self.page_cache:
            return self.page_cache[url]
        if url in self.visited_urls:
            return None
        if is_blocked_url(url) or is_private_or_login_url(url):
            self.log(f"Skipped blocked/private URL: {url}")
            return None
        if not self.can_fetch(url):
            self.log(f"Skipped by robots.txt: {url}")
            return None

        self.visited_urls.add(url)
        time.sleep(self.delay)

        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            content_type = response.headers.get("content-type", "").lower()
            if response.status_code >= 400 or "text/html" not in content_type:
                self.log(f"Skipped non-HTML/error page ({response.status_code}): {url}")
                return None
            self.page_cache[url] = response.text
            return response.text
        except requests.RequestException:
            self.log(f"Request failed: {url}")
            return None

    def can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False

        root = f"{parsed.scheme}://{parsed.netloc}"
        if root not in self.robot_cache:
            robots_url = urljoin(root, "/robots.txt")
            parser = RobotFileParser()
            parser.set_url(robots_url)
            try:
                parser.read()
                self.robot_cache[root] = parser
            except Exception:
                self.robot_cache[root] = None

        parser = self.robot_cache[root]
        if parser is None:
            return True

        try:
            return parser.can_fetch(self.session.headers["User-Agent"], url)
        except Exception:
            return True

    def log(self, message: str) -> None:
        if self.verbose:
            print(message)
