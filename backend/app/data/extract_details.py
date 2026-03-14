"""Extract additional scheme details from MyScheme Detail API.

Piggybacks on the detail API to extract structured information like
launch date, helpline, benefit type, and other metadata not in the
search API response.

Usage:
    python -m app.data.extract_details [--batch-size 50] [--limit 10]
"""

import argparse
import asyncio
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Scheme

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

API_BASE = "https://api.myscheme.gov.in/search/v6"
API_KEY = "tYTy5eEhlu9rFjyxuCr7ra7ACp4dv1RH8gWuHTDc"
HEADERS = {
    "x-api-key": API_KEY,
    "Origin": "https://www.myscheme.gov.in",
    "Referer": "https://www.myscheme.gov.in/",
    "User-Agent": "Mozilla/5.0 (compatible; SevanaGPT/1.0)",
}

CHECKPOINT_FILE = Path(__file__).parent / "details_checkpoint.json"
RESULTS_FILE = Path(__file__).parent / "details_results.json"

API_SEMAPHORE = asyncio.Semaphore(10)
API_DELAY = 0.5


def parse_date_flexible(val: str | None) -> date | None:
    """Try to parse a date from various formats."""
    if not val or not isinstance(val, str):
        return None
    val = val.strip()
    for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %B %Y", "%B %d, %Y"]:
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def extract_helpline(detail: dict) -> str | None:
    """Extract helpline/contact info from detail response."""
    for field in ["helpline", "contactNumber", "contact_number", "helplineNumber",
                  "helpline_number", "toll_free", "tollFree"]:
        val = detail.get(field)
        if val and isinstance(val, str) and val.strip():
            return val.strip()[:500]

    # Check nested fields
    fields = detail.get("fields", {})
    for field in ["helpline", "contactNumber", "helplineNumber", "tollFree"]:
        val = fields.get(field)
        if val and isinstance(val, str) and val.strip():
            return val.strip()[:500]

    # Try to find in description/application_process
    for text_field in ["applicationProcess", "application_process"]:
        text = detail.get(text_field, "") or fields.get(text_field, "")
        if text:
            # Look for phone patterns
            phone_match = re.search(r'(?:helpline|toll.?free|contact|call)\s*[:=]?\s*(\d[\d\s\-]{7,})', text, re.IGNORECASE)
            if phone_match:
                return phone_match.group(1).strip()[:500]

    return None


def extract_benefit_type(detail: dict) -> str | None:
    """Extract benefit type (Cash/In Kind/Composite)."""
    for field in ["benefitType", "benefit_type", "typeOfBenefit", "type_of_benefit"]:
        val = detail.get(field) or detail.get("fields", {}).get(field)
        if val and isinstance(val, str):
            val_lower = val.strip().lower()
            if "cash" in val_lower and "kind" in val_lower:
                return "Composite"
            elif "cash" in val_lower:
                return "Cash"
            elif "kind" in val_lower:
                return "In Kind"
            else:
                return val.strip()[:50]
    return None


def extract_extra_details(detail: dict) -> dict:
    """Extract all extra structured details from API response."""
    fields = detail.get("fields", {})
    extras = {}

    # Application mode
    for field in ["applicationMode", "application_mode", "applyMode"]:
        val = detail.get(field) or fields.get(field)
        if val:
            extras["application_mode"] = str(val).strip()
            break

    # DBT flag
    for field in ["isDBT", "is_dbt", "dbtScheme", "dbt_scheme"]:
        val = detail.get(field) or fields.get(field)
        if val is not None:
            extras["is_dbt"] = bool(val)
            break

    # Beneficiary count
    for field in ["beneficiaryCount", "beneficiary_count", "totalBeneficiaries"]:
        val = detail.get(field) or fields.get(field)
        if val:
            extras["beneficiary_count"] = str(val).strip()
            break

    # Budget
    for field in ["budget", "budgetAllocation", "budget_allocation"]:
        val = detail.get(field) or fields.get(field)
        if val:
            extras["budget"] = str(val).strip()
            break

    # Marital status requirement
    for field in ["maritalStatus", "marital_status"]:
        val = detail.get(field) or fields.get(field)
        if val:
            extras["marital_status"] = val if isinstance(val, list) else [str(val).strip()]
            break

    # Occupation requirement
    for field in ["occupation", "occupationType", "occupation_type"]:
        val = detail.get(field) or fields.get(field)
        if val:
            extras["occupation"] = val if isinstance(val, list) else [str(val).strip()]
            break

    # Residence type
    for field in ["residenceType", "residence_type", "areaType", "area_type"]:
        val = detail.get(field) or fields.get(field)
        if val:
            extras["residence_type"] = val if isinstance(val, list) else [str(val).strip()]
            break

    # Scheme introduction date
    for field in ["introducedOn", "introduced_on", "startDate", "start_date"]:
        val = detail.get(field) or fields.get(field)
        if val:
            extras["introduced_on"] = str(val).strip()
            break

    return extras


