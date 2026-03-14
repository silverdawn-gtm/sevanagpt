"""Multi-strategy link extraction pipeline for government schemes.

Extracts official website links for schemes using multiple strategies:
0. Curated links (hand-verified dict, highest confidence)
1. MyScheme Detail API (fastest, best coverage)
2. HuggingFace dataset cross-reference (~723 schemes)
3. MyScheme.gov.in page scraping (Playwright fallback)
4. DuckDuckGo Search (last resort, replaces blocked Google scraper)

Usage:
    python -m app.data.extract_links [--batch-size 50] [--limit 10] [--strategy curated|api|hf|scrape|search|all]
"""

import argparse
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.data.curated_links import CURATED_LINKS, get_curated_link
from app.models import Scheme

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# MyScheme API config (reuse from ingest_myscheme.py)
API_BASE = "https://api.myscheme.gov.in/search/v6"
API_KEY = "tYTy5eEhlu9rFjyxuCr7ra7ACp4dv1RH8gWuHTDc"
HEADERS = {
    "x-api-key": API_KEY,
    "Origin": "https://www.myscheme.gov.in",
    "Referer": "https://www.myscheme.gov.in/",
    "User-Agent": "Mozilla/5.0 (compatible; SevanaGPT/1.0)",
}

CHECKPOINT_FILE = Path(__file__).parent / "extraction_checkpoint.json"
RESULTS_FILE = Path(__file__).parent / "extraction_results.json"

# Concurrency controls
API_SEMAPHORE = asyncio.Semaphore(10)
SCRAPE_SEMAPHORE = asyncio.Semaphore(5)
API_DELAY = 0.5
SCRAPE_DELAY = 3.0


def load_checkpoint() -> dict:
    """Load extraction checkpoint for resume support."""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"completed_slugs": [], "results": {}, "started_at": datetime.now().isoformat()}


def save_checkpoint(checkpoint: dict):
    """Save extraction checkpoint."""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f, indent=2, default=str)


def save_results(results: dict):
    """Save final extraction results."""
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Strategy 1: MyScheme Detail API
# ---------------------------------------------------------------------------

