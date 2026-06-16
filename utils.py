import re
from urllib.parse import parse_qs, urljoin, urlparse


BLOCKED_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "m.facebook.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}

SEARCH_DOMAINS = {
    "bing.com",
    "duckduckgo.com",
    "google.com",
}

DIRECTORY_DOMAINS = {
    "yellowpages.ca",
    "yelp.ca",
    "clutch.co",
    "goodfirms.co",
    "cylex-canada.ca",
}

PRIVATE_PATH_KEYWORDS = {
    "account",
    "admin",
    "cart",
    "checkout",
    "login",
    "logout",
    "my-account",
    "password",
    "portal",
    "register",
    "signin",
    "sign-in",
    "signup",
    "wp-admin",
}

CONTACT_LINK_KEYWORDS = {
    "contact",
    "locations",
    "office",
    "team",
    "about",
    "support",
    "get in touch",
    "request",
    "quote",
}

INDUSTRY_KEYWORDS = {
    "Logistics": [
        "logistics",
        "freight",
        "warehousing",
        "warehouse",
        "transportation",
        "trucking",
        "supply chain",
        "distribution",
        "fulfillment",
    ],
    "Construction": [
        "construction",
        "contractor",
        "building",
        "infrastructure",
        "civil",
        "earthworks",
        "renovation",
        "industrial construction",
    ],
    "Marketing Agency": [
        "marketing agency",
        "digital marketing",
        "branding",
        "seo",
        "advertising",
        "creative agency",
        "media buying",
        "social media marketing",
    ],
    "Property Management": [
        "property management",
        "rental management",
        "condominium management",
        "real estate management",
        "tenant",
        "landlord",
        "strata",
    ],
    "E-commerce": [
        "ecommerce",
        "e-commerce",
        "online store",
        "shopify",
        "retail",
        "direct to consumer",
        "d2c",
        "marketplace",
    ],
}

CITY_KEYWORDS = [
    "Ottawa",
    "Gatineau",
    "Toronto",
    "Mississauga",
    "Montreal",
    "Vancouver",
    "Calgary",
    "Edmonton",
    "Halifax",
    "New York",
    "Chicago",
    "Boston",
    "Seattle",
    "Austin",
    "San Francisco",
    "Los Angeles",
]

COUNTRY_KEYWORDS = {
    "Canada": ["Canada", "Ontario", "Quebec", "British Columbia", "Alberta", "Nova Scotia"],
    "USA": ["United States", "USA", "U.S.", "US ", "New York", "California", "Texas"],
}

EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?x)(?:\+?1[\s.\-]?)?(?:\(?[2-9]\d{2}\)?[\s.\-]?)?[2-9]\d{2}[\s.\-]?\d{4}"
)
GENERIC_EMAIL_PREFIXES = (
    "info",
    "contact",
    "sales",
    "hello",
    "support",
    "admin",
    "office",
    "inquiries",
    "enquiries",
    "service",
    "customerservice",
    "marketing",
)


def normalize_url(url: str, root_only: bool = False) -> str:
    if not url:
        return ""

    url = url.strip()
    if url.startswith("//"):
        url = f"https:{url}"
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    parsed = urlparse(url)
    if not parsed.netloc:
        return ""

    scheme = "https" if parsed.scheme in {"http", "https"} else parsed.scheme
    netloc = parsed.netloc.lower().replace("www.", "")
    path = "" if root_only else parsed.path
    if path == "/":
        path = ""

    normalized = f"{scheme}://{netloc}{path}"
    return normalized.rstrip("/")


def domain_from_url(url: str) -> str:
    return urlparse(normalize_url(url)).netloc.lower().replace("www.", "")


def same_domain(left: str, right: str) -> bool:
    return domain_from_url(left) == domain_from_url(right)


def is_blocked_url(url: str) -> bool:
    domain = domain_from_url(url)
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in BLOCKED_DOMAINS)


def is_private_or_login_url(url: str) -> bool:
    parsed = urlparse(normalize_url(url))
    path = parsed.path.lower()
    return any(keyword in path for keyword in PRIVATE_PATH_KEYWORDS)


