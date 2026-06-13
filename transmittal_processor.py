#!/usr/bin/env python3
"""
Transmittal Register Processor
Merges daily Aconex ExportMailAll with Master Submittal Log format.
"""

import re
import sys
import os
from datetime import datetime, timedelta
import openpyxl
from openpyxl import load_workbook
from openpyxl.styles import (PatternFill, Font, Alignment, Border, Side,
                              GradientFill)
from openpyxl.utils import get_column_letter
import copy

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Map short doc-type codes (from doc reference) to the Type codes used in Col H
DOC_TYPE_MAP = {
    'DRW': 'DRW', 'CAL': 'CAL', 'RPT': 'RPT', 'MTS': 'MAT', 'MAT': 'MAT',
    'ITP': 'ITP', 'MST': 'MST', 'PLN': 'PLN', 'PRD': 'PRD', 'PQN': 'PQN',
    'SPC': 'SPC', 'MAN': 'MAN', 'OTH': 'OTH', 'DES': 'DES', 'PGM': 'OTH',
    'IRE': 'OTH', 'TMP': 'PLN', 'SCH': 'OTH',
}

# Contractor org prefixes → outgoing submittals
CONTRACTOR_ORGS = {'MAPA-LIMAK-CRRC', 'GUNAL'}

# Engineer org prefix → responses
ENGINEER_ORGS_PREFIX = ('PAJV',)


# ─────────────────────────────────────────────────────────────────────────────
# Parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

DOC_REF_RE = re.compile(
    r'[A-Z]{2,10}-[A-Z0-9]{2,10}-[A-Z]{2,5}-[A-Z]{2,5}(?:-[A-Z]{2,5})*-\d{4,6}'
    r'(?:\s+to\s+\d+)?'
)
DOT_REF_RE = re.compile(
    r'\b[A-Z]{2,4}\.[A-Z]{2,4}\.[A-Z]{2,4}\d{0,4}(?:\.[A-Z0-9]{1,5}){1,5}\b'
)
REV_RE = re.compile(r'_Rev[.\s]([A-Z0-9]+)', re.IGNORECASE)
DCP_RE = re.compile(r'\bDCP\s*(\d+)\b', re.IGNORECASE)


def extract_doc_refs(subject: str) -> tuple[list[str], bool]:
    """
    Extract doc refs from subject.
    Returns (refs, is_dot_format).
    """
    dash_refs = DOC_REF_RE.findall(subject or '')
    if dash_refs:
        return dash_refs, False
    dot_refs = DOT_REF_RE.findall(subject or '')
    return dot_refs, bool(dot_refs)


def parse_doc_ref(doc_ref: str) -> dict:
    """
    Parse a doc ref like MLCC-S0681-CIV-VBR-PIR-DRW-13000
    Returns dict with keys: discipline, sub_discipline, type_code, type_h
    """
    parts = doc_ref.split('-')
    result = {'discipline': '', 'sub_discipline': '', 'type_code': '', 'type_h': ''}
    if len(parts) >= 4:
        result['discipline'] = parts[2]          # e.g. CIV
        result['sub_discipline'] = parts[3]      # e.g. VBR
    if len(parts) >= 6:
        # The type code is typically the second-to-last alpha segment
        for seg in reversed(parts):
            if seg.isalpha() and len(seg) == 3:
                tc = seg.upper()
                result['type_code'] = tc
                result['type_h'] = DOC_TYPE_MAP.get(tc, tc)
                break
    return result


def extract_revision(subject: str) -> str:
    """Return the value after '_Rev.' e.g. '_Rev.C01' → 'C01', '_Rev.01' → '01'."""
    m = REV_RE.search(subject or '')
    return m.group(1) if m else ''


def extract_dcp(subject: str) -> str:
    m = DCP_RE.search(subject or '')
    return f"DCP{m.group(1)}" if m else ''


def parse_date(val) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y'):
            try:
                return datetime.strptime(val.strip(), fmt)
            except ValueError:
                pass
    return None


