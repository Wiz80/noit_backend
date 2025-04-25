#!/usr/bin/env python3
"""Debug script for LinkedInAdsService.

Execute a live scrape against LinkedIn Ad Library for a given company to help
inspect issues without running the full pytest suite.  This is useful when you
face import timeouts or want step‑by‑step debugging via VS Code.

Usage (from project root):

    python scripts/debug_linkedin_ads_service.py --company nvidia --country BR --max 5

The script prints the JSON of the first ad plus a summary of the extraction.
"""

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Ensure project root in path
ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))

from app.services.business.competitive_analysis.linkedin.linkedin_ads_service import (
    LinkedInAdsService,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug LinkedIn Ads Scraper")
    parser.add_argument("--company", default="nvidia", help="Account owner / company")
    parser.add_argument("--country", default="BR", help="Country code (e.g. BR, US)")
    parser.add_argument("--date_option", default="last-30-days", help="Date filter")
    parser.add_argument("--max", type=int, default=5, help="Max ads to fetch")
    parser.add_argument("--no-detect", action="store_true", help="Disable selector detection")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    load_dotenv()

    service = LinkedInAdsService(
        verbose=True,
        headless=args.headless,
        max_retries=1,
    )

    search_url = service.build_search_url(
        account_owner=args.company,
        countries=[args.country],
        date_option=args.date_option,
    )

    print(f"Search URL: {search_url}\n")

    result = await service.fetch_ads_data(
        search_url=search_url,
        max_results=args.max,
        detect_selectors=not args.no_detect,
    )

    print("\nExtraction summary:\n", json.dumps({k: v for k, v in result.items() if k != "data"}, indent=2))

    if result.get("success") and result.get("data"):
        print("\nFirst ad sample:\n", json.dumps(result["data"][0], indent=2, ensure_ascii=False))
    else:
        print("\nExtraction failed:", result.get("error"))


if __name__ == "__main__":
    asyncio.run(main()) 