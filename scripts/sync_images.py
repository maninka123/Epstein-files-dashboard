#!/usr/bin/env python3
"""
Epstein Files — Image Sync & Organisation Script
=================================================
1. Moves document scan images (EFTA*) from GDrive_Upload → data/images/documents/
2. Downloads person headshots from Wikipedia for POI list
3. Sorts images into:
   - data/images/persons/  — associates, politicians, business figures, others
   - data/images/victims/  — known victims (Virginia Giuffre, Chauntae Davies, etc.)
4. Rebuilds image index in data/processed/image_index.json

Usage:
    python scripts/sync_images.py
"""

import os
import json
import time
import shutil
import logging
import requests
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

IMAGES_DIR       = DATA_DIR / "images"
PERSONS_DIR      = IMAGES_DIR / "persons"
VICTIMS_DIR      = IMAGES_DIR / "victims"
DOCUMENTS_DIR    = IMAGES_DIR / "documents"
GDRIVE_DIR       = PERSONS_DIR / "GDrive_Upload"     # where Kaggle unzipped

POI_JSON         = BASE_DIR / "dashboard" / "data" / "persons_of_interest.json"
IMAGE_INDEX_OUT  = DATA_DIR / "processed" / "image_index.json"

# Known victims with their best Wikipedia search term
# (Wikipedia often has no photo for victims for privacy, so we note what to try)
VICTIM_SEARCH_TERMS = {
    "virginia giuffre": "Virginia Giuffre",
    "virginia roberts": "Virginia Giuffre",
    "chauntae davies": "Chauntae Davies",
    "johanna sjoberg": "Johanna Sjoberg Epstein",
    "sarah ransome": "Sarah Ransome Epstein",
    "alicia arden": "Alicia Arden actress",
    "maria farmer": "Maria Farmer Epstein",
    "annie farmer": "Annie Farmer Epstein",
    "carolyn": None,   # no enough info for Wikipedia lookup
    "jane doe": None,
}

# Set of lowercase name prefixes that flag someone as a victim
VICTIM_NAMES = set(VICTIM_SEARCH_TERMS.keys())

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("image_sync")

# ── Helpers ───────────────────────────────────────────────────────────────────

def is_victim(name: str, category: str, bio: str = "") -> bool:
    """Determine if a person is classified as a victim."""
    name_lower = name.lower()
    if any(v in name_lower for v in VICTIM_NAMES):
        return True
    # Check bio for victim-related keywords
    bio_lower = (bio or "").lower()
    if any(kw in bio_lower for kw in ("victim", "accuser", "trafficked", "survivor", "abuse")):
        return True
    # category 'victim' or 'accuser' if it ever appears
    if category and category.lower() in ("victim", "accuser", "survivor"):
        return True
    return False


def safe_filename(name: str, ext: str = ".jpg") -> str:
    """Convert a name to a safe filename."""
    safe = name.lower().replace(" ", "_").replace("'", "").replace(".", "")
    safe = "".join(c for c in safe if c.isalnum() or c == "_")
    return safe + ext


def fetch_wikipedia_image(name: str, session: requests.Session, alt_name: str = None) -> bytes | None:
    """
    Fetch the main thumbnail image for a Wikipedia article matching 'name'.
    Falls back to opensearch if direct lookup fails.
    Returns image bytes on success, None otherwise.
    """
    search_names = [name]
    if alt_name and alt_name != name:
        search_names.append(alt_name)

    for search_name in search_names:
        try:
            # Direct page lookup by title
            resp = session.get("https://en.wikipedia.org/w/api.php", params={
                "action": "query", "format": "json",
                "prop": "pageimages", "titles": search_name,
                "pithumbsize": 400, "redirects": 1,
            }, timeout=15)
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for page_id, page in pages.items():
                if page_id == "-1":
                    continue
                img_url = page.get("thumbnail", {}).get("source")
                if img_url:
                    img_resp = session.get(img_url, timeout=20)
                    img_resp.raise_for_status()
                    return img_resp.content

            # Fallback: opensearch to find the right article title
            search_resp = session.get("https://en.wikipedia.org/w/api.php", params={
                "action": "opensearch", "format": "json",
                "search": search_name, "limit": 3, "namespace": 0,
            }, timeout=10)
            results = search_resp.json()
            if len(results) > 1 and results[1]:
                for candidate_title in results[1][:3]:
                    img_resp2 = session.get("https://en.wikipedia.org/w/api.php", params={
                        "action": "query", "format": "json",
                        "prop": "pageimages", "titles": candidate_title,
                        "pithumbsize": 400, "redirects": 1,
                    }, timeout=15)
                    img_resp2.raise_for_status()
                    pages2 = img_resp2.json().get("query", {}).get("pages", {})
                    for pid2, page2 in pages2.items():
                        if pid2 != "-1":
                            img_url2 = page2.get("thumbnail", {}).get("source")
                            if img_url2:
                                img_bytes = session.get(img_url2, timeout=20).content
                                return img_bytes
        except Exception as e:
            log.debug(f"   Wikipedia fetch failed for '{search_name}': {e}")
    return None


# ── Step 1: Move document scans out of persons folder ─────────────────────────

