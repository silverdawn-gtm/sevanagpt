"""Manual link search & update CLI for government schemes.

Interactive tool to find official .gov.in websites for schemes using:
  Strategy 0: Curated links (hand-verified dict)
  Strategy 1: MyScheme Detail API (schemeDetail/{slug})
  Strategy 2: DuckDuckGo search (multi-query, site:gov.in)
  Strategy 3: Link validation (HEAD/GET every link before saving)

Modes:
    --search "scheme name"   Search for a single scheme interactively
    --batch N                Auto-process N schemes without links
    --verify                 Re-validate all existing links

Usage:
    python -m app.data.manual_link_search --search "Pradhan Mantri Jan Dhan Yojana"
    python -m app.data.manual_link_search --batch 50
    python -m app.data.manual_link_search --batch 50 --no-resume
    python -m app.data.manual_link_search --verify
"""

import argparse
import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.data.curated_links import CURATED_LINKS, get_curated_link
from app.models import Scheme

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Checkpoint file for --batch resume support
CHECKPOINT_FILE = Path(__file__).parent / "link_search_checkpoint.json"

# HTTP validation settings
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 30.0
MAX_RETRIES = 2
RETRY_BACKOFF = [1.0, 2.0]

# DuckDuckGo search delay (seconds) to avoid rate limiting
DDGS_DELAY = 1.5

# MyScheme API config
MYSCHEME_API_BASE = "https://api.myscheme.gov.in/search/v6"
MYSCHEME_API_KEY = "tYTy5eEhlu9rFjyxuCr7ra7ACp4dv1RH8gWuHTDc"
MYSCHEME_HEADERS = {
    "x-api-key": MYSCHEME_API_KEY,
    "Origin": "https://www.myscheme.gov.in",
    "Referer": "https://www.myscheme.gov.in/",
    "User-Agent": "Mozilla/5.0 (compatible; SevanaGPT/1.0)",
}

# Domains to prioritize (higher = better)
PRIORITY_DOMAINS = [".gov.in", ".nic.in", ".india.gov.in"]
# Domains to exclude from results
EXCLUDED_DOMAINS = ["myscheme.gov.in", "youtube.com", "wikipedia.org", "facebook.com"]


