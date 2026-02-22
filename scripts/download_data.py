#!/usr/bin/env python3
"""
Epstein Files — Data Download & Organization Script
====================================================
Downloads publicly available structured datasets related to the Jeffrey Epstein case
and organizes them into categorized folders.

Data Sources:
  1. epsteininvestigation.org — Entities CSV (23K+ people/orgs/locations)
  2. epsteininvestigation.org — Flight Logs CSV (3K+ flight records)
  3. epsteininvestigation.org — Entity Relationships CSV (network graph)
  4. epsteininvestigation.org — Email Metadata CSV
  5. Kaggle (optional) — Persons of Interest & Ranked Documents
  6. Victim/individual images from public archives

Usage:
  pip install -r requirements.txt
  python scripts/download_data.py
"""

import os
import sys
import json
import time
import logging
import requests
import subprocess
from pathlib import Path
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

FOLDERS = {
    "persons_of_interest": DATA_DIR / "persons_of_interest",
    "flight_logs": DATA_DIR / "flight_logs",
    "documents": DATA_DIR / "documents",
    "relationships": DATA_DIR / "relationships",
    "emails": DATA_DIR / "emails",
    "images": DATA_DIR / "images",
    "images_victims": DATA_DIR / "images" / "victims",
    "images_persons": DATA_DIR / "images" / "persons",
    "raw": DATA_DIR / "raw",
    "processed": DATA_DIR / "processed",
}

# Primary data sources — epsteininvestigation.org (no auth required)
ARCHIVE_DOWNLOADS = {
    "entities": {
        "url": "https://www.epsteininvestigation.org/api/download/entities",
        "destination": "persons_of_interest",
        "filename": "entities.csv",
        "description": "Entities & People (23K+ individuals, orgs, locations)",
    },
    "flights": {
        "url": "https://www.epsteininvestigation.org/api/download/flights",
        "destination": "flight_logs",
        "filename": "flights.csv",
        "description": "Flight Logs (3K+ flights with passengers, routes, airports)",
    },
    "relationships": {
        "url": "https://www.epsteininvestigation.org/api/download/relationships",
        "destination": "relationships",
        "filename": "relationships.csv",
        "description": "Entity Relationships (network graph: associates, co-passengers, etc.)",
    },
    "emails": {
        "url": "https://www.epsteininvestigation.org/api/download/emails",
        "destination": "emails",
        "filename": "emails.csv",
        "description": "Email Metadata (dates, senders, recipients, subjects)",
    },
}

# Optional Kaggle datasets
KAGGLE_DATASETS = {
    "persons_of_interest": {
        "dataset": "wilomentena/epstein-list-persons-of-interest",
        "destination": "persons_of_interest",
        "skip_if_exists": "epstein-persons",  # filename prefix to check for
        "description": "Kaggle: Persons of Interest (individuals with flight counts, connections)",
    },
    "ranked_documents": {
        "dataset": "linogova/epstein-ranker-dataset-u-s-house-oversight",
        "destination": "documents",
        "skip_if_exists": "epstein_ranked",  # filename prefix to check for
        "description": "Kaggle: Ranked document metadata from U.S. House Oversight",
    },
    "images": {
        "dataset": "commanderbtc/epstein-files-images",
        "destination": "images_persons",
        "skip_if_exists": None,  # check by image count instead
        "description": "Kaggle: Epstein Files Images (persons, locations, evidence)",
    },
}

# DOJ Dataset metadata
DOJ_DATASETS_META = {
    "datasets": [
        {"id": 1, "name": "Data Set 1", "type": "FBI 302 Reports", "description": "FBI interview summaries and reports"},
        {"id": 2, "name": "Data Set 2", "type": "FBI 302 Reports", "description": "Additional FBI interview summaries"},
        {"id": 3, "name": "Data Set 3", "type": "Police Records", "description": "Palm Beach police records (2005-2008)"},
        {"id": 4, "name": "Data Set 4", "type": "Police Records", "description": "Additional police investigation records"},
        {"id": 5, "name": "Data Set 5", "type": "Legal Correspondence", "description": "Early legal correspondence"},
        {"id": 6, "name": "Data Set 6", "type": "Legal Correspondence", "description": "Additional legal correspondence"},
        {"id": 7, "name": "Data Set 7", "type": "Investigation Records", "description": "Investigation findings"},
        {"id": 8, "name": "Data Set 8", "type": "Investigation Records", "description": "Additional investigation materials"},
        {"id": 9, "name": "Data Set 9", "type": "Communications", "description": "Emails, DOJ correspondence, NPA records"},
        {"id": 10, "name": "Data Set 10", "type": "Visual/Forensic Media", "description": "~180K images and ~2K videos"},
        {"id": 11, "name": "Data Set 11", "type": "Financial & Flight Records", "description": "Ledgers, flight manifests, seizure records"},
        {"id": 12, "name": "Data Set 12", "type": "Supplemental", "description": "Late/supplemental productions"},
    ],
    "source_url": "https://www.justice.gov/epstein",
    "total_pages": "~3,500,000",
}

