<p align="center">
  <img src="https://img.shields.io/badge/⚖️-OSINT_Research-8B5CF6?style=for-the-badge" alt="OSINT Research" />
</p>

<h1 align="center">🔍 Epstein Files Intelligence Dashboard</h1>

<p align="center">
  <em>An open-source intelligence dashboard for exploring publicly released documents, flight logs, relationships, and persons of interest related to the Jeffrey Epstein case.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9+" />
  <img src="https://img.shields.io/badge/javascript-ES6+-F7DF1E?style=flat-square&logo=javascript&logoColor=black" alt="JavaScript ES6+" />
  <img src="https://img.shields.io/badge/chart.js-v4-FF6384?style=flat-square&logo=chartdotjs&logoColor=white" alt="Chart.js v4" />
  <img src="https://img.shields.io/badge/d3.js-v7-F9A03C?style=flat-square&logo=d3dotjs&logoColor=white" alt="D3.js v7" />
  <img src="https://img.shields.io/badge/license-MIT-22C55E?style=flat-square" alt="MIT License" />
  <img src="https://img.shields.io/badge/data-DOJ_|_Kaggle_|_Public_Records-0EA5E9?style=flat-square" alt="Data Sources" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/persons_of_interest-1,297-8B5CF6?style=flat-square" alt="1297 Persons" />
  <img src="https://img.shields.io/badge/ranked_documents-25,781-EC4899?style=flat-square" alt="25781 Documents" />
  <img src="https://img.shields.io/badge/flight_records-55-06B6D4?style=flat-square" alt="55 Flights" />
  <img src="https://img.shields.io/badge/relationships-1,000-F59E0B?style=flat-square" alt="1000 Relationships" />
  <img src="https://img.shields.io/badge/images-5,700+-10B981?style=flat-square" alt="5700+ Images" />
</p>

---

## 📋 Overview

A complete data pipeline and interactive web dashboard for analysing publicly available data from the Jeffrey Epstein case. The project downloads, cleans, cross-references, and visualises data from multiple open sources — no API keys required for core functionality.

### ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🏠 **Overview Dashboard** | Key metrics, top 15 by flights & connections, yearly trends, top routes, nationality breakdown |
| 👤 **Persons of Interest** | Searchable/sortable table of 1,297 individuals with bios, flight counts, document mentions, connection scores |
| ✈️ **Flight Analysis** | Aircraft usage charts, departure/arrival heatmaps, full flight log table with passenger names |
| 📄 **Ranked Documents** | 25,781 AI-ranked documents from U.S. House Oversight with importance scores, tags, and key insights |
| 🕸️ **Network Graph** | Interactive D3.js force-directed graph with 305 nodes and 1,000 relationship links |
| 🖼️ **Image Integration** | 73 person headshots auto-fetched from Wikipedia, 5,702 document scans from Kaggle |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+**
- **Kaggle CLI** *(optional — for supplemental datasets)*

### Installation

```bash
# Clone the repository
git clone https://github.com/maninka123/Epstein-files-dashboard.git
cd Epstein-files-dashboard

# Install Python dependencies
pip install -r requirements.txt

# (Optional) Set up Kaggle for supplemental data
pip install kaggle
# Download your API token from https://www.kaggle.com/settings
mv ~/Downloads/kaggle.json ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json
```

### Run

```bash
# Step 1: Download all data (archive + Kaggle)
python scripts/download_data.py

# Step 2: Download & organise person images
python scripts/sync_images.py

# Step 3: Process data into dashboard JSON
python scripts/process_data.py

# Step 4: Launch dashboard
cd dashboard && python3 -m http.server 8765
# Open http://localhost:8765
```

---

## 📁 Project Structure

```
epstein-files-dashboard/
├── 📄 README.md
├── 📄 requirements.txt
│
├── 📂 scripts/
│   ├── download_data.py        # Downloads CSVs from archive + Kaggle datasets
│   ├── sync_images.py          # Fetches Wikipedia headshots, sorts images by category
│   └── process_data.py         # Cleans, normalises, cross-references → exports JSON
│
├── 📂 dashboard/
│   ├── index.html              # 5-tab dashboard layout
│   ├── styles.css              # Dark theme with glassmorphism
│   ├── app.js                  # Chart.js + D3.js visualisations
│   └── 📂 data/                # Auto-generated JSON files
│       ├── persons_of_interest.json
│       ├── flight_logs.json
│       ├── documents.json
│       ├── network.json
│       └── summary.json
│
└── 📂 data/
    ├── 📂 persons_of_interest/ # Entity CSVs + Kaggle POI CSV
    ├── 📂 flight_logs/         # Flight log CSVs
    ├── 📂 documents/           # Ranked JSONL files (U.S. House Oversight)
    ├── 📂 relationships/       # Network relationship CSVs
    ├── 📂 emails/              # Email metadata CSVs
    ├── 📂 images/
    │   ├── 📂 persons/         # Wikipedia headshots (73 images)
    │   ├── 📂 victims/         # Victim photos (3 images)
    │   └── 📂 documents/       # EFTA document scans (5,702 images)
    ├── 📂 raw/                 # DOJ metadata
    └── 📂 processed/           # Image index JSON
```