def _get_engine_and_session():
    """Create async engine + session factory."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, session_factory


# ---------------------------------------------------------------------------
# Checkpoint support for batch mode
# ---------------------------------------------------------------------------

def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"completed_slugs": [], "results": {}, "started_at": datetime.now().isoformat()}


def save_checkpoint(checkpoint: dict):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Strategy 1: MyScheme Detail API
# ---------------------------------------------------------------------------

async def myscheme_api_search(client: httpx.AsyncClient, slug: str) -> str | None:
    """Try to extract an official link from the MyScheme detail API."""
    try:
        resp = await client.get(
            f"{MYSCHEME_API_BASE}/schemeDetail/{slug}",
            headers=MYSCHEME_HEADERS,
            timeout=15.0,
        )
        if resp.status_code != 200:
            return None

        detail = resp.json().get("data", {})
        if not detail:
            return None

        # Check top-level fields first, then nested "fields"
        for source in [detail, detail.get("fields", {})]:
            for field in [
                "officialUrl", "official_url", "schemeUrl", "scheme_url",
                "websiteUrl", "website_url", "url", "link",
                "officialLink", "official_link",
            ]:
                val = source.get(field)
                if val and isinstance(val, str) and val.startswith("http"):
                    url = val.strip()
                    # Skip myscheme.gov.in self-references
                    if "myscheme.gov.in" not in url.lower():
                        return url

        return None
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        logger.warning("MyScheme API error for %s: %s", slug, e)
        return None


# ---------------------------------------------------------------------------
# Strategy 2: DuckDuckGo Search
# ---------------------------------------------------------------------------

def web_search(query: str, max_results: int = 10) -> list[str]:
    """Search DuckDuckGo and return a list of URLs."""
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = ddgs.text(query, region="in-en", max_results=max_results)
            return [r["href"] for r in results if r.get("href")]
    except ImportError:
        logger.error("duckduckgo-search not installed. Run: pip install duckduckgo-search")
        return []
    except Exception as e:
        logger.warning("DuckDuckGo search failed for %r: %s", query, e)
        return []


def _build_queries(name: str) -> list[str]:
    """Build multiple search queries for a scheme name (best first)."""
    return [
        f"site:gov.in {name} official website",
        f"{name} official website India government",
        f"{name} .gov.in portal",
    ]


def rank_urls(urls: list[str]) -> list[dict]:
    """Rank URLs by domain priority. Returns list of {url, score, domain_type}."""
    ranked = []
    for url in urls:
        lower = url.lower()
        # Skip excluded domains
        if any(excl in lower for excl in EXCLUDED_DOMAINS):
            continue

        score = 0
        domain_type = "other"
        if ".gov.in" in lower:
            score = 30
            domain_type = "gov.in"
        if ".nic.in" in lower:
            score = max(score, 20)
            domain_type = domain_type if score > 20 else "nic.in"
        if ".india.gov.in" in lower:
            score = 25
            domain_type = "india.gov.in"

        ranked.append({"url": url, "score": score, "domain_type": domain_type})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


# ---------------------------------------------------------------------------
# Link validation (reuses logic from validate_links.py)
# ---------------------------------------------------------------------------

async def validate_url(client: httpx.AsyncClient, url: str) -> dict:
    """Validate a single URL. Returns {status, status_code, final_url, error}."""
    result = {
        "url": url,
        "status": "unknown",
        "status_code": None,
        "final_url": None,
        "error": None,
    }

    for attempt in range(MAX_RETRIES):
        try:
            # HEAD first
            try:
                resp = await client.head(
                    url,
                    follow_redirects=True,
                    timeout=httpx.Timeout(
                        connect=CONNECT_TIMEOUT, read=READ_TIMEOUT,
                        write=10.0, pool=10.0,
                    ),
                )
            except httpx.HTTPStatusError:
                resp = None

            # GET fallback if HEAD returns 405 or fails
            if resp is None or resp.status_code == 405:
                resp = await client.get(
                    url,
                    follow_redirects=True,
                    timeout=httpx.Timeout(
                        connect=CONNECT_TIMEOUT, read=READ_TIMEOUT,
                        write=10.0, pool=10.0,
                    ),
                )

            result["status_code"] = resp.status_code
            result["final_url"] = str(resp.url)

            if 200 <= resp.status_code < 300:
                result["status"] = "working"
            elif 300 <= resp.status_code < 400:
                result["status"] = "redirected"
            elif resp.status_code >= 500 and attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_BACKOFF[attempt])
                continue
            else:
                result["status"] = "broken"
                result["error"] = f"HTTP {resp.status_code}"
            break

        except httpx.TimeoutException:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_BACKOFF[attempt])
                continue
            result["status"] = "timeout"
            result["error"] = "Connection/read timeout"
            break
        except httpx.ConnectError as e:
            err_str = str(e).lower()
            if "name resolution" in err_str or "dns" in err_str:
                result["status"] = "dns_error"
                result["error"] = "DNS resolution failed"
            else:
                result["status"] = "broken"
                result["error"] = str(e)[:200]
            break
        except Exception as e:
            result["status"] = "broken"
            result["error"] = str(e)[:200]
            break

    return result


# ---------------------------------------------------------------------------
# Mode 1: Interactive single-scheme search
# ---------------------------------------------------------------------------

async def search_scheme(name: str):
    """Search for a single scheme interactively."""
    engine, session_factory = _get_engine_and_session()

    async with session_factory() as session:
        # Fuzzy search DB for matching schemes
        rows = (await session.execute(
            select(Scheme.id, Scheme.slug, Scheme.name, Scheme.official_link)
            .where(func.lower(Scheme.name).contains(name.lower()))
            .order_by(Scheme.name)
            .limit(20)
        )).all()

        if not rows:
            logger.info("No schemes found matching %r", name)
            await engine.dispose()
            return

        print(f"\n{'='*70}")
        print(f"Found {len(rows)} matching scheme(s):")
        print(f"{'='*70}")
        for i, row in enumerate(rows, 1):
            link_info = f" -> {row.official_link}" if row.official_link else " (no link)"
            print(f"  [{i}] {row.name}{link_info}")

        print()
        selection = input("Enter number(s) to search (comma-separated, or 'all'): ").strip()
        if not selection:
            await engine.dispose()
            return

        if selection.lower() == "all":
            selected = list(range(len(rows)))
        else:
            try:
                selected = [int(x.strip()) - 1 for x in selection.split(",")]
            except ValueError:
                print("Invalid input.")
                await engine.dispose()
                return

        async with httpx.AsyncClient(
            verify=False, headers={"User-Agent": USER_AGENT},
        ) as client:
            for idx in selected:
                if idx < 0 or idx >= len(rows):
                    continue
                row = rows[idx]
                print(f"\n{'─'*60}")
                print(f"Scheme: {row.name}")
                print(f"Slug:   {row.slug}")
                print(f"Current link: {row.official_link or '(none)'}")

                # Strategy 0: Curated links
                curated = get_curated_link(row.slug)
                if curated:
                    print(f"\n  [CURATED] {curated}")
                    confirm = input(f"  Use curated link? [Y/n]: ").strip()
                    if confirm.lower() in ("", "y", "yes"):
                        vresult = await validate_url(client, curated)
                        if vresult["status"] in ("working", "redirected"):
                            final_url = vresult["final_url"] or curated
                            await session.execute(
                                update(Scheme).where(Scheme.slug == row.slug).values(
                                    official_link=final_url,
                                    link_status="working",
                                    link_checked_at=datetime.now(),
                                )
                            )
                            await session.commit()
                            print(f"  Saved (curated): {final_url}")
                            continue
                        else:
                            print(f"  Curated link failed validation: {vresult['error']}")

                # Strategy 1: MyScheme API
                api_url = await myscheme_api_search(client, row.slug)
                if api_url:
                    print(f"\n  [API] {api_url}")
                    vresult = await validate_url(client, api_url)
                    if vresult["status"] in ("working", "redirected"):
                        final_url = vresult["final_url"] or api_url
                        confirm = input(f"  Save API link '{final_url}'? [Y/n]: ").strip()
                        if confirm.lower() in ("", "y", "yes"):
                            await session.execute(
                                update(Scheme).where(Scheme.slug == row.slug).values(
                                    official_link=final_url,
                                    link_status="working",
                                    link_checked_at=datetime.now(),
                                )
                            )
                            await session.commit()
                            print(f"  Saved (api)!")
                            continue

                # Strategy 2: DuckDuckGo search with multi-query
                queries = _build_queries(row.name)
                all_urls = []
                for q in queries:
                    print(f"  Searching: {q!r}")
                    urls = web_search(q)
                    all_urls.extend(urls)
                    if urls:
                        break  # Got results, no need for fallback queries
                    time.sleep(DDGS_DELAY)

                ranked = rank_urls(all_urls)
                if not ranked:
                    print("  No results found.")
                    continue

                print(f"\n  Candidates (ranked by domain priority):")
                for j, r in enumerate(ranked[:8], 1):
                    print(f"    [{j}] ({r['domain_type']:>10}) {r['url']}")

                choice = input("\n  Pick a number to validate & save (or Enter to skip): ").strip()
                if not choice:
                    continue

                try:
                    chosen_idx = int(choice) - 1
                    chosen_url = ranked[chosen_idx]["url"]
                except (ValueError, IndexError):
                    print("  Invalid choice, skipping.")
                    continue

                # Validate
                print(f"  Validating: {chosen_url}")
                vresult = await validate_url(client, chosen_url)
                print(f"  Status: {vresult['status']} (HTTP {vresult['status_code']})")
                if vresult["final_url"] and vresult["final_url"] != chosen_url:
                    print(f"  Redirected to: {vresult['final_url']}")

                if vresult["status"] in ("working", "redirected"):
                    final_url = vresult["final_url"] or chosen_url
                    confirm = input(f"  Save '{final_url}' to DB? [Y/n]: ").strip()
                    if confirm.lower() in ("", "y", "yes"):
                        await session.execute(
                            update(Scheme).where(Scheme.slug == row.slug).values(
                                official_link=final_url,
                                link_status="working",
                                link_checked_at=datetime.now(),
                            )
                        )
                        await session.commit()
                        print(f"  Saved!")
                    else:
                        print("  Skipped.")
                else:
                    print(f"  Link appears broken ({vresult['error']}). Not saving.")

    await engine.dispose()


# ---------------------------------------------------------------------------
# Mode 2: Batch auto-search
# ---------------------------------------------------------------------------

async def batch_search(limit: int, resume: bool = True):
    """Auto-search and update N schemes without links."""
    engine, session_factory = _get_engine_and_session()

    checkpoint = load_checkpoint() if resume else {
        "completed_slugs": [], "results": {}, "started_at": datetime.now().isoformat(),
    }
    completed_slugs = set(checkpoint.get("completed_slugs", []))
    results = checkpoint.get("results", {})

    stats = {"curated": 0, "api": 0, "duckduckgo": 0, "validated": 0, "failed": 0, "skipped": 0}

    async with session_factory() as session:
        # Fetch schemes without links
        rows = (await session.execute(
            select(Scheme.id, Scheme.slug, Scheme.name)
            .where(Scheme.official_link.is_(None))
            .order_by(Scheme.name)
        )).all()

        schemes = [
            {"id": str(r.id), "slug": r.slug, "name": r.name}
            for r in rows
            if r.slug not in completed_slugs
        ]

        total = min(limit, len(schemes))
        schemes = schemes[:total]

        logger.info("=" * 60)
        logger.info("Batch Link Search")
        logger.info("Schemes to process: %d (of %d without links)", total, len(rows))
        logger.info("Already completed (checkpoint): %d", len(completed_slugs))
        logger.info("=" * 60)

        if not schemes:
            logger.info("Nothing to do!")
            await engine.dispose()
            return

        async with httpx.AsyncClient(
            verify=False, headers={"User-Agent": USER_AGENT},
        ) as client:
            start_time = time.time()

            for i, scheme in enumerate(schemes, 1):
                slug = scheme["slug"]
                name = scheme["name"]
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0

                logger.info(
                    "[%d/%d] (%.1f/min) %s",
                    i, total, rate * 60, name[:60],
                )

                found_url = None
                strategy_used = None

                # ── Strategy 0: Curated links ──
                curated = get_curated_link(slug)
                if curated:
                    logger.info("  [curated] %s", curated)
                    vresult = await validate_url(client, curated)
                    if vresult["status"] in ("working", "redirected"):
                        found_url = vresult["final_url"] or curated
                        strategy_used = "curated"
                        stats["curated"] += 1
                    else:
                        logger.warning("  Curated link broken: %s", vresult["error"])

                # ── Strategy 1: MyScheme Detail API ──
                if not found_url:
                    api_url = await myscheme_api_search(client, slug)
                    if api_url:
                        logger.info("  [api] %s", api_url)
                        vresult = await validate_url(client, api_url)
                        if vresult["status"] in ("working", "redirected"):
                            found_url = vresult["final_url"] or api_url
                            strategy_used = "api"
                            stats["api"] += 1

                # ── Strategy 2: DuckDuckGo search ──
                if not found_url:
                    queries = _build_queries(name)
                    all_urls = []
                    for q in queries:
                        urls = web_search(q)
                        all_urls.extend(urls)
                        if urls:
                            break  # Got results from first query
                        await asyncio.sleep(DDGS_DELAY)

                    ranked = rank_urls(all_urls)

                    if not ranked:
                        logger.info("  No search results")
                    else:
                        # Try top 2 candidates
                        for candidate in ranked[:2]:
                            logger.info(
                                "  [duckduckgo] (%s) %s",
                                candidate["domain_type"], candidate["url"],
                            )
                            vresult = await validate_url(client, candidate["url"])
                            if vresult["status"] in ("working", "redirected"):
                                found_url = vresult["final_url"] or candidate["url"]
                                strategy_used = "duckduckgo"
                                stats["duckduckgo"] += 1
                                break

                # ── Save or skip ──
                if found_url:
                    await session.execute(
                        update(Scheme).where(Scheme.slug == slug).values(
                            official_link=found_url,
                            link_status="working",
                            link_checked_at=datetime.now(),
                        )
                    )
                    stats["validated"] += 1
                    results[slug] = {
                        "url": found_url,
                        "strategy": strategy_used,
                        "status": "saved",
                    }
                    logger.info("  Saved (%s): %s", strategy_used, found_url)
                else:
                    stats["failed"] += 1
                    stats["skipped"] += 1
                    results[slug] = {"status": "no_results"}
                    logger.info("  No valid link found")

                completed_slugs.add(slug)

                # Checkpoint every 10 schemes
                if i % 10 == 0:
                    await session.commit()
                    checkpoint["completed_slugs"] = list(completed_slugs)
                    checkpoint["results"] = results
                    save_checkpoint(checkpoint)
                    logger.info("  [checkpoint saved]")

                # Rate limit between schemes (DuckDuckGo is the bottleneck)
                if strategy_used == "duckduckgo" or not found_url:
                    await asyncio.sleep(DDGS_DELAY)

            # Final commit
            await session.commit()
            checkpoint["completed_slugs"] = list(completed_slugs)
            checkpoint["results"] = results
            save_checkpoint(checkpoint)

    await engine.dispose()

    # Summary
    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 60)
    logger.info("Batch Search Complete!")
    logger.info("Processed:   %d schemes in %.0fs", total, elapsed)
    logger.info("Curated:     %d", stats["curated"])
    logger.info("API:         %d", stats["api"])
    logger.info("DuckDuckGo:  %d", stats["duckduckgo"])
    logger.info("Total saved: %d links", stats["validated"])
    logger.info("No results:  %d", stats["skipped"])
    logger.info("Checkpoint:  %s", CHECKPOINT_FILE)
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Mode 3: Verify existing links (delegates to validate_links.py)
# ---------------------------------------------------------------------------

async def verify_links():
    """Verify all existing links by running the validation pipeline."""
    from app.data.validate_links import validate_links
    await validate_links(update_db=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Manual link search & update tool for government schemes",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--search", type=str, metavar="NAME",
                       help="Interactive search for a scheme by name")
    group.add_argument("--batch", type=int, metavar="N",
                       help="Auto-process N schemes without links")
    group.add_argument("--verify", action="store_true",
                       help="Re-validate all existing links")
    parser.add_argument("--no-resume", action="store_true",
                        help="Ignore checkpoint, start fresh (batch mode)")
    args = parser.parse_args()

    if args.search:
        asyncio.run(search_scheme(args.search))
    elif args.batch:
        asyncio.run(batch_search(args.batch, resume=not args.no_resume))
    elif args.verify:
        asyncio.run(verify_links())


if __name__ == "__main__":
    main()