# ── Logging Setup ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("epstein_downloader")

# ── Helper Functions ───────────────────────────────────────────────────────────


def create_folder_structure():
    """Create all required data folders."""
    log.info("📁 Creating folder structure...")
    for name, path in FOLDERS.items():
        path.mkdir(parents=True, exist_ok=True)
        log.info(f"   ✓ {path.relative_to(BASE_DIR)}")
    log.info("✅ Folder structure ready.\n")


def download_file(url, dest_path, description="file"):
    """Download a file from a URL with progress logging."""
    log.info(f"📥 Downloading {description}...")
    log.info(f"   URL: {url}")

    try:
        response = requests.get(url, stream=True, timeout=120, headers={
            "User-Agent": "Mozilla/5.0 (Research/Academic - Epstein Files Dashboard)"
        })
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)

        size_mb = dest_path.stat().st_size / (1024 * 1024)
        log.info(f"   ✅ Saved: {dest_path.name} ({size_mb:.2f} MB)")
        return True

    except requests.exceptions.HTTPError as e:
        log.error(f"   ❌ HTTP Error: {e}")
        return False
    except requests.exceptions.ConnectionError:
        log.error(f"   ❌ Connection failed")
        return False
    except Exception as e:
        log.error(f"   ❌ Error: {e}")
        return False


def download_archive_sources():
    """Download CSVs from epsteininvestigation.org (primary source, no auth required)."""
    log.info("=" * 60)
    log.info("DOWNLOADING FROM EPSTEIN INVESTIGATION ARCHIVE")
    log.info("(epsteininvestigation.org — No auth required)")
    log.info("=" * 60 + "\n")

    results = {}
    for key, config in ARCHIVE_DOWNLOADS.items():
        dest_path = FOLDERS[config["destination"]] / config["filename"]

        if dest_path.exists() and dest_path.stat().st_size > 100:
            log.info(f"⏩ Skipping {config['filename']} (already exists)")
            results[key] = True
            continue

        success = download_file(config["url"], dest_path, config["description"])
        results[key] = success
        time.sleep(1)  # Respectful rate limiting

    return results