def format_date(val) -> str:
    d = parse_date(val)
    return d.strftime('%d/%m/%Y') if d else (str(val) if val else '')


# ─────────────────────────────────────────────────────────────────────────────
# Main processor
# ─────────────────────────────────────────────────────────────────────────────

def load_master_log(path: str) -> dict:
    """Load master log, return dict keyed by Aconex Reference (col B)."""
    wb = load_workbook(path)
    ws = wb['Register']

    # Find header row (look for 'Aconex Reference')
    header_row = None
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=15, values_only=True), 1):
        if any('Aconex' in str(c) for c in row if c):
            header_row = i
            break
    if not header_row:
        raise ValueError("Could not find header row in Master Submittal Log")

    records = {}
    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
        aconex_ref = row[1]  # Col B
        if aconex_ref:
            records[str(aconex_ref).strip()] = {
                'row': list(row),
                'aconex_ref': str(aconex_ref).strip(),
            }
    return records


def load_export_mail(path: str) -> list[dict]:
    """Load ExportMailAll, return list of dicts."""
    wb = load_workbook(path)
    ws = wb['Mail']
    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    records = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        rec = dict(zip(headers, row))
        records.append(rec)
    return records


def _first_after_colon(s: str) -> str:
    """Return first name after the first ':' in a string."""
    if not s:
        return ''
    idx = s.find(':')
    return s[idx + 1:].split(',')[0].strip() if idx != -1 else ''


def _norm_subject(s: str) -> str:
    """Strip leading Re: prefixes and lowercase for subject matching."""
    return re.sub(r'^(Re:\s*)+', '', s or '', flags=re.IGNORECASE).strip().lower()


def build_intm_lead_map(mail_records: list[dict]) -> dict:
    """
    Map normalised subject → lead name.
    Source: INTM rows, lead = first name after ':' in their Recipients (col G).
    """
    lead_map = {}
    for rec in mail_records:
        if rec.get('Type') == 'Internal Memorandum':
            key = _norm_subject(rec.get('Subject', ''))[:120]
            lead = _first_after_colon(str(rec.get('Recipients') or ''))
            if key and lead:
                lead_map[key] = lead
    return lead_map


def process_transmittals(mail_records: list[dict],
                         existing_records: dict) -> list[dict]:
    """
    Build output rows.
    - Outgoing MLCC/GUNAL transmittals → new submittal rows
    - PAJV transmittals → response data for matching existing rows
    - Lead (col L): matched from INTM Recipients (col G) by subject
    Returns list of row dicts mapping to master log columns.
    """
    intm_lead_map = build_intm_lead_map(mail_records)
    rows = []
    for rec in mail_records:
        if rec.get('Type') != 'Transmittal':
            continue
        org = str(rec.get('From Organization') or '')
        mail_no = str(rec.get('Mail No') or '').strip()

        # Determine direction: outgoing contractor submittal or incoming PAJV response
        is_contractor = any(org.startswith(c) for c in CONTRACTOR_ORGS) or \
                        (mail_no.startswith('MLCC-') or mail_no.startswith('GUNAL-'))
        is_engineer_response = mail_no.startswith('PAJV-TRANSMIT')

        if not (is_contractor or is_engineer_response):
            continue

        subj = str(rec.get('Subject') or '').strip()
        date_val = parse_date(rec.get('Date'))

        # Extract doc refs from subject
        doc_refs, is_dot_ref = extract_doc_refs(subj)
        first_ref = doc_refs[0] if doc_refs else ''
        # Dot-format refs don't encode Type/Discipline/Sub-Discipline
        parsed = {} if is_dot_ref else (parse_doc_ref(first_ref) if first_ref else {})

        current_rev = extract_revision(subj)   # full value after _Rev. e.g. C01
        dcp = extract_dcp(subj)
        lead = intm_lead_map.get(_norm_subject(subj)[:120], '')

        due_date = date_val + timedelta(days=21) if date_val else None

        # Build row dict (matching master log column positions A-Z, AA)
        row = {
            'A': '',                                           # Draft
            'B': mail_no,                                     # Aconex Reference
            'C': date_val,                                    # Submittal Date
            'D': first_ref if first_ref else '',              # Doc Reference
            'E': subj,                                        # Submittal Item Description
            'F': current_rev,                                 # Current Rev (e.g. C01)
            'G': '',                                          # Rev. — not populated
            'H': parsed.get('type_h', ''),                   # Type
            'I': parsed.get('discipline', ''),               # Discipline
            'J': parsed.get('sub_discipline', ''),           # Sub Discipline
            'K': len(doc_refs) if doc_refs else 1,            # No of Items
            'L': lead,                                        # Lead
            'M': dcp,                                         # DCP
            'N': due_date,                                    # Due date (+21 days)
            'O': '',                                          # Response Ref.
            'P': '',                                          # Date Responded
            'Q': '',                                          # Response Status days
            'R': '',                                          # Days Overdue
            'S': '',                                          # Review Status
            'T': '',                                          # Actual Status
            'U': '',                                          # Contractor Response Due
            'V': '',                                          # Contractor Date Responded
            'W': '',                                          # Contractor Days Overdue
            'X': '',                                          # Contractor Response Status Days
            'Y': datetime.now(),                              # Data Date
            'Z': '',                                          # Remarks
            '_direction': 'outgoing' if is_contractor else 'incoming',
            '_raw': rec,
        }

        # Check if already in master log (skip duplicates — just flag them)
        row['_exists'] = mail_no in existing_records

        rows.append(row)

    return rows


