#!/usr/bin/env python3
"""
Epstein Files — Data Processing & JSON Export Script
=====================================================
Reads downloaded CSV data from epsteininvestigation.org and Kaggle,
cleans/normalizes it, and exports JSON files for the web dashboard.

Usage:
  python scripts/process_data.py
"""

import os
import json
import csv
import re
import logging
from pathlib import Path
from collections import Counter, defaultdict

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DASHBOARD_DATA_DIR = BASE_DIR / "dashboard" / "data"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("epstein_processor")


def ensure_dirs():
    DASHBOARD_DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_csv_safe(filepath):
    """Read a CSV file with error handling."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        log.error(f"Error reading {filepath}: {e}")
        return []


def load_image_index():
    index_path = DATA_DIR / "processed" / "image_index.json"
    if index_path.exists():
        with open(index_path, "r") as f:
            return json.load(f)
    return {}


# ── Processing Functions ───────────────────────────────────────────────────────


def process_entities(image_index):
    """Process entities.csv from epsteininvestigation.org."""
    log.info("👤 Processing Entities data...")

    filepath = DATA_DIR / "persons_of_interest" / "entities.csv"
    if not filepath.exists():
        log.warning("   ⚠️ entities.csv not found")
        return None

    records = read_csv_safe(filepath)
    log.info(f"   📄 entities.csv: {len(records)} records")

    processed = []
    for record in records:
        name = (record.get("name", "") or "").strip()
        if not name:
            continue

        entity_type = (record.get("entity_type", "") or "").strip()
        role = (record.get("role_description", "") or "").strip()
        doc_count = 0
        flight_count = 0
        email_count = 0

        try:
            doc_count = int(record.get("document_count", 0) or 0)
        except (ValueError, TypeError):
            pass
        try:
            flight_count = int(record.get("flight_count", 0) or 0)
        except (ValueError, TypeError):
            pass
        try:
            email_count = int(record.get("email_count", 0) or 0)
        except (ValueError, TypeError):
            pass

        # Match images
        name_title = name.title()
        images = image_index.get(name_title, [])
        if not images:
            for key in image_index:
                name_parts = name_title.split()
                if len(name_parts) >= 2 and all(part in key for part in name_parts[:2] if len(part) > 2):
                    images = image_index[key]
                    break

        entry = {
            "name": name,
            "entity_type": entity_type,
            "role_description": role,
            "documents": doc_count,
            "flights": flight_count,
            "emails": email_count,
            "slug": (record.get("slug", "") or "").strip(),
            "images": images,
        }
        processed.append(entry)

    processed.sort(key=lambda x: (x["flights"], x["documents"]), reverse=True)
    log.info(f"   ✅ Processed {len(processed)} entities")
    return processed


def process_persons_kaggle(image_index):
    """Process Kaggle Persons of Interest dataset (supplement)."""
    # Look for any non-entities CSV in persons_of_interest/
    folder = DATA_DIR / "persons_of_interest"
    csv_files = [f for f in folder.glob("*.csv") if f.name != "entities.csv"]

    if not csv_files:
        return None

    log.info("👤 Processing Kaggle Persons of Interest (supplement)...")
    all_records = []
    for csv_file in csv_files:
        records = read_csv_safe(csv_file)
        log.info(f"   📄 {csv_file.name}: {len(records)} records")
        all_records.extend(records)

    processed = []
    for record in all_records:
        # Support both field naming conventions
        name = (record.get("Name", "") or record.get("Persons of Interest", "") or "").strip()
        if not name:
            continue

        flights = 0
        documents = 0
        connections = 0
        bio = ""
        try:
            # Kaggle CSV uses 'Flights', older format used 'Number of flights'
            flights = int(record.get("Flights", record.get("Number of flights", 0)) or 0)
        except (ValueError, TypeError):
            pass
        try:
            # Kaggle CSV uses 'Documents', older format used 'Number of documents'
            documents = int(record.get("Documents", record.get("Number of documents", 0)) or 0)
        except (ValueError, TypeError):
            pass
        try:
            connections = int(record.get("Connections", 0) or 0)
        except (ValueError, TypeError):
            pass

        bio = (record.get("Bio", "") or "").strip()
        in_bb = (record.get("In Black Book", "") or "").strip().lower() in ("yes", "true", "1", "y")
        nationality = (record.get("Nationality", "") or "").strip() or "Unknown"

        # Match images
        name_title = name.title()
        images = image_index.get(name_title, [])

        processed.append({
            "name": name,
            "bio": bio,
            "flights": flights,
            "documents": documents,
            "connections": connections,
            "in_black_book": in_bb,
            "nationality": nationality,
            "category": (record.get("Category", "") or "").strip() or "Unknown",
            "images": images,
        })

    processed.sort(key=lambda x: (x["connections"], x["flights"], x["documents"]), reverse=True)
    log.info(f"   ✅ Processed {len(processed)} kaggle persons")
    return processed


def count_connections_from_relationships(relationships_data):
    """Count how many unique connections each entity has from relationships CSV."""
    conn_counts = Counter()
    if not relationships_data:
        return conn_counts
    rel_links, _ = relationships_data
    for link in rel_links:
        src = link["source"]
        tgt = link["target"]
        conn_counts[src] += 1
        conn_counts[tgt] += 1
    return conn_counts


def merge_persons(entities_data, kaggle_data, connection_counts=None):
    """Merge entity data with Kaggle POI data, enriching with connection counts."""
    if connection_counts is None:
        connection_counts = {}

    if not entities_data:
        if kaggle_data:
            for p in kaggle_data:
                p["connections"] = max(p.get("connections", 0), connection_counts.get(p["name"], 0))
            return kaggle_data
        return []

    if not kaggle_data:
        # Convert entities to persons format
        persons = []
        for e in entities_data:
            persons.append({
                "name": e["name"],
                "entity_type": e.get("entity_type", ""),
                "role_description": e.get("role_description", ""),
                "flights": e.get("flights", 0),
                "documents": e.get("documents", 0),
                "emails": e.get("emails", 0),
                "connections": connection_counts.get(e["name"], 0),
                "in_black_book": False,
                "nationality": "Unknown",
                "category": e.get("entity_type", "Unknown"),
                "slug": e.get("slug", ""),
                "images": e.get("images", []),
            })
        return persons

    # Merge: entities as base, enrich with Kaggle data
    kaggle_map = {p["name"].lower(): p for p in kaggle_data}
    merged = []
    seen = set()

    for e in entities_data:
        name_lower = e["name"].lower()
        seen.add(name_lower)
        kaggle_match = kaggle_map.get(name_lower, {})
        conn = max(connection_counts.get(e["name"], 0), kaggle_match.get("connections", 0))

        merged.append({
            "name": e["name"],
            "entity_type": e.get("entity_type", ""),
            "role_description": e.get("role_description", ""),
            "flights": max(e.get("flights", 0), kaggle_match.get("flights", 0)),
            "documents": max(e.get("documents", 0), kaggle_match.get("documents", 0)),
            "emails": e.get("emails", 0),
            "connections": conn,
            "in_black_book": kaggle_match.get("in_black_book", False),
            "nationality": kaggle_match.get("nationality", "Unknown"),
            "category": kaggle_match.get("category", e.get("entity_type", "Unknown")),
            "slug": e.get("slug", ""),
            "images": e.get("images", []) or kaggle_match.get("images", []),
        })

    # Add Kaggle-only entries
    for p in kaggle_data:
        if p["name"].lower() not in seen:
            p["connections"] = max(p.get("connections", 0), connection_counts.get(p["name"], 0))
            merged.append(p)

    merged.sort(key=lambda x: (x.get("flights", 0), x.get("documents", 0)), reverse=True)
    return merged


def process_flights():
    """Process flights.csv from epsteininvestigation.org."""
    log.info("✈️  Processing Flight Logs...")

    filepath = DATA_DIR / "flight_logs" / "flights.csv"
    if not filepath.exists():
        log.warning("   ⚠️ flights.csv not found")
        return None

    records = read_csv_safe(filepath)
    log.info(f"   📄 flights.csv: {len(records)} records")

    processed = []
    for record in records:
        date = (record.get("flight_date", "") or "").strip()
        aircraft = (record.get("aircraft_tail_number", "") or record.get("aircraft_id", "") or "").strip()
        pilot = (record.get("pilot_name", "") or record.get("pilot", "") or "").strip()
        dep_code = (record.get("departure_airport_code", "") or "").strip()
        dep_name = (record.get("departure_airport", "") or "").strip()
        arr_code = (record.get("arrival_airport_code", "") or "").strip()
        arr_name = (record.get("arrival_airport", "") or "").strip()

        # Passengers — may be a list or comma-separated
        pax_raw = record.get("passenger_names", "") or ""
        if isinstance(pax_raw, str):
            pax_raw = pax_raw.strip().strip("[]\"'")
            passengers = pax_raw
        else:
            passengers = str(pax_raw)

        # Construct display strings
        departure = f"{dep_name} ({dep_code})" if dep_code and dep_name else (dep_name or dep_code or "")
        arrival = f"{arr_name} ({arr_code})" if arr_code and arr_name else (arr_name or arr_code or "")

        # Parse year
        year = ""
        if date:
            ym = re.search(r"(19|20)\d{2}", date)
            if ym:
                year = ym.group()

        entry = {
            "date": date,
            "year": year,
            "departure": departure,
            "departure_code": dep_code,
            "arrival": arrival,
            "arrival_code": arr_code,
            "aircraft": aircraft,
            "pilot": pilot,
            "passengers": passengers,
        }
        processed.append(entry)

    processed.sort(key=lambda x: x.get("date", ""))
    log.info(f"   ✅ Processed {len(processed)} flight records")
    return processed


def process_relationships():
    """Process relationships.csv for network graph data."""
    log.info("🕸️  Processing Relationships...")

    filepath = DATA_DIR / "relationships" / "relationships.csv"
    if not filepath.exists():
        log.warning("   ⚠️ relationships.csv not found")
        return None

    records = read_csv_safe(filepath)
    log.info(f"   📄 relationships.csv: {len(records)} records")

    links = []
    node_set = set()

    for record in records:
        entity_a = (record.get("entity_a", "") or "").strip()
        entity_b = (record.get("entity_b", "") or "").strip()
        rel_type = (record.get("relationship_type", "") or "").strip()
        strength = 1
        try:
            strength = int(record.get("strength", 1) or 1)
        except (ValueError, TypeError):
            try:
                strength = float(record.get("strength", 1) or 1)
                strength = int(round(strength))
            except:
                strength = 1

        if entity_a and entity_b:
            links.append({
                "source": entity_a,
                "target": entity_b,
                "type": rel_type,
                "weight": strength,
            })
            node_set.add(entity_a)
            node_set.add(entity_b)

    log.info(f"   ✅ {len(links)} relationships, {len(node_set)} unique nodes")
    return links, node_set


def process_documents():
    """Process document metadata from Kaggle ranked dataset (JSONL or CSV)."""
    import json as _json
    log.info("📄 Processing Document Metadata...")

    folder = DATA_DIR / "documents"
    all_records = []

    # Load JSONL files (primary: Kaggle ranked dataset)
    jsonl_files = sorted(folder.glob("*.jsonl"))
    if jsonl_files:
        log.info(f"   Found {len(jsonl_files)} JSONL file(s)")
        for jf in jsonl_files:
            try:
                with open(jf, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            all_records.append(_json.loads(line))
            except Exception as e:
                log.warning(f"   ⚠️ Could not read {jf.name}: {e}")
        log.info(f"   📄 Loaded {len(all_records)} JSONL records")

    # Load CSV files as fallback
    csv_files = list(folder.glob("*.csv"))
    for csv_file in csv_files:
        records = read_csv_safe(csv_file)
        log.info(f"   📄 {csv_file.name}: {len(records)} records")
        all_records.extend(records)

    if not all_records:
        log.warning("   ⚠️ No document files found in data/documents/")
        return None

    def parse_list(val):
        if not val:
            return []
        if isinstance(val, list):
            return [str(v).strip() for v in val if str(v).strip()]
        val = str(val).strip("[]'\"")
        return [x.strip().strip("'\"") for x in val.split(",") if x.strip()]

    processed = []
    for record in all_records:
        filename = (record.get("filename", "") or record.get("Filename", "") or "").strip()
        headline = (record.get("headline", "") or record.get("title", "") or "").strip()
        if not filename and not headline:
            continue

        importance = 0
        try:
            importance = int(record.get("importance_score", 0) or 0)
        except (ValueError, TypeError):
            pass

        reason = (record.get("reason", "") or "").strip()

        entry = {
            "filename": filename,
            "headline": headline,
            "importance_score": importance,
            "reason": reason,
            "tags": parse_list(record.get("tags", [])),
            "power_mentions": parse_list(record.get("power_mentions", [])),
            "agency_involvement": parse_list(record.get("agency_involvement", [])),
            "lead_types": parse_list(record.get("lead_types", [])),
            "key_insights": parse_list(record.get("key_insights", [])),
        }
        processed.append(entry)

    processed.sort(key=lambda x: x["importance_score"], reverse=True)
    log.info(f"   ✅ Processed {len(processed)} documents")
    return processed


def process_emails():
    """Process email metadata CSV."""
    log.info("📧 Processing Email Metadata...")

    filepath = DATA_DIR / "emails" / "emails.csv"
    if not filepath.exists():
        log.warning("   ⚠️ emails.csv not found")
        return None

    records = read_csv_safe(filepath)
    log.info(f"   📄 emails.csv: {len(records)} records")

    processed = []
    for record in records:
        entry = {
            "date": (record.get("date", "") or "").strip(),
            "from": (record.get("from", "") or "").strip(),
            "to": (record.get("to", "") or "").strip(),
            "subject": (record.get("subject", "") or "").strip(),
            "slug": (record.get("slug", "") or "").strip(),
        }
        if entry["from"] or entry["to"]:
            processed.append(entry)

    processed.sort(key=lambda x: x.get("date", ""))
    log.info(f"   ✅ Processed {len(processed)} emails")
    return processed


def build_network(persons_data, relationships_data, flight_data):
    """Build network graph data from relationships and flight co-occurrences."""
    log.info("🕸️  Building Network Graph...")

    nodes = {}
    links = []

    # Add persons as nodes
    if persons_data:
        for p in persons_data[:300]:
            name = p["name"]
            if name not in nodes:
                nodes[name] = {
                    "id": name,
                    "group": p.get("category", p.get("entity_type", "Unknown")),
                    "flights": p.get("flights", 0),
                    "documents": p.get("documents", 0),
                    "connections": p.get("connections", 0),
                    "in_black_book": p.get("in_black_book", False),
                    "nationality": p.get("nationality", "Unknown"),
                    "images": p.get("images", []),
                }

    # Use relationships data for links
    if relationships_data:
        rel_links, rel_nodes = relationships_data
        for link in rel_links[:1000]:
            src = link["source"]
            tgt = link["target"]

            # Add nodes if not present
            for n in [src, tgt]:
                if n not in nodes:
                    nodes[n] = {
                        "id": n,
                        "group": "Relationship",
                        "flights": 0, "documents": 0, "connections": 0,
                    }

            links.append(link)

    # Build co-occurrence from flight passengers
    if flight_data and not relationships_data:
        co_occurrence = Counter()
        for flight in flight_data:
            pax_str = flight.get("passengers", "")
            if pax_str:
                pax = re.split(r"[,;/&]+", pax_str)
                pax = [p.strip().title() for p in pax if p.strip() and len(p.strip()) > 2]
                for i, p1 in enumerate(pax):
                    for p2 in pax[i + 1:]:
                        if p1 != p2:
                            pair = tuple(sorted([p1, p2]))
                            co_occurrence[pair] += 1
                            for p in [p1, p2]:
                                if p not in nodes:
                                    nodes[p] = {
                                        "id": p, "group": "Flight Passenger",
                                        "flights": 0, "documents": 0, "connections": 0,
                                    }

        for (src, tgt), weight in co_occurrence.most_common(500):
            links.append({"source": src, "target": tgt, "weight": weight, "type": "co-passenger"})

    network = {"nodes": list(nodes.values()), "links": links}
    log.info(f"   ✅ Network: {len(nodes)} nodes, {len(links)} links")
    return network


def generate_summary(persons_data, flight_data, document_data, email_data, image_index):
    """Generate summary statistics."""
    log.info("📊 Generating Summary Statistics...")

    summary = {
        "total_persons": len(persons_data) if persons_data else 0,
        "total_flights": len(flight_data) if flight_data else 0,
        "total_documents": len(document_data) if document_data else 0,
        "total_emails": len(email_data) if email_data else 0,
        "total_images": sum(len(v) for v in image_index.values()),
        "data_sources": {
            "doj_datasets": 12,
            "doj_total_pages": "~3,500,000",
        },
    }

    # Persons stats
    if persons_data:
        nationalities = Counter(p.get("nationality", "Unknown") for p in persons_data if p.get("nationality"))
        categories = Counter(p.get("category", p.get("entity_type", "Unknown")) for p in persons_data)
        black_book_count = sum(1 for p in persons_data if p.get("in_black_book"))

        summary["persons_stats"] = {
            "nationalities": dict(nationalities.most_common(20)),
            "categories": dict(categories.most_common(20)),
            "in_black_book": black_book_count,
            "top_by_flights": [
                {"name": p["name"], "flights": p["flights"]}
                for p in sorted(persons_data, key=lambda x: x.get("flights", 0), reverse=True)[:15]
                if p.get("flights", 0) > 0
            ],
            "top_by_connections": [
                {"name": p["name"], "connections": p.get("connections", p.get("documents", 0))}
                for p in sorted(persons_data, key=lambda x: x.get("connections", x.get("documents", 0)), reverse=True)[:15]
            ],
        }

    # Flight stats
    if flight_data:
        years = Counter(f["year"] for f in flight_data if f.get("year"))
        departures = Counter(f["departure"] for f in flight_data if f.get("departure"))
        arrivals = Counter(f["arrival"] for f in flight_data if f.get("arrival"))
        aircraft = Counter(f["aircraft"] for f in flight_data if f.get("aircraft"))

        routes = Counter()
        for f in flight_data:
            dep = f.get("departure", "").strip()
            arr = f.get("arrival", "").strip()
            if dep and arr:
                routes[(dep, arr)] += 1

        summary["flight_stats"] = {
            "by_year": dict(sorted(years.items())),
            "top_departures": dict(departures.most_common(15)),
            "top_arrivals": dict(arrivals.most_common(15)),
            "top_routes": [{"from": r[0], "to": r[1], "count": c} for r, c in routes.most_common(20)],
            "aircraft_types": dict(aircraft.most_common(10)),
        }

    # Document stats
    if document_data:
        all_tags = Counter()
        all_power = Counter()
        all_agencies = Counter()
        all_leads = Counter()
        importance_dist = Counter()

        for doc in document_data:
            for t in doc.get("tags", []):
                if t: all_tags[t] += 1
            for p in doc.get("power_mentions", []):
                if p: all_power[p] += 1
            for a in doc.get("agency_involvement", []):
                if a: all_agencies[a] += 1
            for l in doc.get("lead_types", []):
                if l: all_leads[l] += 1
            score = doc.get("importance_score", 0)
            bucket = f"{(score // 10) * 10}-{(score // 10) * 10 + 9}"
            importance_dist[bucket] += 1

        summary["document_stats"] = {
            "top_tags": dict(all_tags.most_common(30)),
            "top_power_mentions": dict(all_power.most_common(20)),
            "top_agencies": dict(all_agencies.most_common(15)),
            "lead_types": dict(all_leads.most_common(15)),
            "importance_distribution": dict(sorted(importance_dist.items())),
            "avg_importance": round(sum(d["importance_score"] for d in document_data) / max(len(document_data), 1), 1),
        }

    # Email stats
    if email_data:
        senders = Counter(e["from"] for e in email_data if e.get("from"))
        recipients = Counter(e["to"] for e in email_data if e.get("to"))
        email_years = Counter()
        for e in email_data:
            ym = re.search(r"(19|20)\d{2}", e.get("date", ""))
            if ym:
                email_years[ym.group()] += 1

        summary["email_stats"] = {
            "top_senders": dict(senders.most_common(15)),
            "top_recipients": dict(recipients.most_common(15)),
            "by_year": dict(sorted(email_years.items())),
        }

    log.info("   ✅ Summary generated")
    return summary


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("  EPSTEIN FILES — DATA PROCESSING")
    log.info("=" * 60 + "\n")

    ensure_dirs()
    image_index = load_image_index()
    log.info(f"📷 Image index: {len(image_index)} entries\n")

    # Process each source
    entities_data = process_entities(image_index)
    kaggle_data = process_persons_kaggle(image_index)
    flight_data = process_flights()
    relationships_data = process_relationships()
    document_data = process_documents()
    email_data = process_emails()

    # Count connections from relationships
    connection_counts = count_connections_from_relationships(relationships_data)
    log.info(f"🔗 Derived connection counts for {len(connection_counts)} entities")

    # Merge persons data with connection counts
    persons_data = merge_persons(entities_data, kaggle_data, connection_counts)

    # Build network
    network_data = build_network(persons_data, relationships_data, flight_data)

    # Summary
    summary_data = generate_summary(persons_data, flight_data, document_data, email_data, image_index)

    # Export JSON
    log.info("\n💾 Exporting JSON files for dashboard...")

    exports = {
        "persons_of_interest.json": persons_data,
        "flight_logs.json": flight_data,
        "documents.json": document_data,
        "network.json": network_data,
        "summary.json": summary_data,
    }

    for filename, data in exports.items():
        filepath = DASHBOARD_DATA_DIR / filename
        if data:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            size_kb = filepath.stat().st_size / 1024
            log.info(f"   ✅ {filename} ({size_kb:.1f} KB)")
        else:
            with open(filepath, "w") as f:
                if "network" in filename:
                    json.dump({"nodes": [], "links": []}, f)
                elif "summary" in filename:
                    json.dump(summary_data or {}, f, indent=2)
                else:
                    json.dump([], f)
            log.info(f"   ⚠️ {filename} (empty — source data not available)")

    log.info("\n" + "=" * 60)
    log.info("  PROCESSING COMPLETE")
    log.info("=" * 60)
    log.info(f"  Output: {DASHBOARD_DATA_DIR}")
    log.info(f"  Dashboard: dashboard/index.html")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
