<div align="center">

# 🔗 TRACELink

### Batch Traceability System for Indian Auto-Component Manufacturing

**AMD Slingshot Regional Ideathon · PS-01: The Silent Recall**

[![Python](https://img.shields.io/badge/ETL-Python_3.x-3776AB?logo=python&logoColor=white)](clean_data.py)
[![HTML](https://img.shields.io/badge/Frontend-Single_HTML-E34F26?logo=html5&logoColor=white)](index.html)
[![Offline](https://img.shields.io/badge/Mode-Offline_First-4CAF50?logo=wifi&logoColor=white)](#offline-capability)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)

<br/>

*When 340 brake pads fail at Tata Motors, finding the root cause takes **4.5 days manually**.*
*TRACELink finds the same answer in **0.3 milliseconds**.*

</div>

---

## 🎯 The Problem

A mid-tier auto-component plant in Pune runs **2 production lines, 3 shifts, ~8,000 units/day**. When a batch-level defect surfaces at an OEM customer, the recall investigation is entirely manual:

- Open 3 Excel sheets (production, QC, dispatch)
- Cross-reference ~5,400 rows by eye
- Call the warehouse, QC, and supplier
- **Time to root cause: 4.5 days**
- **During those 4.5 days: 2 more contaminated shipments escape**

The data exists. The linkage doesn't.

## 💡 The Solution

TRACELink is a **zero-dependency, offline-first traceability engine** that connects every node in the manufacturing chain:

```
Raw Material (Lot) → Production (Batch) → QC (Inspection) → Dispatch (Order) → Customer (OEM)
```

One contaminated lot → every affected batch, order, and customer — **in under 1 second**.

---

## 🏗️ Architecture

```
MMCIA/
├── clean_data.py          ← ETL pipeline. Run ONCE. Outputs data.js
├── data.js                ← Pre-cleaned, pre-imputed dataset (auto-generated, gitignored)
├── index.html             ← Complete PWA. Imports data.js at runtime
└── *.csv                  ← Raw source data (6 files)
```

### Why This Design

| Approach | Problem |
|----------|---------|
| Pure single HTML | 10,000+ rows inline = 500KB parse lag |
| Python backend + API | Deployment risk, port conflicts, server dependency |
| **Python ETL → data.js → HTML** | ✅ Data pre-validated. Zero runtime dependencies. Works offline. |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.x (for data cleaning — one-time)
- Any modern browser

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/Harsh-4210/TRACE_LINK_MCCIA.git
cd TRACE_LINK_MCCIA

# 2. Generate clean dataset
python clean_data.py

# 3. Serve locally (required — Chrome blocks file:// script loading)
python -m http.server 8080

# 4. Open in browser
# http://localhost:8080/index.html
```

> ⚠️ **Do NOT open index.html via file://** — Chrome silently blocks `<script src="data.js">` due to CORS policy. Always use the HTTP server.

---

## ✨ Features

### 📦 Order Trace Engine
Enter any dispatch order ID → get the complete end-to-end chain:
- **Dispatch** → Customer, product, quantity, vehicle
- **Production** → Machine, operator, shift, cycle time
- **QC Inspection** → Pass/Fail, defect type, rate, inspector
- **Raw Materials** → Lot number, supplier, quality grade
- **Anomaly Detection** → Cross-supplier lot flags

### ⚠️ Contamination Blast Radius
Enter a contaminated lot number → instant impact assessment:
- All affected batches and dispatch orders
- Financial exposure calculation (with complaint correlation)
- **Escaped shipments** (shipped before QC caught the defect)
- **Post-QC dispatches** (shipped after the defect was known — process failure)
- Quarantine recommendations for unshipped inventory

### 📊 Shift Intelligence
Real-time QC fail rates by shift (A/B/C), pre-computed from 5,400 production records:
- Worst-performing shift highlighted
- Visible in hero section — no clicks needed

### 🔧 Data Imputation Engine (40% of Judging Rubric)

678 of 5,400 production rows had **missing batch IDs**. We don't drop them — we impute with documented confidence:

| Rule | Confidence | Logic |
|------|-----------|-------|
| Rule 1 | 🟡 75% — High | Same lot + same machine + ±3 days of known batch |
| Rule 2 | 🟠 45% — Moderate | Same lot + ±7 days (any machine) |
| Rule 3 | 🔴 0% — Manual Review | No match → synthetic ID, flagged for human verification |

Every imputed record carries a visible confidence badge and full audit trail.

### ✏️ Shop-Floor Batch Logger
- **Bilingual** — English / Marathi toggle (Noto Sans Devanagari)
- **Offline-first** — saves to `localStorage`, syncs when connected
- **Shift-aware** — filter to active shift

### 🤖 AI Query Interface
Natural language queries against the dataset. Works without API keys via local data scanning fallback.

### 📋 Data Audit Dashboard
Full transparency on the cleaning pipeline:
- Row counts (2,400 raw materials · 5,400 production · 5,400 QC · 1,800 dispatch)
- Imputation breakdown with per-record decision logs
- Temporal integrity warnings (QC-before-production anomalies)
- LOT anomaly flags

---

## 📈 Key Metrics

| Metric | Value |
|--------|-------|
| Trace Speed | **0.3ms** (measured via `performance.now()`) |
| Manual Process | **4.5 days** |
| Financial Exposure | **₹2,52,500** (C001 + C003; C002 excluded — unrelated tooling) |
| Contaminated Batches | **19** from LOT-2023-114 |
| Affected Dispatch Orders | **7** across 3 OEMs |
| Missing Batch IDs Imputed | **678** (29 Rule 1 · 169 Rule 2 · 480 flagged) |
| Defect Spellings Normalized | **6 → 3** canonical labels |
| Worst Shift (QC Fail Rate) | **Shift A — 7.07%** |
| Industry Defect Limit | **0.5%** (BATCH-2023-0500 at 5.74% = 11.5× over) |

---

## 🧹 Data Cleaning Pipeline

The `clean_data.py` ETL handles real-world manufacturing data quality issues:

- **Date Normalization** — DD/MM/YYYY (Indian convention) vs MM/DD/YYYY disambiguation
- **Defect Canonicalization** — `"surf-delam"`, `"SurfDeLam"`, `"surfdlm"` → `surface_delamination`
- **Missing Lot Recovery** — 8% of raw materials rows have no lot number → synthetic LOT-UNKNOWN IDs
- **Batch Imputation** — 3-tier proximity algorithm with confidence scoring
- **Temporal Integrity** — Flags batches where QC inspection date precedes production date
- **LOT Anomaly Detection** — LOT-2023-114 appears under 6 different supplier IDs (S01–S06)

---

## 🔒 Offline Capability

TRACELink is designed for shop-floor environments with unreliable connectivity:

- **Full functionality offline** — all data pre-loaded in `data.js`
- **Embedded demo data** — if `data.js` fails to load, falls back to key records
- **localStorage queue** — batch entries saved locally, synced when online
- **Zero external dependencies** — no CDNs, no APIs, no frameworks

---

## 📂 Source Data

| File | Rows | Description |
|------|------|-------------|
| `raw_materials_log.csv` | 2,400 | Material receipts with lot numbers, suppliers, grades |
| `production_log.csv` | 5,400 | Production records — some with missing batch IDs |
| `qc_inspection.csv` | 5,400 | QC results with inconsistent defect type labels |
| `dispatch_log.csv` | 1,800 | Customer shipments with batch references |
| `supplier_master.csv` | 6 | Supplier metadata |
| `defect_complaints.csv` | 3 | OEM complaints with financial impact |

---

## 🛠️ Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| ETL | Python 3 (csv, json, datetime) | Standard library only — no pip installs |
| Frontend | Vanilla HTML/CSS/JS | Zero build step, any browser, any laptop |
| Fonts | IBM Plex Sans, JetBrains Mono, Orbitron, Noto Sans Devanagari | Industrial aesthetic + bilingual support |
| Storage | localStorage | Offline batch logging queue |
| Server | `python -m http.server` | One command, zero config |

---

## 👥 Team

**AMD Slingshot Regional Ideathon — PS-01: The Silent Recall**

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