def move_document_scans():
    """Move EFTA* document scan images from GDrive_Upload → data/images/documents/"""
    if not GDRIVE_DIR.exists():
        log.info("ℹ️  No GDrive_Upload folder found — skipping document scan move.")
        return 0

    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    scans = list(GDRIVE_DIR.glob("*.jpg")) + list(GDRIVE_DIR.glob("*.png"))

    if not scans:
        log.info(f"ℹ️  No image files in {GDRIVE_DIR.name}")
        return 0

    log.info(f"📦 Moving {len(scans)} document scan images → data/images/documents/")
    moved = 0
    for src in scans:
        dest = DOCUMENTS_DIR / src.name
        if not dest.exists():
            shutil.move(str(src), str(dest))
            moved += 1

    # Remove GDrive_Upload if now empty
    remaining = list(GDRIVE_DIR.iterdir())
    if not remaining:
        GDRIVE_DIR.rmdir()
        log.info("   🗑️  Removed empty GDrive_Upload folder")

    log.info(f"   ✅ Moved {moved} scans to data/images/documents/")
    return moved


# ── Step 2: Download person headshots from Wikipedia ─────────────────────────

def download_person_images(max_persons: int = 150):
    """Download Wikipedia headshots for top persons of interest."""
    if not POI_JSON.exists():
        log.warning("⚠️  persons_of_interest.json not found — run process_data.py first")
        return

    PERSONS_DIR.mkdir(parents=True, exist_ok=True)
    VICTIMS_DIR.mkdir(parents=True, exist_ok=True)

    persons = json.loads(POI_JSON.read_text())[:max_persons]
    log.info(f"🖼️  Downloading Wikipedia headshots for up to {len(persons)} persons...")

    session = requests.Session()
    session.headers["User-Agent"] = "EpsteinFilesDashboard/1.0 (research; educational)"

    downloaded = 0
    skipped = 0
    failed = 0

    for i, person in enumerate(persons):
        name = person.get("name", "").strip()
        category = person.get("category", "")
        bio = person.get("bio", "")
        if not name:
            continue

        # Decide destination folder
        victim = is_victim(name, category, bio)
        target_dir = VICTIMS_DIR if victim else PERSONS_DIR
        dest_file = target_dir / safe_filename(name)

        if dest_file.exists():
            skipped += 1
            continue

        label = "victims" if victim else "persons"
        log.info(f"   [{i+1}/{len(persons)}] {name} → {label}/")

        # Use alternate search term for victims where available
        alt_name = None
        if victim:
            for vkey, valt in VICTIM_SEARCH_TERMS.items():
                if vkey in name.lower() and valt:
                    alt_name = valt
                    break

        img_bytes = fetch_wikipedia_image(name, session, alt_name=alt_name)

        if img_bytes:
            dest_file.write_bytes(img_bytes)
            downloaded += 1
            log.info(f"      ✅ Saved ({len(img_bytes)//1024} KB)")
        else:
            failed += 1
            log.warning(f"      ⚠️  No image found on Wikipedia")

        time.sleep(0.3)  # Respectful rate limiting

    log.info(f"\n   📸 Downloaded: {downloaded} | Skipped (cached): {skipped} | Not found: {failed}")


# ── Step 3: Rebuild image index ───────────────────────────────────────────────

def build_image_index():
    """Scan all image subfolders and build name→image mapping."""
    log.info("\n🔗 Rebuilding image index...")
    IMAGE_INDEX_OUT.parent.mkdir(parents=True, exist_ok=True)

    image_index = {}
    for img_path in IMAGES_DIR.rglob("*"):
        if not img_path.is_file():
            continue
        if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            continue
        # Skip document scans (not person photos)
        if img_path.parent.name == "documents":
            continue

        name_key = img_path.stem.replace("_", " ").replace("-", " ").strip().title()
        rel_path = str(img_path.relative_to(BASE_DIR))
        category = img_path.parent.name  # 'persons' or 'victims'

        if name_key not in image_index:
            image_index[name_key] = []
        image_index[name_key].append({
            "path": rel_path,
            "filename": img_path.name,
            "category": category,
            "size_bytes": img_path.stat().st_size,
        })

    IMAGE_INDEX_OUT.write_text(json.dumps(image_index, indent=2))
    log.info(f"   ✅ Indexed {len(image_index)} persons with images")

    # Stats
    persons_count = sum(1 for v in image_index.values() if any(i["category"] == "persons" for i in v))
    victims_count = sum(1 for v in image_index.values() if any(i["category"] == "victims" for i in v))
    log.info(f"   👤 Persons: {persons_count} | 💔 Victims: {victims_count}")

    return image_index


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("  EPSTEIN FILES — IMAGE SYNC & ORGANISATION")
    log.info("=" * 60)

    # Step 1: Move document scan images out of the persons folder
    log.info("\n📦 Step 1: Organise document scans")
    move_document_scans()

    # Step 2: Download person photos from Wikipedia
    log.info("\n🌐 Step 2: Download person headshots (Wikipedia)")
    download_person_images(max_persons=150)

    # Step 3: Rebuild image index
    log.info("\n🔗 Step 3: Rebuild image index")
    build_image_index()

    log.info("\n" + "=" * 60)
    log.info("  DONE — Re-run process_data.py to update dashboard JSON")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