def is_likely_company_url(url: str) -> bool:
    parsed = urlparse(normalize_url(url))
    domain = parsed.netloc.lower()
    path = parsed.path.lower()

    if not domain or is_blocked_url(url) or is_private_or_login_url(url):
        return False
    if any(domain.endswith(search_host) for search_host in SEARCH_DOMAINS):
        return False
    if is_directory_url(url):
        return False
    if re.search(r"\.(pdf|jpg|jpeg|png|gif|webp|svg|zip|docx?|xlsx?)$", path):
        return False

    return True


def is_directory_url(url: str) -> bool:
    domain = domain_from_url(url)
    return any(domain == directory or domain.endswith(f".{directory}") for directory in DIRECTORY_DOMAINS)


def unwrap_search_url(href: str) -> str:
    if not href:
        return ""

    parsed = urlparse(href)
    query = parse_qs(parsed.query)

    for key in ("q", "u", "url", "uddg"):
        value = query.get(key, [""])[0]
        if value.startswith(("http://", "https://")):
            return value

    if href.startswith("/"):
        return href

    return href


def extract_emails(text: str) -> list[str]:
    emails = EMAIL_RE.findall(text or "")
    cleaned = []

    for email in emails:
        email = email.strip(".,;:()[]{}<>").lower()
        if email.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
            continue
        if any(skip in email for skip in ("example.com", "domain.com", "email.com")):
            continue
        cleaned.append(email)

    unique = list(dict.fromkeys(cleaned))
    return sorted(unique, key=email_priority)


def email_priority(email: str) -> tuple[int, str]:
    prefix = email.split("@", 1)[0].lower()
    if prefix in GENERIC_EMAIL_PREFIXES:
        return (0, email)
    if any(prefix.startswith(f"{generic}.") for generic in GENERIC_EMAIL_PREFIXES):
        return (0, email)
    return (1, email)


def extract_phone_numbers(text: str) -> list[str]:
    matches = PHONE_RE.findall(text or "")
    phones = []

    for match in matches:
        digits = re.sub(r"\D", "", match)
        if len(digits) == 10:
            phones.append(f"({digits[:3]}) {digits[3:6]}-{digits[6:]}")
        elif len(digits) == 11 and digits.startswith("1"):
            phones.append(f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}")

    return list(dict.fromkeys(phones))


def extract_company_name(soup, website: str) -> str:
    for selector in [
        ('meta[property="og:site_name"]', "content"),
        ('meta[property="og:title"]', "content"),
        ('meta[name="application-name"]', "content"),
    ]:
        tag = soup.select_one(selector[0])
        if tag and tag.get(selector[1]):
            return clean_company_name(tag.get(selector[1], ""))

    if soup.title and soup.title.string:
        return clean_company_name(soup.title.string)

    return domain_from_url(website).split(".")[0].title()


def clean_company_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name or "").strip()
    name = re.split(r"\s[|-]\s| - | \| ", name)[0].strip()
    return name[:120]


def detect_industry(text: str) -> str:
    text_lower = (text or "").lower()
    scores = {}

    for industry, keywords in INDUSTRY_KEYWORDS.items():
        scores[industry] = sum(1 for keyword in keywords if keyword.lower() in text_lower)

    best_industry, best_score = max(scores.items(), key=lambda item: item[1])
    return best_industry if best_score else "Unknown"


def detect_city_country(text: str) -> tuple[str, str]:
    text_blob = text or ""
    city = ""
    country = ""

    for candidate in CITY_KEYWORDS:
        if re.search(rf"\b{re.escape(candidate)}\b", text_blob, flags=re.IGNORECASE):
            city = candidate
            break

    for candidate_country, keywords in COUNTRY_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(keyword)}\b", text_blob, flags=re.IGNORECASE) for keyword in keywords):
            country = candidate_country
            break

    return city, country


def dedupe_leads(leads: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    unique = []

    for lead in leads:
        website_key = domain_from_url(lead.get("website", ""))
        email_key = lead.get("email", "").lower()
        key = (website_key, email_key)

        if key in seen:
            continue

        seen.add(key)
        unique.append(lead)

    return unique