def check_kaggle_cli():
    """Check if kaggle CLI is available and authenticated."""
    try:
        result = subprocess.run(
            ["kaggle", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            log.info(f"   Kaggle CLI found: {result.stdout.strip()}")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False


def download_kaggle_sources():
    """Download optional datasets from Kaggle."""
    log.info("\n" + "=" * 60)
    log.info("DOWNLOADING FROM KAGGLE (Optional Supplements)")
    log.info("=" * 60 + "\n")

    has_kaggle = check_kaggle_cli()

    if not has_kaggle:
        log.warning("⚠️  Kaggle CLI is not installed or not authenticated.")
        log.warning("   This is optional — primary data was already downloaded above.")
        log.warning("")
        log.warning("   To set up Kaggle access for additional data:")
        log.warning("   1. Install: pip install kaggle")
        log.warning("   2. Go to https://www.kaggle.com/settings → API → Create New Token")
        log.warning("   3. Save kaggle.json to ~/.kaggle/kaggle.json")
        log.warning("   4. Run: chmod 600 ~/.kaggle/kaggle.json")
        log.warning("   5. Re-run this script")
        log.warning("")
        return {k: False for k in KAGGLE_DATASETS}

    results = {}
    for key, config in KAGGLE_DATASETS.items():
        dest_path = FOLDERS[config["destination"]]
        skip_prefix = config.get("skip_if_exists", "")
        # Skip only if the Kaggle-specific files are already present
        already_downloaded = any(
            skip_prefix and f.name.startswith(skip_prefix)
            for f in dest_path.iterdir() if f.is_file()
        ) if dest_path.exists() else False
        if already_downloaded:
            log.info(f"⏩ Skipping {key} (already downloaded)")
            results[key] = True
            continue

        try:
            result = subprocess.run(
                ["kaggle", "datasets", "download", "-d", config["dataset"],
                 "-p", str(dest_path), "--unzip"],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                log.info(f"   ✅ {config['description']}")
                results[key] = True
            else:
                log.error(f"   ❌ {key}: {result.stderr.strip()}")
                results[key] = False
        except Exception as e:
            log.error(f"   ❌ {key}: {e}")
            results[key] = False

    return results


def download_images():
    """Download publicly available images from archives."""
    log.info("\n" + "=" * 60)
    log.info("DOWNLOADING IMAGES")
    log.info("=" * 60 + "\n")

    # Try to find images from GitHub repos
    repos_to_check = [
        "https://api.github.com/repos/theelderemo/FULL_EPSTEIN_INDEX/contents/",
    ]

    for repo_url in repos_to_check:
        log.info(f"🖼️  Checking archive for images...")
        try:
            response = requests.get(repo_url, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (Research/Academic)",
                "Accept": "application/vnd.github.v3+json",
            })

            if response.status_code == 200:
                items = response.json()
                # Look for image-containing directories
                img_dirs = [item for item in items if item.get("type") == "dir"
                           and any(k in item["name"].lower() for k in ["image", "photo", "media", "victim"])]

                for img_dir in img_dirs:
                    log.info(f"   📂 Found directory: {img_dir['name']}")
                    sub_resp = requests.get(img_dir["url"], timeout=30, headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "application/vnd.github.v3+json",
                    })
                    if sub_resp.status_code == 200:
                        sub_items = sub_resp.json()
                        images = [i for i in sub_items if i.get("type") == "file"
                                 and i["name"].lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))]
                        log.info(f"      Found {len(images)} images")
                        for img in images[:100]:
                            dest_file = FOLDERS["images_victims"] / img["name"]
                            if not dest_file.exists() and img.get("download_url"):
                                download_file(img["download_url"], dest_file, img["name"])
                                time.sleep(0.5)
            else:
                log.info(f"   Could not access (HTTP {response.status_code})")
        except Exception as e:
            log.warning(f"   ⚠️ Error: {e}")

    log.info(f"\n   ℹ️  For additional images:")
    log.info(f"   • DOJ Data Set 10: https://www.justice.gov/epstein")
    log.info(f"   • Place images in: {FOLDERS['images_victims'].relative_to(BASE_DIR)}")
    log.info(f"   • Re-run process_data.py to index them")


def save_doj_metadata():
    """Save DOJ dataset structure metadata."""
    log.info("\n📋 Saving DOJ dataset metadata...")
    meta_path = FOLDERS["raw"] / "doj_datasets_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(DOJ_DATASETS_META, f, indent=2)
    log.info(f"   ✅ Saved to {meta_path.relative_to(BASE_DIR)}")


def build_image_index():
    """Build an index mapping of available images to persons/records."""
    log.info("\n🔗 Building image index...")

    image_index = {}
    images_dir = FOLDERS["images"]

    for img_path in images_dir.rglob("*"):
        if img_path.is_file() and img_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            name_key = img_path.stem.replace("_", " ").replace("-", " ").strip().title()
            rel_path = str(img_path.relative_to(BASE_DIR))

            if name_key not in image_index:
                image_index[name_key] = []
            image_index[name_key].append({
                "path": rel_path,
                "filename": img_path.name,
                "category": img_path.parent.name,
                "size_bytes": img_path.stat().st_size,
            })

    index_path = FOLDERS["processed"] / "image_index.json"
    with open(index_path, "w") as f:
        json.dump(image_index, f, indent=2)

    log.info(f"   ✅ Indexed {len(image_index)} unique names with images")
    return image_index


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("  EPSTEIN FILES — DATA DOWNLOAD & ORGANIZATION")
    log.info("=" * 60)
    log.info(f"  Base: {BASE_DIR}")
    log.info("=" * 60 + "\n")

    create_folder_structure()

    # Primary downloads (no auth needed)
    archive_results = download_archive_sources()

    # Optional Kaggle supplements
    kaggle_results = download_kaggle_sources()

    # Images
    download_images()

    # Metadata
    save_doj_metadata()

    # Image index
    build_image_index()

    # Summary
    log.info("\n" + "=" * 60)
    log.info("  DOWNLOAD SUMMARY")
    log.info("=" * 60)

    for key, success in archive_results.items():
        log.info(f"   {'✅' if success else '❌'} [Archive] {key}")
    for key, success in kaggle_results.items():
        log.info(f"   {'✅' if success else '⏭️ '} [Kaggle]  {key}")

    archive_ok = all(archive_results.values())
    if archive_ok:
        log.info("\n🎉 Core data downloaded successfully!")
    else:
        log.warning("\n⚠️  Some core downloads failed. Check errors above.")

    log.info(f"\n   Next step: python scripts/process_data.py")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
