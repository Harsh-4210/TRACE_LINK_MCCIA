"""
TRACELink — clean_data.py
AUTO-GENERATES data.js from the 6 raw CSVs.
Run ONCE: python clean_data.py
Then serve: python -m http.server 8080
"""

import csv, json, re
from datetime import datetime

# ─── HELPERS ────────────────────────────────────────────────────────────────

def parse_date(raw):
    """[v2 FIX] Was called but never defined in v1."""
    raw = str(raw).strip()
    formats_to_try = [
        "%Y-%m-%d",   # 2023-03-31
        "%d/%m/%Y",   # 25/04/2023
        "%m/%d/%Y",   # 07/23/2023 (US format — ambiguous, try after DD/MM)
        "%d-%m-%Y",   # 07-01-2023
        "%Y/%m/%d",
    ]
    for fmt in formats_to_try:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None

def normalize_date_str(raw):
    d = parse_date(raw)
    if d:
        return d.strftime("%Y-%m-%d")
    return raw

# IMPORTANT: DD/MM/YYYY and MM/DD/YYYY are ambiguous.
# Rule: if day > 12, it must be DD/MM/YYYY.
# If day ≤ 12 and month ≤ 12, assume DD/MM/YYYY (Indian convention).

DEFECT_MAP = {
    "surfacedelamination": "surface_delamination",
    "surfdelam":           "surface_delamination",
    "surfdlm":             "surface_delamination",
    "edgeburr":            "edge_burr",
    "dimensionaldeviation":"dimensional_deviation",
}

def normalize_defect(raw):
    if not raw or str(raw).strip() == "":
        return ""
    key = str(raw).strip().lower().replace("-","").replace("_","").replace(" ","")
    # [v2 FIX] Use full-key matching, not fragile prefix[:6] matching
    for pattern, canonical in DEFECT_MAP.items():
        if key == pattern or key.startswith(pattern):
            return canonical
    return str(raw).strip().lower().replace(" ", "_")

def handle_missing_lot(row):
    """[v2 FIX] 8% of raw_materials rows have no lot_number."""
    if not row.get('lot_number') or str(row['lot_number']).strip() == '':
        row['lot_number'] = f"LOT-UNKNOWN-{row.get('receipt_date','UNK')}-{row.get('supplier_id','UNK')}"
        row['lot_flag'] = 'missing_original_lot_number'
    return row

def parse_batch_refs(ref_string):
    """[v2 FIX] Strip surrounding quotes from CSV parsing before splitting."""
    return [b.strip().strip('"').strip("'") for b in str(ref_string).split(',') if b.strip()]

def safe_float(val, default=0.0):
    try:
        return float(str(val).strip())
    except:
        return default

def safe_int(val, default=0):
    try:
        return int(str(val).strip())
    except:
        return default

# ─── READ CSVs ──────────────────────────────────────────────────────────────

