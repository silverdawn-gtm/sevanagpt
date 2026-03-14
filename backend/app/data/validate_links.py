"""Standalone link validator for government scheme official links.

Validates all official_link values in the database and classifies them as:
- working (2xx)
- broken (4xx/5xx)
- redirected (3xx final URL differs)
- timeout
- ssl_error
- dns_error

Usage:
    python -m app.data.validate_links [--update-db] [--limit 100] [--concurrency 20]
"""

import argparse
import asyncio
import csv
import json
import logging
import ssl
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Scheme

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 30.0
MAX_REDIRECTS = 5
MAX_RETRIES = 3
RETRY_BACKOFF = [1.0, 2.0, 4.0]


async def validate_link(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
    slug: str,
) -> dict:
    """Validate a single URL and return classification result."""
    result = {
        "slug": slug,
        "original_url": url,
        "status": "unknown",
        "status_code": None,
        "final_url": None,
        "error": None,
        "response_time_ms": None,
        "checked_at": datetime.now().isoformat(),
    }

    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                start = asyncio.get_event_loop().time()

                # Try HEAD first
                try:
                    resp = await client.head(
                        url,
                        follow_redirects=True,
                        timeout=httpx.Timeout(
                            connect=CONNECT_TIMEOUT,
                            read=READ_TIMEOUT,
                            write=10.0,
                            pool=10.0,
                        ),
                    )
                except httpx.HTTPStatusError:
                    resp = None

                # If HEAD returns 405 or fails, try GET
                if resp is None or resp.status_code == 405:
                    resp = await client.get(
                        url,
                        follow_redirects=True,
                        timeout=httpx.Timeout(
                            connect=CONNECT_TIMEOUT,
                            read=READ_TIMEOUT,
                            write=10.0,
                            pool=10.0,
                        ),
                    )

                elapsed = (asyncio.get_event_loop().time() - start) * 1000
                result["status_code"] = resp.status_code
                result["final_url"] = str(resp.url)
                result["response_time_ms"] = round(elapsed)

                if 200 <= resp.status_code < 300:
                    if str(resp.url) != url:
                        result["status"] = "redirected"
                    else:
                        result["status"] = "working"
                elif 400 <= resp.status_code < 500:
                    result["status"] = "broken"
                    result["error"] = f"HTTP {resp.status_code}"
                elif 500 <= resp.status_code < 600:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_BACKOFF[attempt])
                        continue
                    result["status"] = "broken"
                    result["error"] = f"HTTP {resp.status_code}"
                elif resp.status_code == 429:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_BACKOFF[attempt] * 2)
                        continue
                    result["status"] = "broken"
                    result["error"] = "Rate limited"
                else:
                    result["status"] = "unknown"
                    result["error"] = f"HTTP {resp.status_code}"

                break  # Success - no need to retry

            except httpx.TimeoutException:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_BACKOFF[attempt])
                    continue
                result["status"] = "timeout"
                result["error"] = "Connection/read timeout"
                break

            except ssl.SSLError as e:
                result["status"] = "ssl_error"
                result["error"] = str(e)[:200]
                break

            except httpx.ConnectError as e:
                err_str = str(e).lower()
                if "name resolution" in err_str or "dns" in err_str or "getaddrinfo" in err_str:
                    result["status"] = "dns_error"
                    result["error"] = "DNS resolution failed"
                else:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_BACKOFF[attempt])
                        continue
                    result["status"] = "broken"
                    result["error"] = str(e)[:200]
                break

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_BACKOFF[attempt])
                    continue
                result["status"] = "broken"
                result["error"] = str(e)[:200]
                break

    return result


def write_reports(results: list[dict]):
    """Write validation reports to files."""
    # JSON report
    json_path = REPORTS_DIR / "validation_report.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"JSON report: {json_path}")

    # CSV report
    csv_path = REPORTS_DIR / "validation_report.csv"
    if results:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        logger.info(f"CSV report: {csv_path}")

    # Summary report
    summary_path = REPORTS_DIR / "validation_summary.txt"
    status_counts = {}
    for r in results:
        s = r["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    with open(summary_path, "w") as f:
        f.write("Link Validation Summary\n")
        f.write(f"{'=' * 40}\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write(f"Total links checked: {len(results)}\n\n")
        f.write("Status breakdown:\n")
        for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
            pct = count / len(results) * 100
            f.write(f"  {status:15s}: {count:5d} ({pct:5.1f}%)\n")

        f.write(f"\nBroken links:\n")
        broken = [r for r in results if r["status"] in ("broken", "dns_error", "ssl_error")]
        for r in broken[:50]:  # Top 50
            f.write(f"  [{r['status']}] {r['slug']}: {r['original_url']} - {r.get('error', '')}\n")

        if len(broken) > 50:
            f.write(f"  ... and {len(broken) - 50} more\n")

        f.write(f"\nRedirected links:\n")
        redirected = [r for r in results if r["status"] == "redirected"]
        for r in redirected[:20]:
            f.write(f"  {r['slug']}: {r['original_url']} -> {r['final_url']}\n")

    logger.info(f"Summary report: {summary_path}")


async def validate_links(
    update_db: bool = False,
    limit: int | None = None,
    concurrency: int = 20,
):
    """Run link validation on all schemes with official links."""
    logger.info("=" * 60)
    logger.info("Link Validation Pipeline")
    logger.info(f"Update DB: {update_db}, Concurrency: {concurrency}")
    logger.info("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Get all schemes with official links
        query = select(Scheme.id, Scheme.slug, Scheme.official_link).where(
            Scheme.official_link.isnot(None),
            Scheme.official_link != "",
        )

        if limit:
            query = query.limit(limit)

        rows = (await session.execute(query)).all()
        logger.info(f"Schemes with links to validate: {len(rows)}")

        if not rows:
            logger.info("Nothing to validate!")
            await engine.dispose()
            return

        semaphore = asyncio.Semaphore(concurrency)

        async with httpx.AsyncClient(
            verify=False,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
        ) as client:
            tasks = [
                validate_link(client, semaphore, row.official_link, row.slug)
                for row in rows
            ]

            # Process with progress
            results = []
            batch_size = 100
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i + batch_size]
                batch_results = await asyncio.gather(*batch)
                results.extend(batch_results)
                logger.info(f"Validated {len(results)}/{len(tasks)} links...")

        # Write reports
        write_reports(results)

        # Update DB if requested
        if update_db:
            logger.info("\nUpdating database...")
            updated = 0
            for r in results:
                update_vals = {
                    "link_status": r["status"],
                    "link_checked_at": datetime.now(),
                }

                # Update URL for redirected links
                if r["status"] == "redirected" and r["final_url"]:
                    update_vals["official_link"] = r["final_url"]

                await session.execute(
                    update(Scheme).where(Scheme.slug == r["slug"]).values(**update_vals)
                )
                updated += 1

            await session.commit()
            logger.info(f"Updated {updated} schemes in database")

    await engine.dispose()

    # Print summary
    status_counts = {}
    for r in results:
        s = r["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    logger.info("\n" + "=" * 60)
    logger.info("Validation Complete!")
    logger.info(f"Total checked: {len(results)}")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {status}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Validate official links for government schemes")
    parser.add_argument("--update-db", action="store_true", help="Update DB with validation results")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of links to validate")
    parser.add_argument("--concurrency", type=int, default=20, help="Max concurrent requests")
    args = parser.parse_args()

    asyncio.run(validate_links(
        update_db=args.update_db,
        limit=args.limit,
        concurrency=args.concurrency,
    ))


if __name__ == "__main__":
    main()
