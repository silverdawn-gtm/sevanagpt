"""Update embedded data files with extracted links and details.

Reads extraction results and updates the Python source files
(ingest_hf.py, state_schemes_data.py) with official links and extra fields.

Usage:
    python -m app.data.update_embedded_data [--dry-run] [--source extraction_results.json]
"""

import argparse
import ast
import json
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent
RESULTS_FILE = DATA_DIR / "extraction_results.json"
DETAILS_FILE = DATA_DIR / "details_results.json"


def load_extraction_results(path: Path | None = None) -> dict:
    """Load extraction results from JSON file."""
    path = path or RESULTS_FILE
    if not path.exists():
        logger.warning(f"Results file not found: {path}")
        return {}
    with open(path) as f:
        return json.load(f)


def load_details_results(path: Path | None = None) -> dict:
    """Load details results from JSON file."""
    path = path or DETAILS_FILE
    if not path.exists():
        logger.warning(f"Details file not found: {path}")
        return {}
    with open(path) as f:
        return json.load(f)


def slugify_name(name: str) -> str:
    """Simple slugify for matching purposes."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def build_slug_to_link_map(results: dict) -> dict[str, str]:
    """Build a mapping of scheme slug to official link."""
    mapping = {}
    for slug, data in results.items():
        link = data.get("official_link")
        if link:
            mapping[slug] = link
    return mapping


def update_python_data_file(
    file_path: Path,
    link_map: dict[str, str],
    details_map: dict,
    dry_run: bool = False,
) -> int:
    """Update a Python data file with official links.

    Finds scheme dictionaries in the source and adds/updates official_link.
    Returns count of schemes updated.
    """
    with open(file_path) as f:
        content = f.read()

    original_content = content
    updated = 0

    # Parse schemes by finding "name": "..." patterns and matching slugs
    # We use regex to find scheme dict boundaries and insert/update official_link
    name_pattern = re.compile(r'"name":\s*"([^"]+)"')

    for match in name_pattern.finditer(content):
        name = match.group(1)
        slug = slugify_name(name)

        link = link_map.get(slug)
        if not link:
            # Try fuzzy match
            for map_slug, map_link in link_map.items():
                if slug in map_slug or map_slug in slug:
                    link = map_link
                    break

        if not link:
            continue

        # Find the dict this name belongs to - look for the enclosing { ... }
        # Find the next closing pattern after this name
        name_pos = match.start()

        # Check if official_link already exists in this dict entry
        # Look ahead for the next scheme entry or end of list
        next_name = name_pattern.search(content, match.end())
        end_pos = next_name.start() if next_name else len(content)
        dict_slice = content[name_pos:end_pos]

        if '"official_link"' in dict_slice:
            # Update existing official_link
            old_link_match = re.search(r'"official_link":\s*"[^"]*"', dict_slice)
            if old_link_match:
                old = dict_slice[old_link_match.start():old_link_match.end()]
                new = f'"official_link": "{link}"'
                if old != new:
                    content = content[:name_pos + old_link_match.start()] + new + content[name_pos + old_link_match.end():]
                    updated += 1
        elif '"official_link": None' in dict_slice:
            # Replace None with actual link
            content = content.replace(
                '"official_link": None',
                f'"official_link": "{link}"',
                1,
            )
            updated += 1
        else:
            # Insert official_link after the "name" line
            # Find the line end after name
            line_end = content.index('\n', match.end())
            indent = "            "  # 12 spaces to match existing format
            insert_text = f'\n{indent}"official_link": "{link}",'
            # Insert after the "name" line's comma
            content = content[:line_end] + insert_text + content[line_end:]
            updated += 1
            # Adjust positions for subsequent matches
            # (we're modifying content in place so this is approximate)

    if content != original_content:
        if dry_run:
            logger.info(f"[DRY RUN] Would update {updated} schemes in {file_path.name}")
            # Write preview to a temp file
            preview_path = file_path.with_suffix('.preview.py')
            with open(preview_path, 'w') as f:
                f.write(content)
            logger.info(f"Preview written to: {preview_path}")
        else:
            with open(file_path, 'w') as f:
                f.write(content)
            logger.info(f"Updated {updated} schemes in {file_path.name}")
    else:
        logger.info(f"No changes needed in {file_path.name}")

    return updated


def update_embedded_data(
    results_path: Path | None = None,
    details_path: Path | None = None,
    dry_run: bool = False,
):
    """Main entry point to update embedded data files."""
    logger.info("=" * 60)
    logger.info("Update Embedded Data Files")
    logger.info(f"Dry run: {dry_run}")
    logger.info("=" * 60)

    # Load results
    link_results = load_extraction_results(results_path)
    details_results = load_details_results(details_path)

    if not link_results and not details_results:
        logger.warning("No results to apply. Run extract_links.py and/or extract_details.py first.")
        return

    link_map = build_slug_to_link_map(link_results)
    logger.info(f"Link mappings available: {len(link_map)}")

    # Update ingest_hf.py
    hf_file = DATA_DIR / "ingest_hf.py"
    if hf_file.exists():
        count = update_python_data_file(hf_file, link_map, details_results, dry_run)
        logger.info(f"ingest_hf.py: {count} schemes updated")

    # Update state_schemes_data.py
    state_file = DATA_DIR / "state_schemes_data.py"
    if state_file.exists():
        count = update_python_data_file(state_file, link_map, details_results, dry_run)
        logger.info(f"state_schemes_data.py: {count} schemes updated")

    logger.info("\nDone!")
    if dry_run:
        logger.info("This was a dry run. No files were modified. Check .preview.py files for changes.")


def main():
    parser = argparse.ArgumentParser(description="Update embedded data files with extracted links")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying files")
    parser.add_argument("--source", type=Path, default=None, help="Path to extraction results JSON")
    parser.add_argument("--details", type=Path, default=None, help="Path to details results JSON")
    args = parser.parse_args()

    update_embedded_data(
        results_path=args.source,
        details_path=args.details,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