async def fetch_scheme_detail(client: httpx.AsyncClient, slug: str) -> dict | None:
    """Fetch full scheme detail from MyScheme API."""
    async with API_SEMAPHORE:
        try:
            resp = await client.get(
                f"{API_BASE}/schemeDetail/{slug}",
                headers=HEADERS,
                timeout=15.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", {})
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


async def extract_details(
    batch_size: int = 50,
    limit: int | None = None,
    resume: bool = True,
):
    """Run the details extraction pipeline."""
    logger.info("=" * 60)
    logger.info("Details Extraction Pipeline")
    logger.info(f"Batch size: {batch_size}, Limit: {limit or 'all'}")
    logger.info("=" * 60)

    # Load checkpoint
    if resume and CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            checkpoint = json.load(f)
    else:
        checkpoint = {"completed_slugs": [], "results": {}}

    completed_slugs = set(checkpoint.get("completed_slugs", []))

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Get schemes that need detail extraction
        query = select(Scheme.id, Scheme.slug, Scheme.name).where(
            Scheme.extra_details.is_(None)
        ).order_by(Scheme.slug)

        if limit:
            query = query.limit(limit)

        rows = (await session.execute(query)).all()
        schemes = [{"id": str(r.id), "slug": r.slug, "name": r.name} for r in rows]

        # Filter already completed
        schemes = [s for s in schemes if s["slug"] not in completed_slugs]
        logger.info(f"Schemes to process: {len(schemes)}")

        if not schemes:
            logger.info("Nothing to do!")
            await engine.dispose()
            return

        async with httpx.AsyncClient(verify=False) as client:
            total_updated = 0

            for batch_start in range(0, len(schemes), batch_size):
                batch = schemes[batch_start:batch_start + batch_size]
                batch_num = batch_start // batch_size + 1
                total_batches = (len(schemes) + batch_size - 1) // batch_size

                logger.info(f"Batch {batch_num}/{total_batches} ({len(batch)} schemes)")

                tasks = [fetch_scheme_detail(client, s["slug"]) for s in batch]
                details = await asyncio.gather(*tasks)

                updated = 0
                for scheme, detail in zip(batch, details):
                    if not detail:
                        completed_slugs.add(scheme["slug"])
                        continue

                    # Extract structured data
                    launch_date = parse_date_flexible(
                        detail.get("launchDate") or
                        detail.get("launch_date") or
                        detail.get("fields", {}).get("launchDate")
                    )
                    deadline = parse_date_flexible(
                        detail.get("applicationDeadline") or
                        detail.get("application_deadline") or
                        detail.get("fields", {}).get("applicationDeadline") or
                        detail.get("fields", {}).get("closeDate")
                    )
                    helpline = extract_helpline(detail)
                    benefit_type = extract_benefit_type(detail)
                    extras = extract_extra_details(detail)

                    # Also extract official_link if we got one
                    official_link = None
                    for field in ["officialUrl", "official_url", "schemeUrl", "websiteUrl", "url"]:
                        val = detail.get(field) or detail.get("fields", {}).get(field)
                        if val and isinstance(val, str) and val.startswith("http"):
                            official_link = val.strip()
                            break

                    # Build update values
                    update_vals = {"extra_details": extras if extras else {}}
                    if launch_date:
                        update_vals["launch_date"] = launch_date
                    if deadline:
                        update_vals["application_deadline"] = deadline
                    if helpline:
                        update_vals["helpline"] = helpline
                    if benefit_type:
                        update_vals["benefit_type"] = benefit_type
                    if official_link:
                        # Only update if currently NULL
                        update_vals["official_link"] = official_link

                    await session.execute(
                        update(Scheme).where(Scheme.slug == scheme["slug"]).values(**update_vals)
                    )
                    completed_slugs.add(scheme["slug"])
                    checkpoint["results"][scheme["slug"]] = {
                        "launch_date": str(launch_date) if launch_date else None,
                        "deadline": str(deadline) if deadline else None,
                        "helpline": helpline,
                        "benefit_type": benefit_type,
                        "official_link": official_link,
                        "extras_count": len(extras),
                    }
                    updated += 1

                await session.commit()
                total_updated += updated
                logger.info(f"  Updated {updated}/{len(batch)} schemes in this batch")

                # Save checkpoint
                checkpoint["completed_slugs"] = list(completed_slugs)
                with open(CHECKPOINT_FILE, "w") as f:
                    json.dump(checkpoint, f, indent=2, default=str)

        logger.info(f"\nTotal updated: {total_updated}")

        # Save final results
        with open(RESULTS_FILE, "w") as f:
            json.dump(checkpoint.get("results", {}), f, indent=2, default=str)

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Extract extra details for government schemes")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for processing")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of schemes")
    parser.add_argument("--no-resume", action="store_true", help="Start fresh")
    args = parser.parse_args()

    asyncio.run(extract_details(
        batch_size=args.batch_size,
        limit=args.limit,
        resume=not args.no_resume,
    ))


if __name__ == "__main__":
    main()
