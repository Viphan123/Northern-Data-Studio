import argparse
from pathlib import Path

import pandas as pd

from scraper import LeadScraper


DEFAULT_INDUSTRIES = [
    "logistics",
    "construction",
    "marketing agency",
    "property management",
    "e-commerce",
]

DEFAULT_LOCATIONS = [
    "Ottawa Canada",
    "Ontario Canada",
    "Canada",
    "USA",
]


def build_default_search_urls(max_per_industry: int) -> list[str]:
    """Build public search-result URLs that the scraper can use as discovery pages."""
    from urllib.parse import quote_plus

    urls = []
    for industry in DEFAULT_INDUSTRIES:
        industry_url_count = 0
        for location in DEFAULT_LOCATIONS:
            query = f'{location} "{industry}" company contact email phone'
            urls.append(f"https://duckduckgo.com/html/?q={quote_plus(query)}")
            urls.append(f"https://www.bing.com/search?q={quote_plus(query)}")
            industry_url_count += 1
            if industry_url_count >= max_per_industry:
                break
    return urls


def build_default_directory_urls() -> list[str]:
    from urllib.parse import quote_plus

    categories = {
        "logistics": "logistics",
        "construction": "construction companies",
        "marketing agency": "marketing agencies",
        "property management": "property management",
        "e-commerce": "ecommerce",
    }
    locations = ["Ottawa ON", "Toronto ON", "Montreal QC", "Vancouver BC", "Calgary AB"]
    urls = []

    for category in categories.values():
        for location in locations:
            urls.append(
                "https://www.yellowpages.ca/search/si/1/"
                f"{quote_plus(category)}/{quote_plus(location)}"
            )

    return urls


def read_seed_file(path: str | None) -> list[str]:
    if not path:
        return []

    seed_path = Path(path)
    if not seed_path.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_path}")

    return [
        line.strip()
        for line in seed_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find public business leads for Northern Data Studio."
    )
    parser.add_argument("--target-count", type=int, default=50)
    parser.add_argument("--output", default="leads.csv")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-pages-per-site", type=int, default=4)
    parser.add_argument("--max-search-urls-per-industry", type=int, default=3)
    parser.add_argument("--seed-url", action="append", default=[])
    parser.add_argument("--seed-file")
    parser.add_argument("--search-url", action="append", default=[])
    parser.add_argument("--quiet", action="store_true", help="Hide progress logs.")
    parser.add_argument(
        "--include-default-search",
        action="store_true",
        help="Also use default search pages when a seed file is present.",
    )
    parser.add_argument(
        "--include-directories",
        action="store_true",
        help="Also try public directory pages. These can be slow or blocked.",
    )
    parser.add_argument(
        "--no-default-search",
        action="store_true",
        help="Only use URLs passed with --seed-url, --seed-file, or --search-url.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    seed_urls = list(args.seed_url) + read_seed_file(args.seed_file)
    default_seed_path = Path("seeds.txt")
    if not args.seed_file and default_seed_path.exists():
        seed_urls.extend(read_seed_file(str(default_seed_path)))

    search_urls = list(args.search_url)

    use_default_search = (
        not args.no_default_search
        and (not seed_urls or args.include_default_search)
    )
    if use_default_search:
        search_urls.extend(build_default_search_urls(args.max_search_urls_per_industry))

    if args.include_directories:
        search_urls.extend(build_default_directory_urls())

    scraper = LeadScraper(
        target_count=args.target_count,
        delay=args.delay,
        timeout=args.timeout,
        max_pages_per_site=args.max_pages_per_site,
        verbose=not args.quiet,
    )

    leads = scraper.run(search_urls=search_urls, seed_urls=seed_urls)
    frame = pd.DataFrame(
        leads,
        columns=[
            "company_name",
            "industry",
            "city",
            "country",
            "website",
            "email",
            "phone",
            "source_url",
            "notes",
        ],
    )

    frame.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(frame)} leads to {args.output}")


if __name__ == "__main__":
    main()