async def extract_via_api(client: httpx.AsyncClient, slug: str) -> dict | None:
    """Try to get scheme details (including official link) from MyScheme detail API."""
    async with API_SEMAPHORE:
        try:
            # Try the detail endpoint
            resp = await client.get(
                f"{API_BASE}/schemeDetail/{slug}",
                headers=HEADERS,
                timeout=15.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                detail = data.get("data", {})
                if not detail:
                    return None

                result = {"strategy": "api", "slug": slug}

                # Extract official link from various possible fields
                for field in ["officialUrl", "official_url", "schemeUrl", "scheme_url",
                              "websiteUrl", "website_url", "url", "link",
                              "officialLink", "official_link"]:
                    val = detail.get(field)
                    if val and isinstance(val, str) and val.startswith("http"):
                        result["official_link"] = val.strip()
                        break

                # Also check nested fields
                if "official_link" not in result:
                    fields = detail.get("fields", {})
                    for field in ["officialUrl", "schemeUrl", "websiteUrl", "url"]:
                        val = fields.get(field)
                        if val and isinstance(val, str) and val.startswith("http"):
                            result["official_link"] = val.strip()
                            break

                # Extract extra details while we're here
                result["raw_detail"] = detail
                return result

            elif resp.status_code == 404:
                return None
            else:
                logger.warning(f"API returned {resp.status_code} for {slug}")
                return None

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning(f"API error for {slug}: {e}")
            return None
        finally:
            await asyncio.sleep(API_DELAY)


# ---------------------------------------------------------------------------
# Strategy 2: HuggingFace dataset cross-reference
# ---------------------------------------------------------------------------

def load_hf_dataset() -> dict[str, str]:
    """Load HuggingFace dataset and return slug->official_link mapping.

    Tries to load from datasets library; falls back to cached JSON if available.
    """
    cache_file = Path(__file__).parent / "hf_links_cache.json"

    # Try cached version first
    if cache_file.exists():
        logger.info("Loading HuggingFace links from cache...")
        with open(cache_file) as f:
            return json.load(f)

    # Try loading from datasets library
    try:
        from datasets import load_dataset
        logger.info("Loading HuggingFace dataset shrijayan/gov_myscheme...")
        ds = load_dataset("shrijayan/gov_myscheme", split="train")

        links = {}
        for row in ds:
            # Try different column name patterns
            slug = None
            link = None

            for col in ["slug", "Slug", "scheme_slug"]:
                if col in row and row[col]:
                    slug = row[col].strip()
                    break

            # If no slug, derive from scheme name
            if not slug:
                for col in ["Scheme", "scheme_name", "schemeName", "name", "Name"]:
                    if col in row and row[col]:
                        from app.utils.slug import slugify
                        slug = slugify(row[col].strip())
                        break

            for col in ["Official Link", "official_link", "officialLink", "url", "URL", "website"]:
                if col in row and row[col]:
                    val = str(row[col]).strip()
                    if val.startswith("http"):
                        link = val
                        break

            if slug and link:
                links[slug] = link

        # Cache for next time
        with open(cache_file, "w") as f:
            json.dump(links, f, indent=2)

        logger.info(f"Loaded {len(links)} links from HuggingFace dataset")
        return links

    except ImportError:
        logger.warning("datasets library not installed. Run: pip install datasets")
        return {}
    except Exception as e:
        logger.warning(f"Failed to load HuggingFace dataset: {e}")
        return {}


def match_hf_links(schemes: list[dict], hf_links: dict[str, str]) -> dict[str, str]:
    """Match scheme slugs to HuggingFace links.

    Returns dict of slug -> official_link for matched schemes.
    """
    matched = {}
    for scheme in schemes:
        slug = scheme["slug"]
        if slug in hf_links:
            matched[slug] = hf_links[slug]
        else:
            # Try fuzzy matching - remove common prefixes
            for hf_slug, link in hf_links.items():
                if slug in hf_slug or hf_slug in slug:
                    matched[slug] = link
                    break
    return matched


# ---------------------------------------------------------------------------
# Strategy 3: MyScheme.gov.in page scraping (Playwright)
# ---------------------------------------------------------------------------

async def extract_via_scraping(slug: str) -> dict | None:
    """Scrape the MyScheme.gov.in scheme page for the official link."""
    async with SCRAPE_SEMAPHORE:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                url = f"https://www.myscheme.gov.in/schemes/{slug}"
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Wait for content to load
                await page.wait_for_timeout(2000)

                # Look for official website links in the page
                result = await page.evaluate("""() => {
                    const links = [];
                    // Look for links labeled "Official Website", "Visit Website", etc.
                    const allLinks = document.querySelectorAll('a[href]');
                    for (const a of allLinks) {
                        const text = (a.textContent || '').toLowerCase().trim();
                        const href = a.href;
                        if ((text.includes('official') || text.includes('website') ||
                             text.includes('visit') || text.includes('portal') ||
                             text.includes('apply here') || text.includes('apply now')) &&
                            href.startsWith('http') &&
                            !href.includes('myscheme.gov.in')) {
                            links.push({text: text, url: href});
                        }
                    }

                    // Also check for meta tags with scheme URL
                    const ogUrl = document.querySelector('meta[property="og:url"]');
                    const canonical = document.querySelector('link[rel="canonical"]');

                    // Look for structured data
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    let structuredUrl = null;
                    for (const s of scripts) {
                        try {
                            const data = JSON.parse(s.textContent);
                            if (data.url && !data.url.includes('myscheme.gov.in')) {
                                structuredUrl = data.url;
                            }
                        } catch {}
                    }

                    return {links, structuredUrl};
                }""")

                await browser.close()

                if result["links"]:
                    return {
                        "strategy": "scraping",
                        "slug": slug,
                        "official_link": result["links"][0]["url"],
                        "all_links": result["links"],
                    }
                elif result.get("structuredUrl"):
                    return {
                        "strategy": "scraping",
                        "slug": slug,
                        "official_link": result["structuredUrl"],
                    }

                return None

        except Exception as e:
            logger.warning(f"Scraping error for {slug}: {e}")
            return None
        finally:
            await asyncio.sleep(SCRAPE_DELAY)


# ---------------------------------------------------------------------------
# Strategy 0: Curated links
# ---------------------------------------------------------------------------

def extract_via_curated(slug: str) -> dict | None:
    """Check the hand-verified curated links dict."""
    link = get_curated_link(slug)
    if link:
        return {"strategy": "curated", "slug": slug, "official_link": link}
    return None


# ---------------------------------------------------------------------------
# Strategy 4: DuckDuckGo Search fallback (replaces blocked Google scraper)
# ---------------------------------------------------------------------------

EXCLUDED_DOMAINS = ["myscheme.gov.in", "youtube.com", "wikipedia.org", "facebook.com"]


def extract_via_search(name: str, slug: str) -> dict | None:
    """Search DuckDuckGo for the official website of a scheme."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.warning("duckduckgo-search not installed. Run: pip install duckduckgo-search")
        return None

    try:
        # Multi-query: try site:gov.in first, then broader
        queries = [
            f"site:gov.in {name} official website",
            f"{name} official website India government scheme",
        ]

        for query in queries:
            try:
                with DDGS() as ddgs:
                    results = ddgs.text(query, region="in-en", max_results=8)
                    urls = [r["href"] for r in results if r.get("href")]
            except Exception:
                urls = []

            if not urls:
                continue

            # Filter for likely official sites (.gov.in, .nic.in)
            official_domains = [".gov.in", ".nic.in", ".india.gov.in"]
            for url in urls:
                lower = url.lower()
                if any(excl in lower for excl in EXCLUDED_DOMAINS):
                    continue
                if any(domain in lower for domain in official_domains):
                    return {
                        "strategy": "search",
                        "slug": slug,
                        "official_link": url,
                        "search_results": urls,
                    }

            # If no .gov.in result, return the first non-excluded result
            for url in urls:
                lower = url.lower()
                if not any(excl in lower for excl in EXCLUDED_DOMAINS):
                    return {
                        "strategy": "search",
                        "slug": slug,
                        "official_link": url,
                        "confidence": "low",
                    }

        return None

    except Exception as e:
        logger.warning(f"DuckDuckGo search error for {slug}: {e}")
        return None


# ---------------------------------------------------------------------------
# Main extraction pipeline
# ---------------------------------------------------------------------------

async def extract_links(
    batch_size: int = 50,
    limit: int | None = None,
    strategies: list[str] | None = None,
    resume: bool = True,
):
    """Run the multi-strategy link extraction pipeline."""
    if strategies is None:
        strategies = ["curated", "api", "hf", "scrape", "search"]

    logger.info("=" * 60)
    logger.info("Link Extraction Pipeline")
    logger.info(f"Strategies: {strategies}")
    logger.info(f"Batch size: {batch_size}, Limit: {limit or 'all'}")
    logger.info("=" * 60)

    # Load checkpoint for resume
    checkpoint = load_checkpoint() if resume else {
        "completed_slugs": [], "results": {}, "started_at": datetime.now().isoformat()
    }
    completed_slugs = set(checkpoint.get("completed_slugs", []))
    results = checkpoint.get("results", {})

    # Connect to DB
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Get all schemes without official links
        query = select(Scheme.id, Scheme.slug, Scheme.name).where(
            Scheme.official_link.is_(None)
        ).order_by(Scheme.slug)

        if limit:
            query = query.limit(limit)

        rows = (await session.execute(query)).all()
        total_schemes = len(rows)
        schemes = [{"id": str(r.id), "slug": r.slug, "name": r.name} for r in rows]

        # Filter already completed
        schemes = [s for s in schemes if s["slug"] not in completed_slugs]
        logger.info(f"Total schemes without links: {total_schemes}")
        logger.info(f"Already completed: {len(completed_slugs)}")
        logger.info(f"Remaining: {len(schemes)}")

        if not schemes:
            logger.info("Nothing to do!")
            await engine.dispose()
            return results

        # Strategy 0: Curated links (instant, highest confidence)
        if "curated" in strategies:
            curated_found = 0
            for scheme in list(schemes):
                curated_result = extract_via_curated(scheme["slug"])
                if curated_result and curated_result.get("official_link"):
                    results[scheme["slug"]] = curated_result
                    completed_slugs.add(scheme["slug"])
                    curated_found += 1

                    await session.execute(
                        update(Scheme)
                        .where(Scheme.slug == scheme["slug"])
                        .values(official_link=curated_result["official_link"])
                    )

            if curated_found:
                await session.commit()
                logger.info(f"Curated links applied: {curated_found}")
                schemes = [s for s in schemes if s["slug"] not in completed_slugs]

                checkpoint["completed_slugs"] = list(completed_slugs)
                checkpoint["results"] = {
                    k: {kk: vv for kk, vv in v.items() if kk != "raw_detail"}
                    for k, v in results.items()
                }
                save_checkpoint(checkpoint)

        # Strategy 2: Pre-load HuggingFace links if enabled
        hf_links = {}
        if "hf" in strategies:
            hf_links = load_hf_dataset()
            hf_matched = match_hf_links(schemes, hf_links)
            logger.info(f"HuggingFace matches: {len(hf_matched)} / {len(schemes)}")

            # Apply HF matches immediately
            for slug, link in hf_matched.items():
                if slug not in results:
                    results[slug] = {
                        "strategy": "hf",
                        "slug": slug,
                        "official_link": link,
                    }
                    completed_slugs.add(slug)

            # Update DB with HF links
            if hf_matched:
                for slug, link in hf_matched.items():
                    await session.execute(
                        update(Scheme).where(Scheme.slug == slug).values(official_link=link)
                    )
                await session.commit()
                logger.info(f"Updated {len(hf_matched)} schemes with HuggingFace links")

            # Filter out HF-matched schemes from remaining work
            schemes = [s for s in schemes if s["slug"] not in completed_slugs]

        # Strategy 1: MyScheme Detail API
        if "api" in strategies and schemes:
            logger.info(f"\nRunning API extraction for {len(schemes)} schemes...")
            async with httpx.AsyncClient(verify=False) as client:
                for batch_start in range(0, len(schemes), batch_size):
                    batch = schemes[batch_start:batch_start + batch_size]
                    batch_num = batch_start // batch_size + 1
                    total_batches = (len(schemes) + batch_size - 1) // batch_size

                    logger.info(f"API batch {batch_num}/{total_batches} ({len(batch)} schemes)")

                    tasks = [extract_via_api(client, s["slug"]) for s in batch]
                    api_results = await asyncio.gather(*tasks)

                    found = 0
                    for scheme, api_result in zip(batch, api_results):
                        if api_result and api_result.get("official_link"):
                            results[scheme["slug"]] = api_result
                            completed_slugs.add(scheme["slug"])
                            found += 1

                            # Update DB
                            await session.execute(
                                update(Scheme)
                                .where(Scheme.slug == scheme["slug"])
                                .values(official_link=api_result["official_link"])
                            )

                    await session.commit()
                    logger.info(f"  Found {found}/{len(batch)} links in this batch")

                    # Save checkpoint
                    checkpoint["completed_slugs"] = list(completed_slugs)
                    checkpoint["results"] = {
                        k: {kk: vv for kk, vv in v.items() if kk != "raw_detail"}
                        for k, v in results.items()
                    }
                    save_checkpoint(checkpoint)

            # Filter out API-matched schemes
            schemes = [s for s in schemes if s["slug"] not in completed_slugs]
            logger.info(f"After API: {len(schemes)} schemes still need links")

        # Strategy 3: Playwright scraping
        if "scrape" in strategies and schemes:
            logger.info(f"\nRunning scraping for {len(schemes)} remaining schemes...")

            for batch_start in range(0, len(schemes), batch_size):
                batch = schemes[batch_start:batch_start + batch_size]
                batch_num = batch_start // batch_size + 1
                total_batches = (len(schemes) + batch_size - 1) // batch_size

                logger.info(f"Scrape batch {batch_num}/{total_batches} ({len(batch)} schemes)")

                # Scrape sequentially within batch (browser resource limits)
                found = 0
                for scheme in batch:
                    scrape_result = await extract_via_scraping(scheme["slug"])
                    if scrape_result and scrape_result.get("official_link"):
                        results[scheme["slug"]] = scrape_result
                        completed_slugs.add(scheme["slug"])
                        found += 1

                        await session.execute(
                            update(Scheme)
                            .where(Scheme.slug == scheme["slug"])
                            .values(official_link=scrape_result["official_link"])
                        )

                await session.commit()
                logger.info(f"  Found {found}/{len(batch)} links in this batch")

                checkpoint["completed_slugs"] = list(completed_slugs)
                checkpoint["results"] = {
                    k: {kk: vv for kk, vv in v.items() if kk != "raw_detail"}
                    for k, v in results.items()
                }
                save_checkpoint(checkpoint)

            schemes = [s for s in schemes if s["slug"] not in completed_slugs]

        # Strategy 4: DuckDuckGo Search
        if "search" in strategies and schemes:
            logger.info(f"\nRunning DuckDuckGo search for {len(schemes)} remaining schemes...")

            for batch_start in range(0, len(schemes), batch_size):
                batch = schemes[batch_start:batch_start + batch_size]
                batch_num = batch_start // batch_size + 1
                total_batches = (len(schemes) + batch_size - 1) // batch_size

                logger.info(f"Search batch {batch_num}/{total_batches}")

                found = 0
                for scheme in batch:
                    search_result = extract_via_search(scheme["name"], scheme["slug"])
                    if search_result and search_result.get("official_link"):
                        results[scheme["slug"]] = search_result
                        completed_slugs.add(scheme["slug"])
                        found += 1

                        await session.execute(
                            update(Scheme)
                            .where(Scheme.slug == scheme["slug"])
                            .values(official_link=search_result["official_link"])
                        )

                    await asyncio.sleep(1.5)  # Rate-limit DuckDuckGo

                await session.commit()
                logger.info(f"  Found {found}/{len(batch)} links")

                checkpoint["completed_slugs"] = list(completed_slugs)
                checkpoint["results"] = {
                    k: {kk: vv for kk, vv in v.items() if kk != "raw_detail"}
                    for k, v in results.items()
                }
                save_checkpoint(checkpoint)

    await engine.dispose()

    # Save final results
    final_results = {
        k: {kk: vv for kk, vv in v.items() if kk != "raw_detail"}
        for k, v in results.items()
    }
    save_results(final_results)

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Extraction Complete!")
    logger.info(f"Total links found: {len(results)}")
    strategy_counts = {}
    for r in results.values():
        s = r.get("strategy", "unknown")
        strategy_counts[s] = strategy_counts.get(s, 0) + 1
    for strategy, count in sorted(strategy_counts.items()):
        logger.info(f"  {strategy}: {count}")
    logger.info(f"Schemes still without links: {total_schemes - len(results)}")
    logger.info(f"Results saved to: {RESULTS_FILE}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Extract official links for government schemes")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for processing")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of schemes to process")
    parser.add_argument(
        "--strategy",
        choices=["curated", "api", "hf", "scrape", "search", "all"],
        default="all",
        help="Extraction strategy to use",
    )
    parser.add_argument("--no-resume", action="store_true", help="Start fresh, ignore checkpoint")
    args = parser.parse_args()

    strategies = ["curated", "api", "hf", "scrape", "search"] if args.strategy == "all" else [args.strategy]

    asyncio.run(extract_links(
        batch_size=args.batch_size,
        limit=args.limit,
        strategies=strategies,
        resume=not args.no_resume,
    ))


if __name__ == "__main__":
    main()