def write_output_excel(rows: list[dict], output_path: str,
                       template_path: str | None = None):
    """Write output Excel file formatted like the Master Submittal Log."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Register'

    # ── Header block ──────────────────────────────────────────────────────────
    HEADERS = [
        'Draft', 'Aconex Reference', 'Submittal Date',
        'Document Reference No./Package no.', 'Submittal Item Description',
        'Current Rev', 'Rev.', 'Type', 'Discipline', 'Sub Discipline',
        'No of Items', 'Lead', 'DCP',
        'Due date of Response by the Engineer (+21 days from Submittal date)',
        'Response Ref.', 'Date Responded by the Engineer',
        'Response Status, days', 'Days Overdue', 'Review Status',
        'Actual Status (Latest Rev)',
        'Contractor Response Due (+14 Days from Response Date)',
        'Contractor Date Responded', 'Contractor Days Overdue',
        'Contractor Response Status Days', 'Data Date', 'Remarks',
    ]

    # Title rows
    ws.merge_cells('A1:Z1')
    ws['A1'] = 'TRANSMITTAL REGISTER'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')

    ws.merge_cells('A2:Z2')
    ws['A2'] = f'Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}'
    ws['A2'].alignment = Alignment(horizontal='center')

    # Blank rows 3-7 (match master log structure)
    for r in range(3, 8):
        ws.append([''] * 26)

    # Header row 8
    header_fill = PatternFill('solid', fgColor='1F4E79')
    header_font = Font(bold=True, color='FFFFFF', size=9)
    for col_idx, h in enumerate(HEADERS, 1):
        cell = ws.cell(row=8, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center',
                                   wrap_text=True)

    ws.row_dimensions[8].height = 45

    # ── Data rows ─────────────────────────────────────────────────────────────
    COL_KEYS = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

    alt_fill_new = PatternFill('solid', fgColor='EBF3FB')
    alt_fill_exists = PatternFill('solid', fgColor='FFF2CC')
    thin = Side(style='thin', color='CCCCCC')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    data_font = Font(size=9)
    data_font_exists = Font(size=9, italic=True, color='808080')

    outgoing_fill = PatternFill('solid', fgColor='E2EFDA')
    incoming_fill = PatternFill('solid', fgColor='FCE4D6')

    new_rows = [r for r in rows if not r['_exists']]
    exists_rows = [r for r in rows if r['_exists']]

    print(f"New transmittals (not in master log): {len(new_rows)}")
    print(f"Already in master log (skipped):      {len(exists_rows)}")

    row_num = 9
    for i, row in enumerate(rows):
        fill = outgoing_fill if row['_direction'] == 'outgoing' else incoming_fill
        if row['_exists']:
            fill = alt_fill_exists
        elif i % 2 == 0:
            pass  # keep direction fill

        for col_idx, key in enumerate(COL_KEYS, 1):
            val = row.get(key, '')
            cell = ws.cell(row=row_num, column=col_idx, value=val)
            cell.fill = fill
            cell.font = data_font_exists if row['_exists'] else data_font
            cell.border = border
            if key == 'E':
                cell.alignment = Alignment(wrap_text=True)
            elif key in ('C', 'N', 'P', 'U', 'Y'):
                if isinstance(val, datetime):
                    cell.number_format = 'DD/MM/YYYY'
            else:
                cell.alignment = Alignment(horizontal='left', vertical='center')

        # Add a note in remarks if already exists
        if row['_exists']:
            ws.cell(row=row_num, column=26, value='[Already in master log]')

        row_num += 1

    # ── Column widths ─────────────────────────────────────────────────────────
    COL_WIDTHS = {
        1: 8, 2: 22, 3: 14, 4: 38, 5: 55, 6: 10, 7: 8, 8: 8, 9: 10,
        10: 12, 11: 8, 12: 10, 13: 8, 14: 18, 15: 22, 16: 14, 17: 14,
        18: 12, 19: 14, 20: 14, 21: 14, 22: 14, 23: 14, 24: 14, 25: 12, 26: 30,
    }
    for col_idx, width in COL_WIDTHS.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Freeze panes at row 9, col C
    ws.freeze_panes = 'C9'

    # ── Summary sheet ─────────────────────────────────────────────────────────
    ws_sum = wb.create_sheet('Summary')
    ws_sum['A1'] = 'Processing Summary'
    ws_sum['A1'].font = Font(bold=True, size=12)
    summary_data = [
        ['Total rows in ExportMail', len(rows)],
        ['New outgoing submittals', len([r for r in rows if r['_direction'] == 'outgoing' and not r['_exists']])],
        ['New incoming responses', len([r for r in rows if r['_direction'] == 'incoming' and not r['_exists']])],
        ['Already in master log', len(exists_rows)],
        ['Generated', datetime.now().strftime('%d/%m/%Y %H:%M')],
    ]
    for r_idx, (label, val) in enumerate(summary_data, 3):
        ws_sum.cell(row=r_idx, column=1, value=label)
        ws_sum.cell(row=r_idx, column=2, value=val)
    ws_sum.column_dimensions['A'].width = 35
    ws_sum.column_dimensions['B'].width = 20

    wb.save(output_path)
    print(f"\nOutput saved to: {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def run(master_path: str, export_mail_path: str, output_path: str):
    print("Loading master log...")
    existing = load_master_log(master_path)
    print(f"  Loaded {len(existing)} existing records")

    print("Loading export mail...")
    mail_records = load_export_mail(export_mail_path)
    print(f"  Loaded {len(mail_records)} mail records")

    print("Processing transmittals...")
    rows = process_transmittals(mail_records, existing)
    print(f"  Built {len(rows)} output rows")

    print("Writing output Excel...")
    write_output_excel(rows, output_path)


if __name__ == '__main__':
    master = sys.argv[1] if len(sys.argv) > 1 else \
        '/root/.claude/uploads/8c61c79c-4d5d-56a0-a9bd-29d06cd54f04/e07e6045-Master_Submittal_Log_10062026.xlsx'
    export = sys.argv[2] if len(sys.argv) > 2 else \
        '/root/.claude/uploads/8c61c79c-4d5d-56a0-a9bd-29d06cd54f04/dfd6085b-ExportMailAll20260613_0837.xlsx'
    output = sys.argv[3] if len(sys.argv) > 3 else \
        '/home/user/Coursiv-training-/output_transmittal_register.xlsx'

    run(master, export, output)