def read_csv(filepath):
    rows = []
    with open(filepath, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    return rows

print("Reading CSVs...")
raw_materials_raw  = read_csv("raw_materials_log.csv")
production_raw     = read_csv("production_log.csv")
qc_raw             = read_csv("qc_inspection.csv")
dispatch_raw       = read_csv("dispatch_log.csv")
supplier_raw       = read_csv("supplier_master.csv")
complaints_raw     = read_csv("defect_complaints.csv")

print(f"  raw_materials : {len(raw_materials_raw)} rows")
print(f"  production    : {len(production_raw)} rows")
print(f"  qc            : {len(qc_raw)} rows")
print(f"  dispatch      : {len(dispatch_raw)} rows")
print(f"  suppliers     : {len(supplier_raw)} rows")
print(f"  complaints    : {len(complaints_raw)} rows")

# ─── CLEAN RAW MATERIALS ────────────────────────────────────────────────────

clean_raw_materials = []
for row in raw_materials_raw:
    row = handle_missing_lot(row)
    row['receipt_date'] = normalize_date_str(row.get('receipt_date',''))
    row['quantity_kg']  = safe_float(row.get('quantity_kg', 0))
    clean_raw_materials.append(row)

# ─── CLEAN QC ───────────────────────────────────────────────────────────────

clean_qc = []
for row in qc_raw:
    row['inspection_date'] = normalize_date_str(row.get('inspection_date',''))
    row['defect_type']     = normalize_defect(row.get('defect_type',''))
    row['defect_rate_pct'] = safe_float(row.get('defect_rate_pct', 0))
    clean_qc.append(row)

# ─── CLEAN DISPATCH ─────────────────────────────────────────────────────────

clean_dispatch = []
for row in dispatch_raw:
    row['dispatch_date'] = normalize_date_str(row.get('dispatch_date',''))
    row['quantity']      = safe_int(row.get('quantity', 0))
    # Keep batch_ref as-is; parseBatchRefs handles splitting in JS
    clean_dispatch.append(row)

# ─── CLEAN SUPPLIER MASTER ──────────────────────────────────────────────────

supplier_master = supplier_raw  # Already clean

# ─── CLEAN COMPLAINTS ───────────────────────────────────────────────────────

defect_complaints = []
for row in complaints_raw:
    row['complaint_date']       = normalize_date_str(row.get('complaint_date',''))
    row['financial_impact_inr'] = safe_int(row.get('financial_impact_inr', 0))
    defect_complaints.append(row)

# ─── CLEAN PRODUCTION + IMPUTATION ──────────────────────────────────────────

def impute_missing_batches(production_rows):
    """
    Rule 1 (Confidence 75% — High Confidence):
      Same lot_number + same machine_id + date within ±3 days of a known batch
    Rule 2 (Confidence 45% — Moderate Confidence):
      Same lot_number + date within ±7 days (any machine)
    Rule 3 (Confidence 0% — Low Confidence — Manual Review):
      No match found → assign synthetic ID
    """
    # [v2 FIX] orphan_seq was used but never initialized in v1
    orphan_seq = 0
    imputation_log = []

    known   = [r for r in production_rows if r.get('batch_id') and str(r['batch_id']).strip()]
    missing = [r for r in production_rows if not r.get('batch_id') or not str(r['batch_id']).strip()]

    for row in missing:
        row_date = parse_date(row.get('date',''))
        if not row_date:
            row['batch_id']         = f"INFERRED-NODATE-{orphan_seq}"
            row['confidence']       = 0
            row['confidence_rule']  = 'Unparseable date — manual review'
            row['confidence_label'] = 'Low Confidence — Manual Review Needed'
            row['is_inferred']      = True
            imputation_log.append({'batch_id': row['batch_id'], 'rule': 3, 'confidence': 0, 'reason': 'Unparseable date'})
            orphan_seq += 1
            continue

        # Rule 1: same lot + same machine + ±3 days
        candidates_r1 = [
            k for k in known
            if k.get('input_lot_ref') == row.get('input_lot_ref')
            and k.get('machine_id') == row.get('machine_id')
            and parse_date(k.get('date',''))
            and abs((parse_date(k['date']) - row_date).days) <= 3
        ]
        if candidates_r1:
            best = min(candidates_r1, key=lambda k: abs((parse_date(k['date']) - row_date).days))
            row['batch_id']         = best['batch_id']
            row['confidence']       = 75
            row['confidence_rule']  = 'Same lot + machine + ±3 days'
            row['confidence_label'] = 'High Confidence (Same Machine)'
            row['is_inferred']      = True
            imputation_log.append({'batch_id': row['batch_id'], 'rule': 1, 'confidence': 75,
                                   'reason': f"Matched {best['batch_id']} via Rule 1"})
            continue

        # Rule 2: same lot + ±7 days
        candidates_r2 = [
            k for k in known
            if k.get('input_lot_ref') == row.get('input_lot_ref')
            and parse_date(k.get('date',''))
            and abs((parse_date(k['date']) - row_date).days) <= 7
        ]
        if candidates_r2:
            best = min(candidates_r2, key=lambda k: abs((parse_date(k['date']) - row_date).days))
            row['batch_id']         = best['batch_id']
            row['confidence']       = 45
            row['confidence_rule']  = 'Same lot + ±7 days (any machine)'
            row['confidence_label'] = 'Moderate Confidence (Same Week)'
            row['is_inferred']      = True
            imputation_log.append({'batch_id': row['batch_id'], 'rule': 2, 'confidence': 45,
                                   'reason': f"Matched {best['batch_id']} via Rule 2"})
            continue

        # Rule 3: orphan
        row['batch_id']         = f"INFERRED-{row.get('input_lot_ref','UNK')}-{orphan_seq}"
        row['confidence']       = 0
        row['confidence_rule']  = 'No match found — manual review required'
        row['confidence_label'] = 'Low Confidence — Manual Review Needed'
        row['is_inferred']      = True
        imputation_log.append({'batch_id': row['batch_id'], 'rule': 3, 'confidence': 0,
                               'reason': 'No temporal/lot match found'})
        orphan_seq += 1

    return production_rows, imputation_log

clean_production_raw = []
for row in production_raw:
    row['date']          = normalize_date_str(row.get('date',''))
    row['units_produced'] = safe_int(row.get('units_produced', 0))
    row['cycle_time_min'] = safe_float(row.get('cycle_time_min', 0))
    if row.get('batch_id') and str(row['batch_id']).strip():
        row['is_inferred']      = False
        row['confidence']       = 100
        row['confidence_rule']  = 'Direct match'
        row['confidence_label'] = 'Direct Match — batch ID explicitly recorded'
    clean_production_raw.append(row)

clean_production, imputation_log = impute_missing_batches(clean_production_raw)

# ─── SHIFT STATS ────────────────────────────────────────────────────────────

def compute_shift_stats(production_rows, qc_rows):
    """[v2 WoW] Pre-compute shift fail rates by joining QC → production."""
    qc_by_batch = {r['batch_id']: r for r in qc_rows if r.get('batch_id')}
    shift_stats = {
        'A': {'total': 0, 'fail': 0},
        'B': {'total': 0, 'fail': 0},
        'C': {'total': 0, 'fail': 0}
    }

    for row in production_rows:
        shift = row.get('shift', '').strip()
        if shift not in shift_stats:
            continue
        qc = qc_by_batch.get(row.get('batch_id',''))
        if qc:
            shift_stats[shift]['total'] += 1
            if qc.get('pass_fail') == 'FAIL':
                shift_stats[shift]['fail'] += 1

    for s in shift_stats:
        total = shift_stats[s]['total']
        fail  = shift_stats[s]['fail']
        shift_stats[s]['fail_rate_pct'] = round((fail / total * 100), 2) if total > 0 else 0

    return shift_stats

shift_stats = compute_shift_stats(clean_production, clean_qc)
print(f"\nShift stats: {shift_stats}")

# ─── DATA INTEGRITY WARNINGS ────────────────────────────────────────────────

def check_temporal_integrity(production_rows, qc_rows):
    """[v2 FIX] Flag batches where QC date precedes production date."""
    qc_by_batch = {r['batch_id']: r for r in qc_rows if r.get('batch_id')}
    warnings = []
    for row in production_rows:
        bid = row.get('batch_id')
        if not bid:
            continue
        qc = qc_by_batch.get(bid)
        if not qc:
            continue
        prod_date = parse_date(row.get('date',''))
        qc_date   = parse_date(qc.get('inspection_date',''))
        if prod_date and qc_date and qc_date < prod_date:
            warnings.append({
                'batch_id':        bid,
                'issue':           'qc_before_production',
                'production_date': row.get('date'),
                'qc_date':         qc.get('inspection_date'),
                'note':            'Synthetic data artifact — dates unverified'
            })
    return warnings

data_warnings = check_temporal_integrity(clean_production, clean_qc)
print(f"Data integrity warnings: {len(data_warnings)}")

# ─── LOT ANOMALY DETECTION ──────────────────────────────────────────────────

def detect_lot_anomalies(raw_materials):
    """LOT-2023-114 appears under 6 different supplier_ids (S01–S06)."""
    lot_suppliers = {}
    for row in raw_materials:
        lot = row.get('lot_number','')
        if lot:
            if lot not in lot_suppliers:
                lot_suppliers[lot] = set()
            lot_suppliers[lot].add(row.get('supplier_id',''))
    return {
        lot: sorted(list(suppliers))
        for lot, suppliers in lot_suppliers.items()
        if len(suppliers) > 1
    }

lot_anomalies = detect_lot_anomalies(clean_raw_materials)
print(f"Lot anomalies detected: {list(lot_anomalies.keys())[:5]} ...")

# Verify LOT-2023-114
if 'LOT-2023-114' in lot_anomalies:
    print(f"  LOT-2023-114 supplier IDs: {lot_anomalies['LOT-2023-114']}")

# ─── VERIFY GROUND TRUTH ────────────────────────────────────────────────────

print("\n--- GROUND TRUTH VERIFICATION ---")

# D-1847 trace
d1847 = next((d for d in clean_dispatch if d.get('order_id') == 'D-1847'), None)
if d1847:
    print(f"D-1847 batch_ref: {d1847.get('batch_ref')}")

# LOT-2023-114 contamination
lot114_batches = [p for p in clean_production if p.get('input_lot_ref') == 'LOT-2023-114']
lot114_batch_ids = list({p['batch_id'] for p in lot114_batches if p.get('batch_id')})
print(f"LOT-2023-114 production rows: {len(lot114_batches)}")
print(f"LOT-2023-114 unique batch IDs: {len(lot114_batch_ids)}")

# Which dispatch orders link to LOT-2023-114?
affected_orders = []
for order in clean_dispatch:
    refs = parse_batch_refs(order.get('batch_ref',''))
    if any(r in lot114_batch_ids for r in refs):
        affected_orders.append(order['order_id'])
print(f"Dispatch orders for LOT-2023-114: {len(affected_orders)} -> {affected_orders}")

# ─── WRITE DATA.JS ──────────────────────────────────────────────────────────

print("\nWriting data.js...")

with open('data.js', 'w', encoding='utf-8') as f:
    f.write(f"""// AUTO-GENERATED by clean_data.py — DO NOT EDIT MANUALLY
// Generated: {datetime.now().isoformat()}
// Cleaning assumptions:
//   - Ambiguous dates (DD/MM vs MM/DD) resolved using Indian convention (DD/MM)
//   - Missing batch_ids imputed using proximity rules (see IMPUTATION_LOG)
//   - Missing lot_numbers assigned synthetic LOT-UNKNOWN-date-supplier IDs
//   - Defect types normalized to canonical labels (6 variants → 3 canonical)
//   - LOT-2023-114 flagged: appears under 6 supplier IDs (process control anomaly)
//   - QC-before-production temporal anomalies flagged in DATA_WARNINGS

var RAW_MATERIALS  = {json.dumps(clean_raw_materials,  indent=2, ensure_ascii=False)};
var PRODUCTION     = {json.dumps(clean_production,     indent=2, ensure_ascii=False)};
var QC             = {json.dumps(clean_qc,             indent=2, ensure_ascii=False)};
var DISPATCH       = {json.dumps(clean_dispatch,       indent=2, ensure_ascii=False)};
var SUPPLIERS      = {json.dumps(supplier_master,      indent=2, ensure_ascii=False)};
var COMPLAINTS     = {json.dumps(defect_complaints,    indent=2, ensure_ascii=False)};
var LOT_ANOMALIES  = {json.dumps(lot_anomalies,        indent=2, ensure_ascii=False)};
var IMPUTATION_LOG = {json.dumps(imputation_log,       indent=2, ensure_ascii=False)};
var SHIFT_STATS    = {json.dumps(shift_stats,          indent=2, ensure_ascii=False)};
var DATA_WARNINGS  = {json.dumps(data_warnings,        indent=2, ensure_ascii=False)};
""")

print("[OK] data.js written successfully.")
print("\nNow run: python -m http.server 8080")
print("Then open: http://localhost:8080/index.html")