---

## 📊 Data Sources

| Source | Auth Required | Data |
|--------|:---:|------|
| [epsteininvestigation.org](https://epsteininvestigation.org) | ❌ | Entities, flights, relationships, emails |
| [Kaggle — POI List](https://www.kaggle.com/datasets/wilomentena/epstein-list-persons-of-interest) | 🔑 | 1,264 persons with bios, connections, Black Book status |
| [Kaggle — Ranked Docs](https://www.kaggle.com/datasets/linogova/epstein-ranker-dataset-u-s-house-oversight) | 🔑 | 25,781 AI-ranked documents |
| [Kaggle — File Images](https://www.kaggle.com/datasets/commanderbtc/epstein-files-images) | 🔑 | 5,702 document page scans |
| [Wikipedia](https://en.wikipedia.org) | ❌ | Person headshot thumbnails |
| [U.S. DOJ](https://www.justice.gov/epstein) | ❌ | ~3.5M pages across 12 datasets (metadata only) |

> 🔑 = Requires free [Kaggle API token](https://www.kaggle.com/settings). Core data works without it.

---

## 🖥️ Dashboard Tabs

### 📊 Overview
Key metrics at a glance — total persons, flights, documents. Bar charts for top 15 by flight count and connections. Line chart for flights by year (peak: 2002–2003). Top routes and nationality breakdown.

### 👤 Persons of Interest
Full-text search, column sorting, category filter (person/organization/location). Paginated table with modal detail view showing bio, stats, and images. Data from both the investigation archive and Kaggle POI dataset.

### ✈️ Flight Analysis
Aircraft usage breakdown (N908JE: 38 flights, N986JE: 17 flights). Top departure/arrival airports. Complete flight log table with dates, routes, and passenger manifests.

### 📄 Documents
25,781 ranked documents with AI-generated importance scores (1–10), headlines, reasoning, tags, and power mentions. Filterable by importance threshold.

### 🕸️ Network Graph
Interactive force-directed graph (D3.js) with 305 nodes and 1,000 links. Colour-coded by connection intensity (red = high, yellow = medium, green = low, blue = flight-only). Adjustable minimum connections slider and person search/highlight.

---

## 🔧 Scripts

| Script | Purpose | Runtime |
|--------|---------|---------|
| `download_data.py` | Downloads all CSVs from archive API + 3 Kaggle datasets | ~2 min |
| `sync_images.py` | Sorts document scans, fetches Wikipedia headshots | ~3 min |
| `process_data.py` | Normalises, merges, derives connections → exports JSON | ~2 min |

---

## ⚙️ Tech Stack

**Backend / Data Pipeline**
- Python 3.9+ — pandas, requests, BeautifulSoup4
- Kaggle CLI — dataset downloads

**Frontend / Dashboard**
- Vanilla HTML5 + CSS3 + JavaScript (ES6+)
- [Chart.js v4](https://www.chartjs.org/) — bar, line, doughnut charts
- [D3.js v7](https://d3js.org/) — force-directed network graph
- Dark theme with CSS glassmorphism and gradient animations

---

## 📜 License

This project is released under the [MIT License](LICENSE).

---

## ⚠️ Disclaimer

> This project is intended **strictly for research and educational purposes**. All data is sourced from publicly available DOJ releases, court documents, Kaggle datasets, Wikipedia, and public records. This project does not make any claims of guilt or innocence. The inclusion of any individual's name does not imply wrongdoing.

---

## 🏷️ Keywords

`epstein` · `osint` · `intelligence-dashboard` · `data-visualisation` · `network-analysis` · `flight-logs` · `d3js` · `chartjs` · `public-records` · `doj` · `investigative-journalism` · `open-source-intelligence` · `dark-theme-dashboard`

---

<p align="center">
  <sub>Data sourced from publicly available DOJ releases, court documents, and public records. For research purposes only.</sub>
</p>
