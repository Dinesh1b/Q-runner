"""
ENTERPRISE AUDIT VALIDATION SYSTEM
====================================
Fields to validate = columns present in 'auditSummary' Excel sheet.

  Add a column    → that field gets validated
  Remove a column → that field is skipped
  No code changes needed.

FILTER MERGE LOGIC:
  Negative Variance badge  → shows rows from: Negative Variance + Not Found
  Positive Variance badge  → shows rows from: Positive Variance + Excess Line Item

BIZ RULES:
  Matched Line Item  → Stock Quantity == Audited Qty
  Location Conflict  → Stock Location != Audited Location
  Damaged Report     → Damaged Qty > 0
"""

import math
import os
import re
import shutil
import subprocess
import sys
import zlib
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Optional
from dataclasses import dataclass
from enum import Enum
import pandas as pd
from playwright.sync_api import sync_playwright, Page
try:
    from audit.run_report import run_files, save_to_run_report
except ImportError:                       # run from inside the audit folder
    from run_report import run_files, save_to_run_report


# ── filter enums ─────────────────────────────────────────────────────
class FilterType(Enum):
    ALL                  = "All"
    MATCHED_LINE_ITEM    = "Matched Line Item"
    NOT_FOUND            = "Not Found"
    EXCESS_LINE_ITEM     = "Excess Line Item"
    NEGATIVE_VARIANCE    = "Negative Variance"
    POSITIVE_VARIANCE    = "Positive Variance"
    LOCATION_CONFLICT    = "Location Conflict"
    CROSS_CHECKED_AUDIT  = "Cross Checked Audit"
    DAMAGED_REPORT       = "Damaged Report"
    UN_VERIFIED          = "Un Verified"

class SubFilterType(Enum):
    NEGATIVE_LINE_ITEM = "Negative Line Item"
    POSITIVE_LINE_ITEM = "Positive Line Item"

UI_FILTERS   = [f.value for f in FilterType if f != FilterType.UN_VERIFIED]
SKIP_FILTERS = {"Matched"}


# ── secondary filter columns (O, P in the Excel sheet) ───────────────
SECONDARY_FILTER_COLUMNS: List[str] = [
    "Damaged Filter",
    "Location Filter",
]

# ── filter merge map ─────────────────────────────────────────────────
FILTER_MERGE_MAP: Dict[str, List[str]] = {
    FilterType.NEGATIVE_VARIANCE.value: [
        FilterType.NEGATIVE_VARIANCE.value,
        FilterType.NOT_FOUND.value,
    ],
    FilterType.POSITIVE_VARIANCE.value: [
        FilterType.POSITIVE_VARIANCE.value,
        FilterType.EXCESS_LINE_ITEM.value,
    ],
}

# ── full UI column → td index map ────────────────────────────────────
# Fallback only: extract_row uses the index read from the table header
# (see refresh_column_index), because the column order changes between releases.
ALL_UI_COLUMNS: Dict[str, int] = {
    "Item Code":        1,
    "Item Name":        2,
    "Category":         3,
    "Stock Location":   4,
    "Audited Location": 5,
    "UOM":              6,
    "Stock Quantity":   7,
    "Audited Qty":      8,
    "Variance":         9,
    "Variance Value":   10,
    "Variance Type":    11,
    "Variance History": 12,
    "Damaged Qty":      13,
    "Auditor Name":     14,
    "Audited DateTime": 15,
    "Audited Image":    16,
    "Cross AuditedQty": 17,
    "Cross DamagedQty": 18,
    "Reason":           19,
    "Geo Location":     20,
    "Resolution Status": 21,
    "Remarks":          22,
}

# Field name (as used in the Excel sheet) → UI header text, where they differ
UI_HEADER_ALIASES: Dict[str, str] = {
    "UOM":              "UOM (Base)",
    "Audited Qty":      "Audited Quantity",
    "Auditor Name":     "Auditor",
    "Audited DateTime": "Audited Date",
    "Reason":           "Declaration Note",
    "Geo Location":     "Coordinates",
}

# ── config ───────────────────────────────────────────────────────────
@dataclass
class Config:
    DEFAULT_TIMEOUT:     int = 20_000
    SCROLL_WAIT_MS:      int = 600
    SCROLL_STEP_PX:      int = 400
    SCROLL_WRAPPER_CSS:  str = ".p-datatable-scrollable .p-datatable-wrapper"
    TABLE_ROW_SELECTOR:  str = "tbody.p-datatable-tbody > tr"
    TABLE_BODY_SELECTOR: str = "tbody.p-datatable-tbody"
    BADGE_CSS:           str = "span.badge-custom"
    FILTER_NAV_BTNS:     str = "button.filter-nav"
    BADGE_CONTAINER:     str = "div.filters-list"
    FILTER_COLUMN:       str = "Filter"
# ── colours ──────────────────────────────────────────────────────────
R="\033[91m"; G="\033[92m"; Y="\033[93m"; C="\033[96m"
W="\033[97m"; B="\033[1m";  DIM="\033[2m"; RS="\033[0m"
def c(t,col): return f"{col}{t}{RS}"
def bar(ch="─",w=110,col=C): print(c(ch*w,col))
def dbl(): print(c("-"*110,B))
def section(t): dbl(); print(c(f" -  {t}",B)); dbl()

# ── normaliser ───────────────────────────────────────────────────────
class N:
    _F = re.compile(r'^-?\d+\.\d+$')
    @classmethod
    def norm(cls, v) -> str:
        if v is None: return ""
        s = str(v).strip()
        if s.lower() in ("nan","none",""): return ""
        t = " ".join(s.replace(",","").lower().split())
        if cls._F.match(t):
            try:
                f = float(t)
                return str(int(f)) if f == int(f) else str(round(f,4))
            except ValueError: pass
        return t
if sys.platform == "win32":
       sys.stdout.reconfigure(encoding='utf-8')
def f2f(v) -> float:
    try: return float(str(v).replace(",","").strip())
    except: return 0.0

DASH = "-"

def is_dash(v) -> bool:
    return str(v).strip() == DASH

def _nh(h): return h.strip().lower().replace("_"," ").replace("-"," ")




# ======================================================
# EXCEL LOADER  <  CHANGED
# ======================================================
def load_excel(path, sheet, fcol):
    df = pd.read_excel(path, sheet_name=sheet)

    # normalised name → standard UI name
    norm_to_std = {_nh(k): k for k in ALL_UI_COLUMNS}

    # columns that must never be validated as UI fields
    skip_as_field: Set[str] = {_nh(s) for s in SECONDARY_FILTER_COLUMNS} | {_nh(fcol)}

    col_to_std: Dict[str, str] = {}
    for col in df.columns:
        n = _nh(col)
        if n in norm_to_std and n not in skip_as_field:
            col_to_std[col] = norm_to_std[n]

    active_fields = list(col_to_std.values())

    # find secondary filter columns that actually exist in the sheet
    sec_col_map: Dict[str, str] = {}   # excel_col_name → secondary filter value
    for col in df.columns:
        if _nh(col) in {_nh(s) for s in SECONDARY_FILTER_COLUMNS}:
            sec_col_map[col] = col     # keep actual column name for row.get()

    grouped: Dict[str, List[Dict]] = {}

    for _, row in df.iterrows():
        # ── primary filter (column Q) ────────────────────────────────
        fn = str(row.get(fcol, "")).strip()
        if not fn or fn in SKIP_FILTERS:
            continue

        rec = {std: N.norm(row[col]) for col, std in col_to_std.items()}

        # add to primary group
        grouped.setdefault(fn, []).append(rec)

        # ── secondary filters (columns O and P) ──────────────────────
        # If a secondary-filter cell is non-empty, the same row record
        # is ALSO added to that filter group.
        for sec_col in sec_col_map:
            raw_sec = row.get(sec_col, "")
            if pd.isna(raw_sec):
                continue
            sec_val = re.sub(r'[:\s]+$', '', str(raw_sec).strip())
            if sec_val and sec_val not in SKIP_FILTERS:
                if sec_val != fn:
                    grouped.setdefault(sec_val, []).append(rec)

    return grouped, active_fields


def print_load_summary(grouped, active_fields):
    print()
    for fn, rows in grouped.items():
        print(f"  {c('+',G)} Excel  {fn:<30}  {len(rows):>3} rows")
    print()
    bar("─", 60, DIM)
    print(f"  {c('Validating these fields',B)}  ({len(active_fields)}):")
    bar("─", 60, DIM)
    for fld in active_fields:                               
        print(f"  {c('+',G)}  {fld}")
    skipped = [f for f in ALL_UI_COLUMNS if f not in active_fields]
    if skipped:
        print()
        print(f"  {c('Skipped (not in Excel sheet)',Y)}  ({len(skipped)}):")
        for fld in skipped:
            print(f"  {c('⛔',Y)}  {fld}")
    bar("─", 60, DIM)
    print()

# ── UI row extraction ────────────────────────────────────────────────
_col_index: Dict[str, int] = {}

def refresh_column_index(page) -> None:
    """Map each field to its td index using the summary table's header row."""
    headers = [_nh(h) for h in page.locator("thead.p-datatable-thead th").all_inner_texts()]
    _col_index.clear()
    for fn in ALL_UI_COLUMNS:
        h = _nh(UI_HEADER_ALIASES.get(fn, fn))
        if h in headers:
            _col_index[fn] = headers.index(h)

def extract_row(row) -> Dict[str, str]:
    cells = row.locator("td")
    data  = {fn: "" for fn in ALL_UI_COLUMNS}
    for fn, idx in (_col_index or ALL_UI_COLUMNS).items():
        try:
            cell = cells.nth(idx)
            data[fn] = "yes" if fn == "Audited Image" and cell.locator("img").count() > 0 \
                             else N.norm(cell.inner_text())
        except:
            data[fn] = ""
    return data

def blank_row(r): return all(not v for v in r.values())

# ── badge count extraction ───────────────────────────────────────────
def _badge_label(badge) -> str:
    txt = " ".join(badge.inner_text().split()).strip()
    return re.sub(r"\s*\(\d+\)\s*$", "", txt).strip()

def _badge_count(badge) -> int:
    txt = " ".join(badge.inner_text().split()).strip()
    m   = re.search(r"\((\d+)\)\s*$", txt)
    return int(m.group(1)) if m else -1

# ── carousel navigation ──────────────────────────────────────────────
def _left_nav(page, cfg) -> None:
    while True:
        left = page.locator(cfg.FILTER_NAV_BTNS).first
        if left.is_disabled():
            break
        left.click()
        page.wait_for_timeout(300)

def _right_nav(page, cfg) -> bool:
    right = page.locator(cfg.FILTER_NAV_BTNS).last
    if right.is_disabled():
        return False
    right.click()
    page.wait_for_timeout(300)
    return True

def click_badge(page, cfg, filter_name: str) -> int:
    badges = page.locator(cfg.BADGE_CSS)
    count  = badges.count()

    for i in range(count):
        badge = badges.nth(i)
        if _badge_label(badge) == filter_name:
            row_count = _badge_count(badge)
            badge.click()
            page.wait_for_timeout(1000)
            print(f"  {c('> Badge clicked',G)}  {filter_name!r}  "
                  f"(count={c(str(row_count), Y)})")
            return row_count

    raise ValueError(
        f"Badge not found: '{filter_name}'\n"
        f"  Badges seen: {[_badge_label(badges.nth(i)) for i in range(count)]}"
    )

# ── scroll + collect ─────────────────────────────────────────────────
def scroll_and_collect(page, cfg, seen):
    wrapper = page.locator(cfg.SCROLL_WRAPPER_CSS).first
    collected, prev_top = [], -1

    def _grab():
        for i in range(wrapper.locator(cfg.TABLE_ROW_SELECTOR).count()):
            data = extract_row(wrapper.locator(cfg.TABLE_ROW_SELECTOR).nth(i))
            if blank_row(data): continue
            code = data.get("Item Code","")
            if code and code not in seen:
                seen.add(code); collected.append(data)

    _grab()
    while True:
        cur = wrapper.evaluate("el => el.scrollTop")
        if cur == prev_top: break
        prev_top = cur
        wrapper.evaluate(f"el => el.scrollTop += {cfg.SCROLL_STEP_PX}")
        page.wait_for_timeout(cfg.SCROLL_WAIT_MS)
        _grab()
    wrapper.evaluate("el => el.scrollTop = el.scrollHeight")
    page.wait_for_timeout(cfg.SCROLL_WAIT_MS)
    _grab()
    return collected

def collect_all(page, cfg) -> List[Dict]:
    try:
        page.wait_for_selector(
            cfg.TABLE_BODY_SELECTOR,
            state="visible",
            timeout=5_000
        )
    except Exception:
        print(f"  {c('⚠ No table body visible — 0 rows for this filter',Y)}")
        return []

    refresh_column_index(page)
    seen, all_rows = set(), []
    while True:
        all_rows.extend(scroll_and_collect(page, cfg, seen))
        try:
            nxt = page.locator("button.p-paginator-next")
            if nxt.count()==0 or "p-disabled" in (nxt.get_attribute("class") or ""): break
            nxt.click()
            page.wait_for_load_state("networkidle", timeout=10_000)
            page.wait_for_timeout(1200)
            page.wait_for_selector(cfg.TABLE_BODY_SELECTOR, timeout=cfg.DEFAULT_TIMEOUT)
        except: break
    return all_rows

# ── business rules ───────────────────────────────────────────────────
class BizRules:
    @staticmethod
    def matched_line_item(r):
        return f2f(r.get("Stock Quantity", 0)) == f2f(r.get("Audited Qty", 0))

    @staticmethod
    def excess(r):
        return f2f(r["Stock Quantity"])==0 and f2f(r["Audited Qty"])>0 and f2f(r["Variance"])>0

    @staticmethod
    def pos_line(r):
        return f2f(r["Stock Quantity"])>0 and f2f(r["Audited Qty"])>0 and f2f(r["Variance"])>0

    @staticmethod
    def not_found(r):
        return f2f(r["Stock Quantity"])>0 and f2f(r["Audited Qty"])==0

    @staticmethod
    def neg_line(r):
        return f2f(r["Stock Quantity"])>0 and f2f(r["Audited Qty"])>0 and f2f(r["Variance"])<0

    @staticmethod
    def pos_var(r):
        # NOTE: f2f("-") == 0.0, so an Un Verified row (Variance="-") never
        # satisfies this rule — Un Verified rows are excluded implicitly.
        return f2f(r["Variance"]) > 0

    @staticmethod
    def neg_var(r):
        # NOTE: f2f("-") == 0.0, so an Un Verified row (Variance="-") never
        # satisfies this rule — Un Verified rows are excluded implicitly.
        return f2f(r["Variance"]) < 0

    @staticmethod
    def location_conflict(r):
        stock   = N.norm(r.get("Stock Location",  ""))
        audited = N.norm(r.get("Audited Location", ""))
        qty     = f2f(r.get("Audited Quantity", r.get("Audited Qty", 0)))
        return qty > 0 and stock != audited

    @staticmethod
    def damaged_report(r):
        return f2f(r.get("Damaged Qty", 0)) > 0

    @staticmethod
    def un_verified(r):
        return (f2f(r.get("Audited Qty", 0)) == 0
                and is_dash(r.get("Variance", ""))
                and is_dash(r.get("Variance Value", ""))
                and is_dash(r.get("Variance Type", "")))

    @staticmethod
    def resolve(fn, row):
        if fn == FilterType.POSITIVE_VARIANCE.value:
            return FilterType.EXCESS_LINE_ITEM.value if f2f(row["Stock Quantity"])==0 \
                   else SubFilterType.POSITIVE_LINE_ITEM.value
        if fn == FilterType.NEGATIVE_VARIANCE.value:
            return FilterType.NOT_FOUND.value if f2f(row["Audited Qty"])==0 \
                   else SubFilterType.NEGATIVE_LINE_ITEM.value
        return fn

    _MAP = None
    def validators(self):
        if self._MAP is None:
            BizRules._MAP = {
                FilterType.MATCHED_LINE_ITEM.value:     self.matched_line_item,
                FilterType.NOT_FOUND.value:              self.not_found,
                FilterType.EXCESS_LINE_ITEM.value:      self.excess,
                FilterType.NEGATIVE_VARIANCE.value:     self.neg_var,
                FilterType.POSITIVE_VARIANCE.value:     self.pos_var,
                SubFilterType.NEGATIVE_LINE_ITEM.value: self.neg_line,
                SubFilterType.POSITIVE_LINE_ITEM.value: self.pos_line,
                FilterType.LOCATION_CONFLICT.value:     self.location_conflict,
                FilterType.DAMAGED_REPORT.value:        self.damaged_report,
                FilterType.UN_VERIFIED.value:           self.un_verified,
            }
        return self._MAP

    def check(self, fn, row):
        leaf = self.resolve(fn, row)
        vfn  = self.validators().get(leaf)
        if vfn is None: return None
        if not vfn(row):
            return (f"Rule=[{leaf}]  Stock={row.get('Stock Quantity')}  "
                    f"Audited={row.get('Audited Qty')}  Variance={row.get('Variance')}  "
                    f"DamagedQty={row.get('Damaged Qty')}  "
                    f"StockLoc={row.get('Stock Location')}  "
                    f"AuditedLoc={row.get('Audited Location')}")
        return None

# ── failure record ───────────────────────────────────────────────────
@dataclass
class Fail:
    filter_name: str; code: str; field: str
    expected: str;    actual: str; kind: str

# ── output ───────────────────────────────────────────────────────────
_WC=14; _WF=22; _WE=28; _WA=28

def _hdr():
    bar("─",100,DIM)
    print(f"  {'Status':<6}  {'Item Code':<{_WC}}  {'Field':<{_WF}}  "
          f"{c('Expected',C):<{_WE+10}}  {c('Actual',Y):<{_WA+10}}  Type")
    bar("─",100,DIM)

def pass_line(code): print(f"  {c('PASS',G)}  {code}")

def fail_line(code, fld, ev, av, kind):
    kc = R if kind in ("FIELD","BIZ") else Y
    print(f"  {c('FAIL',R)}  {code:<{_WC}}  {fld:<{_WF}}  "
          f"{c('exp',C)}={ev!r:<{_WE}}  {c('act',Y)}={av!r:<{_WA}}  [{c(kind,kc)}]")

DASH_FIELDS = {"Variance", "Variance Value", "Variance Type"}

def _field_eq(fld, ev, av) -> bool:
    if fld in DASH_FIELDS and (is_dash(ev) or is_dash(av)):
        return is_dash(ev) and is_dash(av)
    return av == ev

# ── engine ───────────────────────────────────────────────────────────
class Engine:
    def __init__(self, active_fields):
        self.active_fields = active_fields
        self.failures: List[Fail]  = []
        self.passes:   List[tuple] = []
        self._biz = BizRules()

    def _addf(self, *a): self.failures.append(Fail(*a))

    def compare(self, actual, expected, filter_name):
        amap   = {r["Item Code"].lower(): r for r in actual}
        emap   = {r["Item Code"].lower(): r for r in expected}
        is_all = (filter_name == FilterType.ALL.value)
        _hdr()

        for code, exp_row in emap.items():
            if code not in amap:
                fail_line(code,"—","row present","MISSING","MISSING")
                self._addf(filter_name,code,"—","row present","MISSING","MISSING")
                continue

            act_row = amap[code]; ok = True

            for fld in self.active_fields:
                if fld == "Item Code": continue
                ev = exp_row.get(fld, "")
                av = act_row.get(fld, "")
                if not _field_eq(fld, ev, av):
                    fail_line(code, fld, ev, av, "FIELD")
                    self._addf(filter_name, code, fld, ev, av, "FIELD")
                    ok = False

            biz = self._biz.check(filter_name, act_row)
            if biz:
                fail_line(code,"[BIZ RULE]","invariant ok",biz,"BIZ")
                self._addf(filter_name,code,"[BIZ RULE]","invariant ok",biz,"BIZ")
                ok = False

            if ok:
                pass_line(code); self.passes.append((filter_name, code))

        if not is_all:
            for code in amap:
                if code not in emap:
                    fail_line(code,"—","not in Excel","PRESENT IN UI","EXTRA")
                    self._addf(filter_name,code,"—","not in Excel","PRESENT IN UI","EXTRA")
        bar()

    def summary(self) -> bool:
        dbl(); print(c("  FINAL VALIDATION SUMMARY",B)); dbl()
        tp, tf = len(self.passes), len(self.failures)

        print(c(f"\n  +  PASSED ITEMS  ({tp})",G)); bar("─",70,G)
        if self.passes:
            prev=None
            for fn, code in self.passes:
                if fn!=prev: print(f"\n  {c(fn,C)}"); prev=fn
                print(f"    {c('PASS',G)}  {code}")
        else: print(f"    {c('(none)',DIM)}")

        print(c(f"\n  X  FAILED ITEMS  ({tf})",R)); bar("─",110,R)
        if self.failures:
            print(f"  {'#':<5}  {'Filter':<28}  {'Item Code':<16}  "
                  f"{'Field':<24}  {'Expected':<30}  {'Actual':<30}  Type")
            bar("─",110,R)
            prev=None
            for i,f in enumerate(self.failures,1):
                if f.filter_name!=prev:
                    if prev: print()
                    print(f"  {c(f.filter_name,C)}"); prev=f.filter_name
                kc = R if f.kind in ("FIELD","BIZ") else Y
                print(c(f"  {i:<5}  {'':28}  {f.code:<16}  {f.field:<24}  "
                         f"{f.expected[:30]:<30}  {f.actual[:30]:<30}  {f.kind}", kc))

            print(); bar("─",70,R)
            counts: Dict[str,Dict[str,int]] = {}
            for f in self.failures:
                counts.setdefault(f.filter_name,{})
                counts[f.filter_name][f.kind] = counts[f.filter_name].get(f.kind,0)+1
            print(f"  {'Filter':<28}  {'FIELD':>6}  {'MISSING':>7}  {'EXTRA':>5}  {'BIZ':>4}  {'TOTAL':>6}")
            sep=f"  {'─'*28}  {'─'*6}  {'─'*7}  {'─'*5}  {'─'*4}  {'─'*6}"
            print(sep); grand=0
            for fn,kc in counts.items():
                t=sum(kc.values()); grand+=t
                print(f"  {fn:<28}  {kc.get('FIELD',0):>6}  {kc.get('MISSING',0):>7}  "
                      f"{kc.get('EXTRA',0):>5}  {kc.get('BIZ',0):>4}  {c(str(t),R):>6}")
            print(sep)
            print(f"  {'TOTAL':<28}  {'':>6}  {'':>7}  {'':>5}  {'':>4}  {c(str(grand),R):>6}")
        else: print(f"    {c('(none)',DIM)}")

        print(); dbl()
        if not self.failures:
            print(f"  {c('+  ALL VALIDATIONS PASSED',G)}  ({tp} items checked)")
        else:
            print(f"  {c('X  VALIDATION FAILED',R)}     PASS={c(str(tp),G)}    FAIL={c(str(tf),R)}")
        dbl()
        return not self.failures


def select_navigation_option(page, option_name: str):
        """
        option_name: one of 'Stock Audit', 'Audit Summary', 'Settings'
        """
        dialog = page.locator("div[role='dialog'][aria-labelledby='auditNavTitle']")
        try:
            dialog.first.wait_for(state="visible", timeout=15000)
        except Exception:
            # A user who is only an auditor (not the owner) goes straight to the Stock Audit page: no choice dialog
            landed = {"Stock Audit": "/stock", "Audit Summary": "/auditSummary"}.get(option_name)
            if landed and landed in page.url:
                print(f"   No choice dialog: {option_name} opened directly")
                return
            raise

        card = page.locator(
            f"button.create-type-card:has(h6.create-type-card__title:text-is('{option_name}'))"
        )
        card.click()

        # Older builds asked to confirm with "Continue"; the current one navigates directly
        cont = page.locator("button.create-type-btn--primary:has-text('Continue')")
        try:
            cont.wait_for(state="visible", timeout=1500)
            cont.click()
        except Exception:
            pass

        if option_name == "Audit Summary":
            page.wait_for_url("**/auditSummary", timeout=20000)
            # Badges and totals render as "(0)" before the data arrives; wait for the
            # status and the All badge (an audit with no lines just waits out the timeout)
            try:
                page.wait_for_function(
                    """() => {
                        const status = document.querySelector('app-audit-summary div.status-pill');
                        const all = document.querySelector('app-audit-summary span.badge-custom');
                        return status && status.innerText.trim() !== 'Unknown'
                            && all && !/\\(0\\)\\s*$/.test(all.innerText.trim());
                    }""", timeout=30000)
            except Exception:
                pass
def wait_spinner(page, timeout=90000):
    """The loading spinner's backdrop takes every click until the data has arrived."""
    try:
        page.wait_for_selector("app-spinner div.backdrop", state="hidden", timeout=timeout)
    except Exception:
        pass

def select_branch(page, branch):
    wait_spinner(page)
    dd = page.locator('xpath=//div[@data-tour-id="header-branch"]//p-dropdown').first
    dd.locator(".p-dropdown-label").click()
    panel = page.locator(".p-dropdown-panel").last
    panel.wait_for(state="visible")
    inp = panel.locator("input.p-dropdown-filter")
    if inp.count()>0: inp.fill(branch)
    panel.locator("li.p-dropdown-item", has_text=branch).first.click()
    panel.wait_for(state="hidden")

def audit_row(page, ap_audit_name):
    """The audit's row in the audit list. Long names are shown truncated ("QA_FC_explore_1..."),
    the full name is the cell's title; a recount adds a second row with the same name
    (Type "Recount Audit") that opens the recount screen instead."""
    rows = page.locator("table tbody tr").filter(has=page.locator(f"td[title='{ap_audit_name}']"))
    if rows.count() == 0:
        rows = page.locator("table tbody tr").filter(
            has=page.locator("button.audit-name-link", has_text=ap_audit_name))
    main = rows.filter(has_not_text="Recount Audit")
    return main.first if main.count() else rows.first

def click_audit(page, ap_audit_name):
    try:
        page.wait_for_load_state("networkidle", timeout=10000)   # the list keeps polling at times
    except Exception:
        pass
    wait_spinner(page)
    page.wait_for_selector("button.audit-name-link", timeout=30000)
    audit_row(page, ap_audit_name).locator("button.audit-name-link").click()
    print(f"   Opened audit: {ap_audit_name}")

def navigate_to_audit(page, config):
    """The audit's Audit Summary: looked up in Ongoing Audits, else Audit History (a completed audit
    opens straight to the summary, without the Stock Audit / Audit Summary choice)."""
    _ui_open_summary(page, config)


def A_audit_Summary(page, config, is_history: bool = False):
    """Audit Summary flexible formula-based validation:
    - Pre-complete (Ongoing): validates UI fields, values, cards, chips, charts & live Excel export.
    - Post-complete (Audit History): validates Completed status, read-only controls, PDF download & Excel export.
    Read-only: never modifies the audit."""
    if getattr(config, "summary_ui_validation", True):
        return validate_summary_ui(page, config, label="History" if is_history else "UI")
    return True


def _excel_compare(page, config):
    """Rows of each filter badge compared with the 'auditSummary' Excel sheet."""
    cfg = Config()

    section("LOADING EXCEL DATA")
    grouped, active_fields = load_excel(config.EXCEL_PATH, config.EXCEL_SHEET_audit_Summary, config.FILTER_COLUMN)
    print_load_summary(grouped, active_fields)
    navigate_to_audit(page, config)
    engine = Engine(active_fields=active_fields)

    for filter_name in UI_FILTERS:
            section(f"FILTER  >  {filter_name}")

            badge_count = click_badge(page, cfg, filter_name)

            if badge_count == 0:
                print(f"  {c('    Skipping — badge count is 0',DIM)}\n")
                continue

            actual = collect_all(page, cfg)

            merge_keys = FILTER_MERGE_MAP.get(filter_name, [filter_name])
            exp: List[Dict] = []
            for key in merge_keys:
                exp.extend(grouped.get(key, []))

            print(f"\n  {c('UI',C)} = {len(actual)} rows    {c('Excel',G)} = {len(exp)} rows", end="")
            if len(merge_keys) > 1:
                merged_info = " + ".join(f"{c(k,Y)}({len(grouped.get(k,[]))})" for k in merge_keys)
                print(f"   {c('<  merged:',DIM)} {merged_info}", end="")
            print("\n")

            engine.compare(actual, exp, filter_name)

    

    # Return the result (like Q_audit_Summary) instead of sys.exit(), so the
    # runner records pass/fail and continues with the next module.
    return engine.summary()


# ======================================================================
# AUDIT SUMMARY — UI VALIDATION (flexible fields and formulas)
# ======================================================================
# Everything the checks compare against is DATA in the block below: to add or drop a field,
# rename a label or change a formula, edit the block — not the code under it.
#   * Field lists = the user's required fields (2026-11-11).
#   * Formulas are Python expressions in strings. They may use only min / max / round / abs / sum /
#     len / round_half_up and the names given in each block's comment.
#   * Rules come from the spec in audit/skill_audit/ (00-README, 01, 02, 03).
#   * Status: PASS / FAIL (the page differs from the rule: a new problem) /
#     KNOWN (a defect the spec already lists, with its finding number; no bug card) / NOT RUN.

UI_SUMMARY = "app-audit-summary"

REQUIRED_FIELDS = OrderedDict([
    ("Audit Information", ["Audit Name", "Date & Time", "Auditor(s)", "Group", "Audit Type", "Frequency",
                           "Mapping Type", "Progress", "Status"]),
    ("Audit Summary Counts", ["All", "Matched Line Item", "Unverified", "Not Found", "Excess Line Item",
                              "Positive Variance", "Negative Variance", "Location Conflict",
                              "Cross Checked Audit", "Damaged Report"]),
    ("Quantity Summary", ["Stock Quantity", "Audited Quantity", "Damaged Quantity"]),
    ("Audit Report - Table Fields", ["S.No", "Item Code", "Item Name", "Category", "Stock Location",
                                     "Audited Location", "UOM (Primary)", "Stock Quantity", "Audited Quantity",
                                     "Variance", "Variance Value", "Variance Type", "Variance History",
                                     "Damaged Qty", "Auditor", "Audited Date", "Audited Image",
                                     "Cross Audited Qty", "Cross Damaged Qty", "Declaration Note", "Coordinates",
                                     "Resolution Status", "Remarks"]),
    ("Summary Options", ["Item", "Auditor", "Location", "UOM"]),
    ("Actions", ["Stock Audit", "Auditor Insights", "Archive", "Complete Audit", "Download PDF", "Export",
                 "Copy Table", "Reopen Audit"]),
    ("Charts", ["Available Value", "Stock Loss", "Excess Value"]),
])

# Labels are matched ignoring case, spaces and punctuation ("Un Verified" = "Unverified",
# "Cross AuditedQty" = "Cross Audited Qty", "Download Pdf" = "Download PDF", "Available  Value" =
# "Available Value"). Only names that differ in words need an alias.
LABEL_ALIASES = {
    "Stock Quantity": ["Stock"],                 # Quantity Summary cards are labelled Stock / Audited / Damaged
    "Audited Quantity": ["Audited"],
    "Damaged Quantity": ["Damaged"],
    "Copy Table": ["Copy table — paste into Excel"],
    "UOM (Primary)": ["UOM (Base)", "UOM"],
}
SPLIT_TILES = {"Frequency - Mapping Type": ("Frequency", "Mapping Type")}     # one tile, two fields
STATUS_LABELS = ["Not Started", "Stock Sheet Updated", "In Progress", "In Resolution", "Completed",
                 "Auto Completed", "Expired"]                                  # spec 01 §5 ("Unknown" = a defect)
MAPPING_TYPES = ["Random", "ByCategory", "ByStorage", "ByLocation"]
DATE_FORMATS = {"Date & Time": "%Y-%m-%d %H:%M", "Audited Date": "%m-%d-%y %H:%M"}
TOLERANCE = 0.05                                                               # money / quantity rounding

# One report row of an AUDITED line item. Names: stock, audited, damaged, price (CostPrice of the item in the
# export). Line items that were not audited are checked by NOT_AUDITED_EXPECT instead.
ROW_FORMULAS = OrderedDict([
    ("Variance", "audited - stock"),                                           # damaged qty not included
    ("Variance Value", "(audited - stock) * price"),
    ("Variance Type", "'Positive' if audited > stock else 'Negative' if audited < stock else '-'"),
])

# Line items NOT audited = the Un Verified items (user rule, 2026-11-12): only line items with a real count
# show auditor details, an audited date and a variance.
#   Which rows: the rows the NOT_AUDITED_CHIP chip lists; when that list was not read, the rows meeting
#   CHIP_RULES[NOT_AUDITED_CHIP].
#   NOT_AUDITED_EXPECT: field -> (rule every not-audited row must meet, related spec finding).
#   AUDITED_EXPECT: field -> rule every audited row must meet.
#   Names: as in CHIP_RULES, plus audited_date, variance, variance_value, variance_type.
NOT_AUDITED_CHIP = "Unverified"
NOT_AUDITED_EXPECT = OrderedDict([
    ("Audited Quantity", ("audited == 0", "")),
    ("Auditor", ("auditor == ''", "")),
    ("Audited Date", ("audited_date == ''", "")),
    ("Variance", ("variance == 0", "03 F12")),
    ("Variance Value", ("variance_value == 0", "03 F12")),
    ("Variance Type", ("variance_type in ('-', 'Not Audited')", "03 F12")),
])
AUDITED_EXPECT = OrderedDict([
    ("Auditor", "auditor != ''"),
    ("Audited Date", "audited_date != ''"),
])

# Move to Not Found (spec 03 §3.1 steps 6-9, §3.2, findings 8 / 26): Complete Audit > Yes > "Unverified items"
# > Move to Not Found > Proceed to Resolution, then the summary is read again. The moved rows are the rows the
# Un Verified chip listed before.
#   MOVE_NOT_FOUND_POPUP: the step-2 count. Names: popup (N in "There are N items not counted"), before.
#   MOVE_NOT_FOUND_CHIPS: chip -> count after the move. Names: before (chip counts before), moved (rows moved).
#   MOVE_NOT_FOUND_EXPECT: field -> (PASS rule, KNOWN rule or None, spec finding) for every moved row; a row
#   meeting neither rule is a FAIL. Names: as in CHIP_RULES plus audited_date, variance, variance_type,
#   resolution_status, completer (the logged-in user who completed).
MOVE_NOT_FOUND_STATUS = "In Resolution"                   # status after Proceed to Resolution
MOVE_NOT_FOUND_POPUP = "popup == before['Unverified']"    # N = items on the Un Verified list
MOVE_NOT_FOUND_CHIPS = OrderedDict([
    ("Unverified", "0"),
    ("Not Found", "before['Not Found'] + moved"),
    ("Negative Variance", "before['Negative Variance'] + moved"),
    ("All", "before['All']"),
])
MOVE_NOT_FOUND_EXPECT = OrderedDict([
    ("Audited Quantity", ("audited == 0", None, "")),
    ("Damaged Qty", ("damaged == 0", None, "")),
    ("Auditor", ("auditor == ''", "auditor == completer", "03 F26")),   # the server names the completer
    ("Audited Location", ("audited_location == stock_location", None, "")),
    ("Audited Date", ("audited_date != ''", None, "")),
    ("Variance", ("variance == -stock", None, "")),
    ("Variance Type", ("variance_type == 'Negative'", None, "")),
    ("Resolution Status", ("resolution_status == 'Pending'", None, "")),
])
# "Keep as Unverified" (same step, other choice): the items stay Un Verified, are left out of Resolution
# (spec 03 §3.1 step 7) and keep the Not Audited rule (NOT_AUDITED_EXPECT).
KEEP_UNVERIFIED_CHIPS = OrderedDict([
    ("Unverified", "before['Unverified']"),
    ("Not Found", "before['Not Found']"),
    ("Negative Variance", "before['Negative Variance']"),
    ("All", "before['All']"),
])
KEEP_UNVERIFIED_EXPECT = OrderedDict([
    ("Audited Quantity", ("audited == 0", None, "")),
    ("Auditor", ("auditor == ''", None, "")),
    ("Audited Date", ("audited_date == ''", None, "")),
    ("Variance", ("variance == 0", None, "03 F12")),
    ("Variance Type", ("variance_type in ('-', 'Not Audited')", None, "03 F12")),
    ("Resolution Status", ("resolution_status == ''", None, "")),
])
# The popup choice comes from config.complete_choice; its rules: choice -> (chips after, rows after)
UNVERIFIED_CHOICE_RULES = {
    "Move to Not Found": (MOVE_NOT_FOUND_CHIPS, MOVE_NOT_FOUND_EXPECT),
    "Keep as Unverified": (KEEP_UNVERIFIED_CHIPS, KEEP_UNVERIFIED_EXPECT),
}

# Audit Information > Progress (spec 00 / 01 §3). Names: counted_codes (item codes with audited > 0,
# off-sheet items included), stock_rows (stock-sheet rows = "Total Line Item" of the audit list row),
# audited_total, damaged_total, stock_total (the Qty cards).
PROGRESS_FORMULA = ("min(100, (counted_codes / stock_rows * 25 if stock_rows else 0)"
                    " + ((audited_total + damaged_total) / stock_total * 75 if stock_total else 0))")
PROGRESS_LABEL = "min(100, round_half_up(progress))"                           # the "n% Completed" text

# Quantity Summary: card = Σ of the first formula over the Item view rows (Qty), Σ of the second (Value).
CARD_FORMULAS = OrderedDict([
    ("Stock Quantity", ("stock", "stock * price")),
    ("Audited Quantity", ("audited", "audited * price")),
    ("Damaged Quantity", ("damaged", "damaged * price")),
])

# Auditor Insights (spec 01 §4): Σ of each formula over the report rows of one auditor (Summarize As = Auditor).
# Names: as in CHIP_RULES plus price. Progress names: counted_rows (the auditor's rows with audited > 0),
# completed (Completed Inventory), assigned_rows / assigned_stock (the auditor's stock-sheet rows and their
# Σ stock: known from the Summary only when one auditor has every row). Status names: counted_rows, status.
AUDITOR_FORMULAS = OrderedDict([
    ("Completed Inventory", "audited"),          # damaged excluded
    ("Audited Value", "audited * price"),        # spec 01 F4: the server's cost may differ from CostPrice
    ("Damaged Value", "damaged * price"),
])
AUDITOR_PROGRESS_FORMULA = ("min(100, (counted_rows / assigned_rows * 25 if assigned_rows else 0)"
                            " + (completed / assigned_stock * 75 if assigned_stock else 0))")
AUDITOR_STATUS_RULE = ("status in ('In Progress', 'Completed') if counted_rows > 0"
                       " else status in ('Yet to Start', 'Completed', 'Unknown')")   # Completed: the auditor finished
# An auditor who pressed Finish Audit (Config.finished_auditors) must show Status Completed + Action Reopen
# (user, 2026-11-17); AUDITOR_STATUS_RULE is only for auditors not known to have finished.


def _auditor_finished(label, finished) -> bool:
    """Auditor Insights row name (full name, may be cut at 20 chars) is one of the finished auditors' names."""
    n = _txt(label).lower().rstrip(".… ")
    return bool(n) and any(f == n or (len(n) >= 15 and f.startswith(n)) for f in finished)
# Per-auditor progress inputs come from the dialog's API response (returned, not shown; spec 01 §4):
# counted_rows = AuditedCount, assigned_stock = AssignedInventoryCount, assigned_rows = the on-sheet rows the
# auditor counted + RemainingCount (the assigned rows the auditor has not counted).
AUDITOR_API = "GetAuditorSummary"
# Random mapping (spec 01 §4): the stock rows nobody counted are split evenly, the remainder to the last auditor.
# Names: uncounted (stock rows meeting RANDOM_UNCOUNTED), auditors, last (the last auditor of the dialog).
RANDOM_UNCOUNTED = "stock > 0 and audited == 0"
RANDOM_SLICE = "uncounted // auditors + (uncounted % auditors if last else 0)"

# Count chips (spec 03 §3, count rules). Names: stock, audited, damaged, auditor ('' when none),
# stock_location, audited_location ('' when blank or '-'), cross_audited.
CHIP_RULES = OrderedDict([
    ("All", "True"),
    ("Matched Line Item", "audited == stock"),
    ("Unverified", "stock > 0 and audited == 0 and auditor == ''"),
    ("Not Found", "stock > 0 and audited == 0 and auditor != ''"),
    ("Excess Line Item", "stock == 0 and audited > 0"),
    ("Positive Variance", "audited > stock"),
    ("Negative Variance", "auditor != '' and audited < stock"),
    ("Location Conflict", "audited > 0 and stock_location != audited_location"),
    ("Cross Checked Audit", "cross_audited > 0"),
    ("Damaged Report", "damaged > 0"),
])
# Chips whose count rule and list rule differ in the spec (03 §3): when the list differs from the count
# under this condition, the check is KNOWN with the finding. Names: count, listed, resolution (the audit
# has resolution rows: In Resolution / Completed / Auto Completed).
CHIP_LIST_DIFFS = {
    "Matched Line Item": ("03 F9", "resolution and listed < count"),   # resolution rows joined on ItemCode only
    "Unverified": ("03 F8", "listed > count"),                         # list also takes zero-stock rows
    "Excess Line Item": ("03 §3", "listed < count"),                   # list takes off-sheet rows only
}

# Charts (spec 02): per item code, quantities netted across locations. Names: stock, audited, auditor,
# stock_location, max_cost (highest CostPrice of the item), on_sheet, counted, cost, value, stock_value.
CHART_ITEM_RULES = OrderedDict([
    ("counted", "auditor != '' or audited > 0"),          # has a count row; uncounted items are skipped (F2)
    ("on_sheet", "stock_location != '' or stock > 0"),     # the item has a stock-sheet row
    ("cost", "max_cost"),                                  # highest cost of the item (from stock sheet or item master)
])
CHART_FORMULAS = OrderedDict([
    ("Available Value", "min(stock, audited) * cost"),
    ("Stock Loss", "max(stock - audited, 0) * cost"),
    ("Excess Value", "max(audited - stock, 0) * cost"),
])
STOCK_VALUE_FORMULA = "stock * cost"                       # doughnut denominator: every on-sheet item
DOUGHNUT_FORMULA = "min(100, round(value / stock_value * 100, 2)) if stock_value > 0 else 0"

# Summary Options: what each Summarize As option must do to the report table (spec 03 §1, §5).
#   key: columns that identify one row; add / drop: columns compared with the Item view;
#   stock: "same" = each row shows the item's whole stock, "sum" = the rows add up to it.
MODE_SPEC = OrderedDict([
    ("Item", {"key": ["Item Code"], "add": [], "drop": [], "stock": "same"}),
    ("Auditor", {"key": ["Item Code", "Auditor"], "add": [], "drop": [], "stock": "same"}),
    ("Location", {"key": ["Item Code", "Stock Location", "Audited Location"], "add": [],
                  "drop": ["Variance History"], "stock": "sum"}),
    ("UOM", {"key": ["Item Code"], "add": ["Audited UOM", "Default UOM", "Audited Qty in Default UOM"],
             "drop": [], "stock": "same"}),
])

# Actions (spec 01 §1, 03 §8). where: top = header buttons, table = buttons above the table,
# menu = the ⋮ menu. show / disabled: expressions over status (the Status tile) and rows.
# check: what is done beyond "shown": open (dialog opened and closed), xlsx / pdf (downloaded and
# read), clipboard (copied and read). Nothing that changes the audit is ever clicked.
DONE = "status in ('Completed', 'Auto Completed')"
ACTION_RULES = OrderedDict([
    ("Stock Audit", {"where": "top", "show": "True"}),
    ("Auditor Insights", {"where": "top", "show": "True", "check": "auditor_insights"}),
    ("Archive", {"where": "top", "show": "status != 'Archived'"}),
    ("Complete Audit", {"where": "top", "show": "status != 'Archived'", "disabled": DONE}),
    ("Download PDF", {"where": "table", "show": DONE, "check": "pdf"}),
    ("Export", {"where": "table", "show": "rows > 0", "check": "xlsx"}),
    ("Copy Table", {"where": "table", "show": "rows > 0", "check": "clipboard"}),
    ("Reopen Audit", {"where": "menu", "show": DONE}),
])
# Download PDF: besides "a PDF that names the audit and lists every item", these figures are read from
# its text and shown in the result for review (the spec does not describe this PDF's sections).
PDF_FIGURES = OrderedDict([
    ("Audit Name", r"Audit Name\s*:\s*(\S+)"),
    ("Verified (counted)", r"VERIFIED \(COUNTED\)\s*([\d.,]+\s*units)"),
    ("lines counted", r"([\d.,]+)\s*lines counted"),
    ("Accepted", r"Accepted\s*\((\d+)\)"),
    ("Investigate", r"Investigate\s*\((\d+)\)"),
    ("Matched Items", r"Matched Items\s*\((\d+)\)"),
    ("Not counted (Unverified)", r"NOT COUNTED \(UNVERIFIED\)\s*(\d+)"),
])

# Spec findings (known defects). KNOWN when the condition holds on this audit, else PASS ("not seen").
# Names: see _ui_facts().
KNOWN_FINDINGS = [
    ("02 F5", "Counted items not on the stock sheet are worth 0 in the charts", "len(off_sheet_counted) > 0"),
    ("02 F1", "Doughnut is drawn from the % values, which do not add up to 100", "abs(doughnut_sum - 100) > 1"),
    ("03 F7", "Location Conflict counts Unverified and Excess rows", "conflict_unverified_or_excess > 0"),
    ("03 F13", "Export has no sheet for the Not Found chip", "export_read and not export_not_found_sheet"),
]   # 03 F12 (Un Verified rows with a variance) is a FAIL of the NOT_AUDITED_EXPECT rule


# ----------------------------------------------------------------------
# formula evaluation and small helpers
# ----------------------------------------------------------------------
def round_half_up(x):
    return math.floor(float(x) + 0.5)


_SAFE = {"min": min, "max": max, "round": round, "abs": abs, "sum": sum, "len": len,
         "round_half_up": round_half_up}


def _calc(expr, **names):
    """Evaluate one formula string of the data block."""
    return eval(expr, {"__builtins__": {}}, {**_SAFE, **names})


def _key(text):
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def _txt(text):
    return " ".join(str(text or "").split())


def _blank(v):
    v = _txt(v)
    return "" if v in ("", "-", "--") else v


_MONEY_NAMES = {"price", "cost", "max_cost", "value", "stock_value", "audited_val", "damaged_val"}


def _show(expr, **names):
    """A formula of the data block with the numbers put in: '(audited - stock) * price' -> '(13 - 10) * 100.00'.
    Only the given names are replaced (name['key'] too, for dict values); quoted labels and keywords stay."""
    def put(m):
        name, sub = m.group(1), m.group(2)
        if name not in names:
            return m.group(0)
        v = names[name]
        if sub and isinstance(v, dict):
            v = v.get(sub[2:-2])
        elif sub or isinstance(v, (dict, list, set, tuple)):
            return m.group(0)
        if isinstance(v, str):
            return repr(v)
        if v is None or isinstance(v, bool):
            return str(v)
        return f"{float(v):.2f}" if name in _MONEY_NAMES else f"{float(v):.4f}".rstrip("0").rstrip(".")
    return re.sub(r"(?<!['\w])([A-Za-z_]\w*)(\['[^']*'\])?(?!['\w])", put, expr)


def _sample(items, n=6, sep=", "):
    """The first n items joined, '(+k more)' after them."""
    items = [str(x) for x in items]
    return sep.join(items[:n]) + (f" (+{len(items) - n} more)" if len(items) > n else "")


def _fmt_field(field, x):
    """A report value as the screen shows it: money with 2 decimals, quantities signed, labels as they are."""
    if isinstance(x, str) or x is None:
        return str(x)
    return f"{x:+.2f}" if "value" in _key(field) else f"{x:+g}"


def _row_sample(field, rule, v, want):
    """One row of a per-row formula: 'ITM2: (13 - 10) * 100.00 = +300.00', 'ITM9: 0 vs 10 → Negative'."""
    if isinstance(want, str):
        return f"{v['code']}: {v['audited']:g} vs {v['stock']:g} → {want}"
    return f"{v['code']}: {_show(rule, **v)} = {_fmt_field(field, want)}"


def _qn(v):
    """Number shown on screen ("+3", "1,234.5", "-" -> 0)."""
    m = re.match(r"^[-+]?\d+(\.\d+)?", _txt(v).replace(",", ""))
    return float(m.group()) if m else 0.0


def _near(a, b, tol=TOLERANCE):
    return a is not None and b is not None and abs(float(a) - float(b)) <= max(tol, abs(float(b)) * 1e-4)


def _find(required, labels):
    """The label on screen that matches a required name (case, spaces, punctuation ignored; aliases)."""
    wanted = {_key(required)} | {_key(a) for a in LABEL_ALIASES.get(required, [])}
    return next((l for l in labels if _key(l) in wanted), None)


def _cell(row, required):
    label = _find(required, list(row.keys()))
    return row.get(label, "") if label else ""


def _row_vals(r, prices=None):
    """Named values of one report row for the formulas."""
    code = _txt(_cell(r, "Item Code"))
    return {"code": code, "stock": _qn(_cell(r, "Stock Quantity")), "audited": _qn(_cell(r, "Audited Quantity")),
            "damaged": _qn(_cell(r, "Damaged Qty")), "auditor": _blank(_cell(r, "Auditor")),
            "stock_location": _blank(_cell(r, "Stock Location")),
            "audited_location": _blank(_cell(r, "Audited Location")),
            "cross_audited": _qn(_cell(r, "Cross Audited Qty")),
            "variance": _qn(_cell(r, "Variance")), "variance_value": _qn(_cell(r, "Variance Value")),
            "variance_type": _blank(_cell(r, "Variance Type")) or "-",
            "audited_date": _blank(_cell(r, "Audited Date")),
            "price": (prices or {}).get(code.upper())}


def _not_audited(v, not_audited_codes):
    """True when the row's line item was not audited, i.e. is an Un Verified item (see NOT_AUDITED_EXPECT):
    its code is in the list the NOT_AUDITED_CHIP chip shows, or, without that list, it meets the chip's rule.
    In location-split views, a row with audited == 0 and no auditor is an uncounted (unverified) location row."""
    if v.get("audited") == 0 and not v.get("auditor"):
        return True
    if not_audited_codes is not None:
        return v["code"].upper() in not_audited_codes
    return bool(_calc(CHIP_RULES[NOT_AUDITED_CHIP], **v))


def _parse_date(text, fmt):
    try:
        return datetime.strptime(_txt(text), fmt)
    except ValueError:
        return None


# ----------------------------------------------------------------------
# expected values (pure: rows in, numbers out — tested offline)
# ----------------------------------------------------------------------
def _expected_chips(item_rows):
    vals = [_row_vals(r) for r in item_rows]
    return OrderedDict((chip, sum(1 for v in vals if _calc(rule, **v))) for chip, rule in CHIP_RULES.items())


def _expected_progress(item_rows, stock_rows, cards):
    counted = len({v["code"].upper() for v in map(_row_vals, item_rows) if v["audited"] > 0})
    names = {"counted_codes": counted, "stock_rows": stock_rows or 0,
             "audited_total": cards.get("Audited", 0.0), "damaged_total": cards.get("Damaged", 0.0),
             "stock_total": cards.get("Stock", 0.0)}
    progress = _calc(PROGRESS_FORMULA, **names)
    return progress, _calc(PROGRESS_LABEL, progress=progress), names


def _expected_auditors(rows, prices, dialog_names):
    """{dialog name: Σ of AUDITOR_FORMULAS over that auditor's report rows, counted_rows, codes}.
    A row belongs to an auditor when the names contain each other (case, spaces ignored); a value is
    None when a row has no price."""
    vals = [_row_vals(r, prices) for r in rows]
    out = OrderedDict()
    for name in dialog_names:
        k = _key(name)
        mine = [v for v in vals if _key(v["auditor"]) and k and (_key(v["auditor"]) in k or k in _key(v["auditor"]))]
        used = [v for v in mine if v["audited"] or v["damaged"]]          # rows that add to a figure
        on_sheet = [v for v in mine if v["audited"] > 0 and v["stock"] > 0]
        e = {"counted_rows": sum(1 for v in mine if v["audited"] > 0), "vals": used,
             "on_sheet_counted": len(on_sheet), "on_sheet_stock": sum(v["stock"] for v in on_sheet)}
        for field, rule in AUDITOR_FORMULAS.items():
            e[field] = (None if "price" in rule and any(v["price"] is None for v in used)
                        else sum(_calc(rule, **v) for v in used))
        out[name] = e
    return out


def _api_records(body, key="auditorname"):
    """The first list of objects in a JSON body whose objects have the key (case, punctuation ignored),
    each object with its keys as _key() names."""
    if isinstance(body, list) and body and isinstance(body[0], dict) and any(_key(k) == key for k in body[0]):
        return [{_key(k): v for k, v in rec.items()} for rec in body if isinstance(rec, dict)]
    for v in (body.values() if isinstance(body, dict) else body if isinstance(body, list) else []):
        found = _api_records(v, key)
        if found:
            return found
    return []


def _api_auditor(records, name):
    """The API record of the auditor shown as name (the dialog may shorten the name)."""
    k = _key(name)
    return next((rec for rec in records if k and _key(rec.get("auditorname")) == k), None) or next(
        (rec for rec in records if k and _key(rec.get("auditorname")) and
         (k in _key(rec.get("auditorname")) or _key(rec.get("auditorname")) in k)), None)


def _expected_charts(item_rows, prices):
    """(bar {category: {dataset: value}}, overall {dataset: value}, doughnut {dataset: %}, facts)."""
    items = OrderedDict()
    for r in item_rows:                                   # net per item code (spec 02 §0)
        v = _row_vals(r)
        e = items.setdefault(v["code"].upper(), {"stock": 0.0, "audited": 0.0, "auditor": "",
                                                 "stock_location": "", "category": _txt(_cell(r, "Category"))})
        e["stock"] += v["stock"]
        e["audited"] += v["audited"]
        e["auditor"] = e["auditor"] or v["auditor"]
        e["stock_location"] = e["stock_location"] or v["stock_location"]
    bar, overall, stock_value, off_sheet = OrderedDict(), dict.fromkeys(CHART_FORMULAS, 0.0), 0.0, []
    for code, e in items.items():
        names = dict(e, max_cost=prices.get(code) or 0.0)
        for k, rule in CHART_ITEM_RULES.items():
            names[k] = _calc(rule, **names)
        if names["on_sheet"]:
            stock_value += _calc(STOCK_VALUE_FORMULA, **names)
        if not names["counted"]:
            continue
        if not names["on_sheet"] and e["audited"] > 0:
            off_sheet.append(code)
        cat = bar.setdefault(e["category"] or "-", dict.fromkeys(CHART_FORMULAS, 0.0))
        for ds, rule in CHART_FORMULAS.items():
            value = _calc(rule, **names)
            cat[ds] += value
            overall[ds] += value
    total_val = sum(overall.values())
    pie = OrderedDict((ds, _calc(DOUGHNUT_FORMULA, value=v, stock_value=total_val)) for ds, v in overall.items())
    return bar, overall, pie, {"stock_value": stock_value, "total_variance": total_val, "off_sheet_counted": off_sheet}


# ----------------------------------------------------------------------
# reading the page (read-only)
# ----------------------------------------------------------------------
_UI_ROWS_JS = """(tbody) => [...tbody.querySelectorAll(':scope > tr')].map(tr =>
    [...tr.querySelectorAll(':scope > td')].map(td => {
        const t = (td.innerText || '').trim();
        return !t && td.querySelector('img') ? '[image]' : t; }))"""
_UI_CHARTS_JS = """() => [...document.querySelectorAll('app-audit-summary p-chart')].map(pc => {
    const card = pc.closest('.cardDetail'); let cmp = null;
    try { cmp = window.ng ? window.ng.getComponent(pc) : null; } catch (e) {}
    return {card: card ? card.className : '', data: cmp && cmp.data ? JSON.parse(JSON.stringify(cmp.data)) : null};
})"""
_UI_LOADED_JS = """() => {
    const status = document.querySelector('app-audit-summary div.status-pill');
    const all = document.querySelector('app-audit-summary span.badge-custom');
    return status && status.innerText.trim() !== 'Unknown' && all && !/\\(0\\)\\s*$/.test(all.innerText.trim());
}"""
_UI_SUMMARIZE = f"{UI_SUMMARY} h6:has-text('Summarize As') ~ p-dropdown"
_UI_PANEL_LI = ".p-dropdown-panel:visible li.p-dropdown-item"


def _ui_settle(page, ms=1200):
    wait_spinner(page)
    page.wait_for_timeout(ms)


def _ui_close_guide(page):
    """The "Audit progress" guide panel that slides in on some screens."""
    close = page.locator("app-audit-guide-panel button.agp-close")
    if close.count() and close.evaluate(
            "e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.left < innerWidth && r.right > 0 }"):
        close.click()
        page.wait_for_timeout(500)


def _ui_open_summary(page, config):
    """Audits -> branch -> the audit in Ongoing Audits, else Audit History -> Audit Summary.
    The Stock Audit / Audit Summary choice only shows for open audits. Returns (list tab, list row)."""
    name = config.ap_audit_name
    page.wait_for_selector("a[href='/home/audit']", state="visible")
    page.click("a[href='/home/audit']")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)     # the list keeps polling at times
    except Exception:
        pass
    select_branch(page, config.Branch)
    wait_spinner(page)
    found = None
    for tab in ("Ongoing Audits", "Audit History"):
        t = page.get_by_role("tab", name=tab, exact=True)
        if t.count():
            t.first.click()
            _ui_settle(page, 2500)
        try:
            page.wait_for_selector("button.audit-name-link", timeout=30000)
        except Exception:
            continue
        page.wait_for_timeout(1000)
        row = audit_row(page, name)
        if row.count():
            found = (tab, row)
            break
    if not found:
        raise RuntimeError(f"audit {name} is in neither Ongoing Audits nor Audit History")
    tab, row = found
    heads = [_txt(h) for h in row.locator("xpath=ancestor::table[1]/thead//th").all_inner_texts()]
    info = OrderedDict(zip(heads, [_txt(x) for x in row.locator("td").all_inner_texts()]))
    row.locator("button.audit-name-link").click()
    print(f"   Opened audit: {name} ({tab})")
    nav = page.locator("div[role='dialog'][aria-labelledby='auditNavTitle']")
    try:
        nav.first.wait_for(state="visible", timeout=6000)
        select_navigation_option(page, "Audit Summary")
    except Exception:
        page.wait_for_url("**/auditSummary", timeout=30000)
        try:
            page.wait_for_function(_UI_LOADED_JS, timeout=30000)
        except Exception:
            pass
    _ui_settle(page, 1500)
    _ui_close_guide(page)
    return tab, info


def _ui_headers(page):
    return [_txt(h) for h in page.locator(f"{UI_SUMMARY} thead th").all_inner_texts()]


def _ui_page_rows(page):
    heads = _ui_headers(page)
    body = page.locator(f"{UI_SUMMARY} tbody.p-datatable-tbody").first
    if not body.count():
        return []
    return [OrderedDict(zip(heads, cells)) for cells in body.evaluate(_UI_ROWS_JS) if len(cells) == len(heads)]


def _ui_chips(page):
    out = OrderedDict()
    for t in page.locator(f"{UI_SUMMARY} span.badge-custom").all_inner_texts():
        m = re.match(r"^(.*?)\s*\((\d+)\)$", _txt(t))
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def _ui_active_count(page):
    a = page.locator(f"{UI_SUMMARY} span.badge-custom.active-badge").first
    m = re.search(r"\((\d+)\)\s*$", _txt(a.inner_text())) if a.count() else None
    return int(m.group(1)) if m else None


def _ui_wait_rows(page, timeout_ms=10000):
    """Wait until the table has finished refreshing: rows and chips read the same twice in a row, and an
    empty table only when the selected chip is 0 (a refresh empties the table before the chips update)."""
    _ui_settle(page, 600)
    prev = None
    for _ in range(max(1, timeout_ms // 400)):
        rows = _ui_page_rows(page)
        snap = ([tuple(r.values())[:3] for r in rows], tuple(_ui_chips(page).items()))
        ready = bool(rows) or _ui_active_count(page) == 0
        if ready and snap == prev:
            return True
        prev = snap if ready else None
        page.wait_for_timeout(400)
    return False


def _ui_pager(page, which):
    return page.locator(f"{UI_SUMMARY} .p-paginator button.p-paginator-{which}").first


def _ui_enabled(btn):
    return btn.count() > 0 and btn.is_enabled() and "p-disabled" not in (btn.get_attribute("class") or "")


def _ui_all_rows(page, limit=200):
    """Every row on every page (repeated item codes kept, unlike collect_all); back on page 1."""
    if _ui_enabled(_ui_pager(page, "first")):
        _ui_pager(page, "first").click()
        _ui_wait_rows(page)
    rows, pages = _ui_page_rows(page), 1
    while pages < limit and _ui_enabled(_ui_pager(page, "next")):
        _ui_pager(page, "next").click()
        _ui_wait_rows(page)
        rows += _ui_page_rows(page)
        pages += 1
    if pages > 1 and _ui_enabled(_ui_pager(page, "first")):
        _ui_pager(page, "first").click()
        _ui_wait_rows(page)
    return rows


def _ui_reopen(page, st):
    """Open the summary again (Item view, All chip): used when the report table stopped loading."""
    _ui_open_summary(page, st["config"])
    _ui_summarize(page, "Item")
    _ui_chip(page, "All")


def _ui_rows_retry(page, st, apply, rows_expected):
    """apply() (select a chip or a Summarize As option), then read every row. When the table stays empty
    although rows are expected, reopen the summary, apply() again and read once more. Returns (rows, note)."""
    apply()
    rows = _ui_all_rows(page)
    if rows or not rows_expected:
        return rows, ""
    _ui_reopen(page, st)
    apply()
    return _ui_all_rows(page), " — the table stayed empty on the first try; read again after reopening the page"


def _ui_tiles(page):
    tiles = OrderedDict()
    for t in page.locator(f"{UI_SUMMARY} div.audit-info-tile .tile-row").all():
        label = _txt(t.locator(".tile-label").first.inner_text())
        val, pill, prog = t.locator(".tile-value").first, t.locator(".status-pill").first, t.locator(".progress-value").first
        if val.count():
            tiles[label] = _txt(val.get_attribute("title") or val.inner_text())    # title = untruncated
        elif pill.count():
            tiles[label] = _txt(pill.inner_text())
        elif prog.count():
            tiles[label] = _txt(prog.inner_text())
        else:
            tiles[label] = _txt(t.inner_text())[len(label):].strip()
    for joined, parts in SPLIT_TILES.items():
        label = _find(joined, list(tiles))
        if label:
            bits = [b.strip() for b in tiles[label].split(" - ", len(parts) - 1)]
            tiles.update(zip(parts, bits + [""] * (len(parts) - len(bits))))
    return tiles


def _ui_cards(page, mode):
    """{Stock, Audited, Damaged} from the Qty or Value cards (the toggle is put back to Qty after Value)."""
    btn = page.locator(f"{UI_SUMMARY} div.summary-toggle button.toggle-btn", has_text=mode).first
    if "active" not in (btn.get_attribute("class") or ""):
        btn.click()
        _ui_settle(page, 1200)
    out = OrderedDict()
    for m in page.locator(f"{UI_SUMMARY} div.summary-metric").all():
        out[_txt(m.locator(".metric-label").inner_text())] = _qn(m.locator(".metric-value").inner_text())
    if mode != "Qty":
        _ui_cards(page, "Qty")
    return out


def _ui_options(page):
    page.locator(_UI_SUMMARIZE).first.click()
    page.wait_for_timeout(600)
    opts = [_txt(t) for t in page.locator(_UI_PANEL_LI).all_inner_texts()]
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    return opts


def _ui_summarize(page, option, tries=3):
    dd = page.locator(_UI_SUMMARIZE).first
    item = page.locator(_UI_PANEL_LI, has_text=re.compile(rf"^\s*{re.escape(option)}\s*$")).first
    for _ in range(tries):
        if _txt(dd.locator(".p-dropdown-label").inner_text()) == option:
            return
        _ui_settle(page, 500)
        try:
            dd.click(timeout=8000)
            item.wait_for(state="visible", timeout=5000)
            item.click(timeout=5000)
            _ui_wait_rows(page)
        except Exception:
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)
    if _txt(dd.locator(".p-dropdown-label").inner_text()) != option:
        raise RuntimeError(f"Summarize As did not switch to {option!r}")


def _ui_chip(page, chip):
    label = _find(chip, list(_ui_chips(page)))
    if label is None:
        raise RuntimeError(f"no chip {chip!r}")
    click_badge(page, Config(), label)
    _ui_wait_rows(page)


def _ui_charts(page):
    out = {}
    for ch in page.evaluate(_UI_CHARTS_JS):
        kind = "bar" if "barChart" in ch["card"] else "pie" if "pieChart" in ch["card"] else None
        if kind and ch["data"]:
            out[kind] = ch["data"]
    return out


def _ui_export(page, folder, prefix=""):
    """Download Export; {sheet: rows under its ItemCode header row} and the file path."""
    with page.expect_download(timeout=60000) as info:
        page.locator(f"{UI_SUMMARY} button.warning-button", has_text="Export").first.click()
    path = os.path.join(folder, prefix + (info.value.suggested_filename or "Audit Summary Report.xlsx"))
    info.value.save_as(path)
    sheets = OrderedDict()
    for name, raw in pd.read_excel(path, header=None, dtype=str, sheet_name=None).items():
        raw = raw.fillna("")
        for i in range(min(15, len(raw))):
            cells = [_txt(x) for x in raw.iloc[i]]
            if "itemcode" in [_key(x) for x in cells]:
                df = raw.iloc[i + 1:].copy()
                df.columns = [c_ if c_ and c_ not in cells[:j] else f"{c_}#{j}" for j, c_ in enumerate(cells)]
                code = next(col for col in df.columns if _key(col) == "itemcode")
                sheets[name] = df[df[code].map(_txt) != ""]
                break
        else:
            sheets[name] = pd.DataFrame()
    return path, sheets


def _ui_prices(sheets):
    """{ITEM CODE: CostPrice} from the export (the report's price; the highest when an item repeats)."""
    df = sheets.get("All")
    if df is None or df.empty:
        df = next((d for d in sheets.values() if d is not None and not d.empty), pd.DataFrame())
    code = next((c_ for c_ in df.columns if _key(c_) == "itemcode"), None)
    cost = next((c_ for c_ in df.columns if _key(c_) == "costprice"), None)
    prices = {}
    if code and cost:
        for _, r in df.iterrows():
            k, v = _txt(r[code]).upper(), _qn(r[cost])
            prices[k] = max(prices.get(k, v), v)
    return prices


def _ui_pdf_cmap(streams):
    """Glyph code -> text from every ToUnicode map in the PDF (fonts with Identity-H encoding)."""
    cmap = {}
    for raw in streams:
        if b"beginbfchar" not in raw and b"beginbfrange" not in raw:
            continue
        for body in re.findall(rb"beginbfchar(.*?)endbfchar", raw, re.S):
            for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", body):
                cmap[int(src, 16)] = bytes.fromhex(dst.decode()).decode("utf-16-be", "ignore")
        for body in re.findall(rb"beginbfrange(.*?)endbfrange", raw, re.S):
            for lo, hi, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]+>|\[[^\]]*\])", body):
                lo, hi = int(lo, 16), int(hi, 16)
                if dst.startswith(b"["):
                    for i, d in enumerate(re.findall(rb"<([0-9A-Fa-f]+)>", dst)):
                        cmap[lo + i] = bytes.fromhex(d.decode()).decode("utf-16-be", "ignore")
                else:
                    start = int(dst[1:-1], 16)
                    for i in range(hi - lo + 1):
                        cmap[lo + i] = chr(start + i)
    return cmap


def _ui_pdf_text(data):
    """Text of a PDF without a PDF library: inflate each stream, then join the strings of each text block.
    Literal strings (...) are read as they are; hex strings <...> through the ToUnicode maps."""
    streams = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        raw = m.group(1).rstrip(b"\r\n")
        try:
            raw = zlib.decompress(raw)
        except Exception:
            pass
        streams.append(raw)
    cmap = _ui_pdf_cmap(streams)
    out = []
    for raw in streams:
        for block in re.findall(rb"BT(.*?)ET", raw, re.S):
            parts = []
            for lit, hexs in re.findall(rb"\(((?:\\.|[^\\)])*)\)|<([0-9A-Fa-f]+)>", block):
                if lit:
                    parts.append(lit.decode("latin-1", "ignore"))
                elif hexs:
                    codes = [int(hexs[i:i + 4], 16) for i in range(0, len(hexs) - 3, 4)]
                    parts.append("".join(cmap.get(x, "") for x in codes))
            out.append("".join(parts))
    return "\n".join(out)


def _ui_buttons(page):
    """{label: locator} of the header buttons, the buttons above the table and the ⋮ menu items."""
    pools = {"top": OrderedDict(), "table": OrderedDict(), "menu": OrderedDict()}
    for where, sel in (("top", f"{UI_SUMMARY} .audit-actions-buttons button"), ("table", f"{UI_SUMMARY} .card-header button")):
        for b in page.locator(sel).all():
            label = _txt(b.inner_text()) or _txt(b.get_attribute("title") or b.get_attribute("aria-label"))
            if label and b.is_visible():
                pools[where][label] = b
    dots = page.locator(f"{UI_SUMMARY} button.dots-btn").first
    if dots.count() and dots.is_visible():
        dots.click()
        page.wait_for_timeout(800)
        for b in page.locator(f"{UI_SUMMARY} .dropdown-container").first.locator("button, a, li").all():
            label = _txt(b.inner_text())
            if label and label not in pools["menu"] and b.is_visible():
                pools["menu"][label] = b
        _ui_close_menu(page)
    return pools


def _ui_close_menu(page):
    page.keyboard.press("Escape")
    title = page.locator(f"{UI_SUMMARY} .audit-details-title").first
    if title.count():
        title.click()
    page.wait_for_timeout(400)


# ----------------------------------------------------------------------
# results and report
# ----------------------------------------------------------------------
class _UIChecks:
    def __init__(self, page, folder, prefix=""):
        self.page, self.folder, self.prefix, self.rows = page, folder, prefix, []

    def add(self, group, check, ok, expected, actual, status=None, finding=""):
        status = status or ("PASS" if ok else "FAIL")
        shot = ""
        if status == "FAIL" and sum(r["Status"] == "FAIL" for r in self.rows) < 40:
            shot = os.path.join(self.folder, f"{self.prefix}FAIL_{len(self.rows) + 1:03d}_{_key(check)[:30]}.png")
            try:
                self.page.screenshot(path=shot, full_page=True)
            except Exception:
                shot = ""
        self.rows.append(OrderedDict([("Group", group), ("Check", check), ("Expected", _txt(expected)),
                                      ("Actual", _txt(actual)), ("Status", status), ("Finding", finding),
                                      ("Screenshot", shot)]))
        col = {"PASS": G, "FAIL": R, "KNOWN": Y}.get(status, DIM)
        print(f"  {c(f'{status:<8}', col)} {group} | {check} | {_txt(actual)[:160]}")

    def error(self, group, step, e):
        self.add(group, step, False, "runs without an error", f"error: {str(e).splitlines()[0][:200]}")

    def not_run(self, group, check, why):
        self.add(group, check, None, "-", why, status="NOT RUN")


def _ui_write_report(checks, folder, config, name="Summary_UI_Validation.xlsx"):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    fills = {"PASS": "C6EFCE", "FAIL": "FFC7CE", "KNOWN": "FCE4D6", "NOT RUN": "D9D9D9"}
    wb = Workbook()
    ws = wb.active
    ws.title = "Checks"
    ws.append(list(checks.rows[0].keys()))
    for r in checks.rows:
        ws.append(list(r.values()))
        ws.cell(ws.max_row, 5).fill = PatternFill("solid", fgColor=fills.get(r["Status"], "FFFFFF"))
    bugs = wb.create_sheet("Bugs")
    bugs.append(["Bug ID", "Module", "Sub Module", "Bug Title", "Environment", "Severity", "Priority",
                 "Preconditions", "Steps to Reproduce", "Expected Result", "Actual Result", "Reproducibility",
                 "Status", "Attachments"])
    for n, r in enumerate([r for r in checks.rows if r["Status"] == "FAIL"], 1):
        bugs.append([f"SA-SUM-{n:03d}", "Stock Audit", f"Audit Summary — {r['Group']}", r["Check"],
                     getattr(config, "environments", "QA"), "Major", "Medium",
                     f"1. User is logged in as the audit owner.\n2. Audit {config.ap_audit_name} exists.",
                     f"1. Audits > open {config.ap_audit_name} > Audit Summary.\n2. Check: {r['Group']} > {r['Check']}.",
                     r["Expected"], r["Actual"], "Always", "New", r["Screenshot"]])
    for sheet in (ws, bugs):
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width = min(max(10, max(len(str(x.value or "")) for x in col) + 2), 70)
            for x in col:
                x.alignment = Alignment(wrap_text=True, vertical="top")
    path = os.path.join(folder, name)
    wb.save(path)
    return path


# ----------------------------------------------------------------------
# the checks, one function per required-field group
# ----------------------------------------------------------------------
def _check_information(ck, st):
    group, tiles, row = "Audit Information", st["tiles"], st["list_row"]
    for field in REQUIRED_FIELDS[group]:
        label = _find(field, list(tiles))
        ck.add(group, f"{field} shown with a value", bool(label and tiles[label]), "shown, not empty",
               f"{label}: {tiles[label]!r}" if label else "MISSING")
    get = lambda f: tiles.get(_find(f, list(tiles)) or "", "")
    ck.add(group, "Audit Name = the audit opened", get("Audit Name") == st["audit"], st["audit"], get("Audit Name"))
    list_type = next((v for k, v in row.items() if _key(k) == "type"), None)
    list_status = next((v for k, v in row.items() if _key(k) == "status"), None)
    ck.add(group, "Audit Type = audit list Type", _key(get("Audit Type")) == _key(list_type), list_type, get("Audit Type"))
    ck.add(group, "Status = audit list Status", _key(get("Status")) == _key(list_status), list_status, get("Status"))
    ck.add(group, "Status is a known label", get("Status") in STATUS_LABELS, " / ".join(STATUS_LABELS), get("Status"))
    ck.add(group, "Mapping Type is a known type", get("Mapping Type") in MAPPING_TYPES, " / ".join(MAPPING_TYPES),
           get("Mapping Type"))
    when = _parse_date(get("Date & Time"), DATE_FORMATS["Date & Time"])
    created = next((v for k, v in row.items() if "created" in _key(k)), "")
    made = next((d for d in (_parse_date(created, f) for f in ("%d-%m-%Y", "%m-%d-%Y", "%Y-%m-%d")) if d), None)
    ck.add(group, f"Date & Time is {DATE_FORMATS['Date & Time']} and the audit's creation date",
           bool(when) and (made is None or abs((when.date() - made.date()).days) <= 1),
           f"format {DATE_FORMATS['Date & Time']}, date ≈ list Created Date {created}", get("Date & Time"))
    # Progress
    total = next((v for k, v in row.items() if "totallineitem" in _key(k)), "")
    m = re.search(r"/\s*(\d+)", total)
    stock_rows = int(m.group(1)) if m else len({_row_vals(r)["code"] for r in st["rows"] if _row_vals(r)["stock_location"]})
    st["stock_rows"] = stock_rows
    progress, label, names = _expected_progress(st["rows"], stock_rows, st["qty"])
    shown = re.search(r"(\d+(?:\.\d+)?)\s*%", get("Progress"))
    bar = st.get("progress_bar")
    ok = bool(shown) and float(shown.group(1)) == label and (bar is None or _near(bar, progress, 0.01))
    ck.add(group, "Progress = formula", ok,
           f"formula: {PROGRESS_FORMULA} → {_show(PROGRESS_FORMULA, **names)} = {progress:.2f} → label {label}%",
           f"label {get('Progress')!r}, bar {bar}")


def _check_counts(ck, st, page):
    group, chips = "Audit Summary Counts", st["chips"]
    expected = _expected_chips(st["rows"])
    for field in REQUIRED_FIELDS[group]:
        label = _find(field, list(chips))
        if label is None:
            ck.add(group, f"{field} chip shown", False, "shown", "MISSING")
            continue
        want = expected.get(field)
        ck.add(group, f"{field} count = rows meeting its rule", want is None or chips[label] == want,
               f"formula: {CHIP_RULES.get(field, '-')} = {want} row(s)", chips[label])
    for field in REQUIRED_FIELDS[group]:                  # each chip lists as many rows as it counts
        label = _find(field, list(chips))
        if label is None:
            continue
        try:
            listed, note = _ui_rows_retry(page, st, lambda: _ui_chip(page, label), chips[label] > 0)
            st.setdefault("chip_lists", {})[field] = {_row_vals(r)["code"].upper() for r in listed}
            actual = f"{len(listed)} row(s): {[_row_vals(r)['code'] for r in listed][:15]}{note}"
            known = CHIP_LIST_DIFFS.get(field)
            names = {"count": chips[label], "listed": len(listed),
                     "resolution": st["status"] in ("In Resolution", "Completed", "Auto Completed")}
            if len(listed) != chips[label] and known and _calc(known[1], **names):
                ck.add(group, f"{field} lists {chips[label]} row(s)", False, f"formula: chip count = {chips[label]} row(s)",
                       f"{actual} (spec {known[0]}: count and list rules differ)", status="KNOWN",
                       finding=f"spec {known[0]}")
                continue
            ck.add(group, f"{field} lists {chips[label]} row(s)", len(listed) == chips[label], f"formula: chip count = {chips[label]} row(s)", actual)
        except Exception as e:
            ck.error(group, f"{field} chip list", e)
    _ui_chip(page, _find("All", list(chips)))


def _check_quantities(ck, st):
    group, prices = "Quantity Summary", st["prices"]
    vals = [_row_vals(r, prices) for r in st["rows"]]
    for field, (qty_rule, value_rule) in CARD_FORMULAS.items():
        label = _find(field, list(st["qty"]))
        if label is None:
            ck.add(group, f"{field} card shown", False, "shown", f"MISSING (cards {list(st['qty'])})")
            continue
        want = sum(_calc(qty_rule, **v) for v in vals)
        ck.add(group, f"{field} (Qty) = Σ {qty_rule}", _near(st["qty"][label], want),
               f"formula: Σ({qty_rule}) over {len(vals)} row(s) = {want:g}", st["qty"][label])
        priced = [v for v in vals if v["price"] is not None]
        if len(priced) < len(vals):
            ck.not_run(group, f"{field} (Value)", f"no price for {len(vals) - len(priced)} row(s) (export not read)")
            continue
        want = sum(_calc(value_rule, **v) for v in vals)
        got = st["value"].get(_find(field, list(st["value"])) or "")
        ck.add(group, f"{field} (Value) = Σ {value_rule}", _near(got, want),
               f"formula: Σ({value_rule}) over {len(vals)} row(s) = {want:.2f}", got)


def _check_table(ck, st):
    group, heads = "Audit Report - Table Fields", st["headers"]
    missing = [f for f in REQUIRED_FIELDS[group] if _find(f, heads) is None]
    ck.add(group, "All table fields shown", not missing, ", ".join(REQUIRED_FIELDS[group]),
           f"missing={missing}; order on screen: {heads}")
    not_audited_codes = (st.get("chip_lists") or {}).get(NOT_AUDITED_CHIP)
    audited_rows = [r for r in st["rows"] if not _not_audited(_row_vals(r), not_audited_codes)]
    for field, rule in ROW_FORMULAS.items():           # variance formulas: audited line items only
        bad, want_samples, got_samples = [], [], []
        for r in audited_rows:
            v = _row_vals(r, st["prices"])
            if "price" in rule and v["price"] is None:
                continue
            want = _calc(rule, **v)
            got = {"Variance": v["variance"], "Variance Value": v["variance_value"],
                   "Variance Type": v["variance_type"]}.get(field)
            want_samples.append(_row_sample(field, rule, v, want))
            got_samples.append(f"{v['code']}: {_fmt_field(field, got)}")
            if not (got == want if isinstance(want, str) else _near(got, want)):
                bad.append(f"{v['code']}: {_fmt_field(field, got)} vs {_fmt_field(field, want)}")
        if not want_samples:
            ck.not_run(group, f"{field} = {rule}", "no price (export not read)")
        else:
            ck.add(group, f"{field} = {rule}", not bad, f"formula: {rule} → {_sample(want_samples)}",
                   _sample(bad, 8, "; ") if bad else _sample(got_samples))
    fmt = DATE_FORMATS["Audited Date"]
    bad = [f"{_row_vals(r)['code']}: {_cell(r, 'Audited Date')!r}" for r in st["rows"]
           if _blank(_cell(r, "Audited Date")) and not _parse_date(_cell(r, "Audited Date"), fmt)]
    date_samples = [f"{_row_vals(r)['code']}: {_cell(r, 'Audited Date')}" for r in audited_rows if _blank(_cell(r, "Audited Date"))]
    act_dates = _sample(bad, 8, "; ") if bad else _sample(date_samples)
    ck.add(group, f"Audited Date format {fmt}", not bad, f"format {fmt} on every audited row", act_dates or "no dates")
    _check_not_audited(ck, st, audited_rows)


def _check_not_audited(ck, st, audited_rows):
    """User rule: line items that were not audited (Un Verified) show no audit details and no variance;
    audited ones do."""
    group = "Not Audited Items"
    listed = (st.get("chip_lists") or {}).get(NOT_AUDITED_CHIP)
    source = (f"the rows the {NOT_AUDITED_CHIP} chip lists" if listed is not None
              else f"rows meeting {CHIP_RULES[NOT_AUDITED_CHIP]}")
    not_audited = [r for r in st["rows"] if r not in audited_rows]
    codes = [_row_vals(r)["code"] for r in not_audited]
    ck.add(group, "Line items that were not audited", True, f"formula: {source} = {len(codes)} item(s)",
           f"{len(codes)} item(s): {codes[:20]}", status="PASS" if codes else "NOT RUN")
    audited_codes = [_row_vals(r)["code"] for r in audited_rows]
    for field, (rule, finding) in NOT_AUDITED_EXPECT.items():
        if not not_audited:
            break
        bad = [f"{_row_vals(r)['code']}: {_cell(r, field)!r}" for r in not_audited if not _calc(rule, **_row_vals(r))]
        samples = [f"{_row_vals(r)['code']}: {_cell(r, field)!r}" for r in not_audited]
        ck.add(group, f"Not audited: {field} ({rule})", not bad,
               f"formula: {rule} on all {len(not_audited)} uncounted item(s) → {_sample(codes, 8)}",
               _sample(bad, 10, "; ") if bad else _sample(samples, 8),
               finding=f"spec {finding}" if bad and finding else "")
    for field, rule in AUDITED_EXPECT.items():
        bad = [f"{_row_vals(r)['code']}: {_cell(r, field)!r}" for r in audited_rows if not _calc(rule, **_row_vals(r))]
        samples = [f"{_row_vals(r)['code']}: {_cell(r, field)!r}" for r in audited_rows]
        ck.add(group, f"Audited: {field} shown ({rule})", not bad,
               f"formula: {rule} on all {len(audited_rows)} audited row(s) → {_sample(audited_codes, 8)}",
               _sample(bad, 10, "; ") if bad else _sample(samples))


def _check_location_view(ck, st, page, rows):
    """Deep validation of Summarize As = 'Location' mode per skill_audit/04-summarize-as-location.md:
    1. Table columns & values (§3): Variance, Variance Value, Variance Type (never-counted = 0/0/'-').
    2. Stock Location (blank for excess, 'Unassigned' for blank sheet loc) vs Audited Location (blank for uncounted).
    3. Location filter chips / badges (§4): All, Matched, Unverified, Not Found, Excess, Positive, Negative, Location Conflict.
    4. Location table filter: clicking active filter badges and verifying filtered rows.
    5. Location Metric Cards (§5): Stock (partitioned by ItemCode, StockLocation), Audited, Damaged.
    6. Search filter (§6): search by item code filters rows.
    """
    group = "Location View"
    prices = st["prices"]
    loc_vals = [_row_vals(r, prices) for r in rows]

    # --- 1. Columns & Values on every row (doc 04 §3, §8 finding 1, §8 finding 8, §9) ---
    bad_val, bad_type = [], []
    want_vals, want_types = [], []
    for v in loc_vals:
        is_audited = (v["audited"] > 0) or bool(v["auditor"])
        want_val = ((v["audited"] - v["stock"]) * v["price"]) if (is_audited and v["price"] is not None) else 0.0
        want_type = ("Positive" if v["audited"] > v["stock"] else "Negative" if v["audited"] < v["stock"] else "-") if is_audited else "-"
        if not is_audited:
            want_vals.append(f"{v['code']}: 0.00 (never counted)")
            want_types.append(f"{v['code']}: '-' (never counted)")
        else:
            want_types.append(_row_sample("Variance Type", ROW_FORMULAS["Variance Type"], v, want_type))
            if v["price"] is not None:
                want_vals.append(_row_sample("Variance Value", ROW_FORMULAS["Variance Value"], v, want_val))
        if v["price"] is not None and not _near(v["variance_value"], want_val):
            bad_val.append(f"{v['code']}: got {v['variance_value']:+.2f} vs {want_val:+.2f}")
        if v["variance_type"] != want_type and not (not is_audited and v["variance_type"] in ("-", "Not Audited")):
            bad_type.append(f"{v['code']}: got {v['variance_type']!r} vs {want_type!r}")
    ck.add(group, "Location: Variance Value = (audited - stock) * price / 0", not bad_val,
           f"formula: {ROW_FORMULAS['Variance Value']} on counted rows, 0.00 on never-counted rows (§8 F1) → "
           f"{_sample(want_vals)}",
           _sample(bad_val, 6, "; ") if bad_val else _sample(f"{v['code']}: {v['variance_value']:+.2f}" for v in loc_vals))

    ck.add(group, "Location: Variance Type = Positive/Negative/- (audited) / '-' (never counted)", not bad_type,
           f"formula: audited > stock → Positive, audited < stock → Negative, else '-' (equal or never counted §8 F1) → "
           f"{_sample(want_types, 8)}",
           _sample(bad_type, 6, "; ") if bad_type else _sample((f"{v['code']}: {v['variance_type']}" for v in loc_vals), 8))

    # --- 2. Stock Location vs Audited Location (doc 04 §2.5, §3, §8 finding 6, §9) ---
    bad_loc = []
    case_breakdown = []
    case_n = Counter()
    for v in loc_vals:
        code = v["code"]
        stk_loc = v["stock_location"].strip()
        aud_loc = v["audited_location"].strip()
        stk = v["stock"]
        aud = v["audited"]
        has_auditor = bool(v["auditor"])
        is_counted = (aud > 0) or has_auditor
        has_sheet = (stk > 0)
        case_n["uncounted" if not is_counted and has_sheet else "excess" if is_counted and not has_sheet
               else "counted" if is_counted else "other"] += 1

        # §8 Finding 6: Blank vs "Unassigned" semantics
        # Stock Location blank = no sheet side (excess/off-sheet); "Unassigned" = sheet row without a location.
        # Audited Location blank = never counted; "Unassigned" = counted without a location.

        if not is_counted and has_sheet:
            # §2.5 Case 6: On sheet, never counted -> Audited Location MUST be strictly blank ''
            if aud_loc != "":
                bad_loc.append(f"{code} (Case 6 Uncounted): Audited Location must be blank '', got {aud_loc!r}")
            elif stk_loc == "":
                bad_loc.append(f"{code} (Case 6 Uncounted): Stock Location cannot be blank for sheet row (should be loc name or 'Unassigned')")
            else:
                case_breakdown.append(f"Case 6 Uncounted {code}: StockLoc='{stk_loc}', AudLoc=''")

        elif is_counted and not has_sheet:
            # §2.5 Cases 3, 4, 5, 7: Excess (no sheet side) -> Stock Location MUST be strictly blank ''
            if stk_loc != "":
                bad_loc.append(f"{code} (Excess): Stock Location must be blank '', got {stk_loc!r}")
            elif aud_loc == "":
                bad_loc.append(f"{code} (Excess): Audited Location cannot be blank when counted")
            else:
                case_lbl = "Case 4/5 Excess Unassigned" if aud_loc.upper() == "UNASSIGNED" else "Case 3/5/7 Excess Located"
                case_breakdown.append(f"{case_lbl} {code}: StockLoc='', AudLoc='{aud_loc}'")

        elif is_counted and has_sheet:
            # §2.5 Cases 1 & 2: Counted sheet item
            if stk_loc == "":
                bad_loc.append(f"{code} (Sheet count): Stock Location cannot be blank for sheet row")
            elif aud_loc == "":
                bad_loc.append(f"{code} (Sheet count): Audited Location cannot be blank for counted item")
            elif stk_loc.upper() == "UNASSIGNED" and aud_loc.upper() == "UNASSIGNED":
                case_breakdown.append(f"Case 2 Sheet Unassigned {code}: StockLoc='Unassigned', AudLoc='Unassigned'")
            elif stk_loc == aud_loc:
                case_breakdown.append(f"Case 1 Matched {code}: StockLoc='{stk_loc}', AudLoc='{aud_loc}'")
            else:
                case_breakdown.append(f"Case 3 Split Location {code}: StockLoc='{stk_loc}', AudLoc='{aud_loc}'")

    ck.add(group, "Location: Stock Location blank for excess, Audited Location blank for uncounted (§8 F6)", not bad_loc,
           f"formula: Excess (counted, stock == 0) → StockLoc='' on {case_n['excess']} row(s); "
           f"Uncounted (stock > 0, not counted) → AudLoc='' on {case_n['uncounted']} row(s); "
           f"Counted sheet rows → StockLoc and AudLoc non-empty on {case_n['counted']} row(s)",
           _sample(bad_loc, 6, "; ") if bad_loc else _sample(case_breakdown, 8, "; "))

    # --- Batch in Location mode: ONLY check when inventory type is 'batch' (skip for 'unit' and 'serialized') ---
    offered_options = st.get("options") or []
    is_batch = (_find("Batch", offered_options) is not None) or (getattr(st.get("config"), "invType", "").upper() in ("B", "BATCH"))
    if is_batch:
        heads = _ui_headers(page)
        batch_col = _find("Batch No", heads) or _find("Batch", heads)
        if batch_col:
            batch_keys = [tuple(_txt(_cell(r, k)) for k in ["Item Code", "Stock Location", "Audited Location"]) for r in rows]
            dup_locs = sorted({k for k in batch_keys if batch_keys.count(k) > 1})
            ck.add(group, "Batch in Location mode: one row per location", not dup_locs,
                   f"formula: count per (ItemCode, StockLocation, AuditedLocation) == 1 over {len(rows)} row(s)",
                   f"repeated={dup_locs[:5]}" if dup_locs else f"{len(set(batch_keys))} unique key(s) in {len(rows)} row(s)")
            multi_batch = [f"{_cell(r, 'Item Code')}: {_cell(r, batch_col)}" for r in rows if "," in _cell(r, batch_col)]
            ck.add(group, "Batch in Location mode: one batch shown per row", not multi_batch,
                   f"formula: batches per row == 1 → 0 multi-batch row(s) of {len(rows)}",
                   f"multi-batch rows: {multi_batch[:5]}" if multi_batch else "one batch shown per row")

    # --- 3. Summary Tiles (Metric strip) with Qty (doc 04 §5) ---
    loc_qty = _ui_cards(page, "Qty")
    seen_stock = set()
    exp_stock = 0.0
    for v in loc_vals:
        key = (v["code"].upper(), v["stock_location"])
        if key not in seen_stock:
            seen_stock.add(key)
            exp_stock += v["stock"]
    exp_audited = sum(v["audited"] for v in loc_vals)
    exp_damaged = sum(v["damaged"] for v in loc_vals)
    label_stock = _find("Stock Quantity", list(loc_qty))
    label_audited = _find("Audited Quantity", list(loc_qty))
    label_damaged = _find("Damaged Quantity", list(loc_qty))
    if label_stock:
        ck.add(group, "Location: Stock card = Σ distinct (ItemCode, StockLocation) stock",
               _near(loc_qty[label_stock], exp_stock),
               f"formula: Σ distinct (ItemCode, StockLocation) StockQty over {len(seen_stock)} key(s) = {exp_stock:g}",
               f"{loc_qty[label_stock]:g}")
    if label_audited:
        ck.add(group, "Location: Audited card = Σ audited",
               _near(loc_qty[label_audited], exp_audited),
               f"formula: Σ AuditedQty over {len(loc_vals)} row(s) = {exp_audited:g}",
               f"{loc_qty[label_audited]:g}")
    if label_damaged:
        ck.add(group, "Location: Damaged card = Σ damaged",
               _near(loc_qty[label_damaged], exp_damaged),
               f"formula: Σ DamagedQty over {len(loc_vals)} row(s) = {exp_damaged:g}",
               f"{loc_qty[label_damaged]:g}")

    # --- 4. Filter Chips (Badges) in Location Mode (doc 04 §4) ---
    loc_chips = _ui_chips(page)
    loc_chip_rules = OrderedDict([
        ("All", "True"),
        ("Matched Line Item", "audited == stock"),
        ("Unverified", "stock > 0 and audited == 0 and auditor == ''"),
        ("Not Found", "stock > 0 and audited == 0 and auditor != ''"),
        ("Excess Line Item", "stock == 0 and audited > 0"),
        ("Positive Variance", "audited > stock"),
        ("Negative Variance", "auditor != '' and audited < stock"),
        ("Location Conflict", "audited > 0 and stock_location != audited_location"),
        ("Cross Checked Audit", "cross_audited > 0"),
        ("Damaged Report", "damaged > 0"),
    ])
    exp_chips = OrderedDict((k, sum(1 for v in loc_vals if _calc(r, **v))) for k, r in loc_chip_rules.items())
    for field, want_cnt in exp_chips.items():
        chip_lbl = _find(field, list(loc_chips))
        if chip_lbl is None:
            continue
        got_cnt = loc_chips[chip_lbl]
        ck.add(group, f"Location: {field} chip count = rows meeting its rule", got_cnt == want_cnt,
               f"formula: {loc_chip_rules[field]} = {want_cnt} row(s)", f"{got_cnt} row(s)")

    # --- 5. Table Filter: Badge Clicking in Location Mode (doc 04 §4) ---
    for field, want_cnt in exp_chips.items():
        if field == "All" or want_cnt == 0:
            continue
        chip_lbl = _find(field, list(loc_chips))
        if chip_lbl is None:
            continue
        try:
            filt_rows, note = _ui_rows_retry(page, st, lambda: _ui_chip(page, chip_lbl), True)
            filt_vals = [_row_vals(r, prices) for r in filt_rows]
            bad_filt = [v["code"] for v in filt_vals if not _calc(loc_chip_rules[field], **v)]
            ck.add(group, f"Location: Filter chip '{field}' lists {want_cnt} row(s) meeting its rule",
                   len(filt_rows) == want_cnt and not bad_filt,
                   f"formula: {loc_chip_rules[field]} = {want_cnt} row(s), every listed row meets it",
                   f"{len(filt_rows)} row(s); non-matching={bad_filt}{note}")
        except Exception as e:
            ck.error(group, f"Location: Filter chip '{field}' table filter", e)

    # Return badge to 'All'
    all_lbl = _find("All", list(loc_chips))
    if all_lbl:
        _ui_chip(page, all_lbl)

    # --- 6. Search / Table Filter Test (doc 04 §6) ---
    search_input = page.locator(f"{UI_SUMMARY} input[placeholder*='Search']").first
    if not search_input.count():
        search_input = page.locator(f"{UI_SUMMARY} .search-box input, {UI_SUMMARY} input.p-inputtext").first
    if search_input.count() and loc_vals:
        test_code = loc_vals[0]["code"]
        matching_codes = [v["code"] for v in loc_vals if test_code.upper() in v["code"].upper()]
        exp_matches = len(matching_codes)
        try:
            search_input.fill(test_code)
            _ui_settle(page, 1000)
            _ui_wait_rows(page)
            s_rows = _ui_all_rows(page)
            s_codes = [_txt(_cell(r, "Item Code")) for r in s_rows]
            ck.add(group, f"Location: Table Search '{test_code}' filters table rows",
                   len(s_rows) == exp_matches,
                   f"formula: ItemCode contains '{test_code}' = {exp_matches} row(s): {matching_codes[:5]}",
                   f"{len(s_rows)} row(s): {s_codes[:5]}")
            clear_btn = page.locator(f"{UI_SUMMARY} i.pi-times, {UI_SUMMARY} .clear-btn, {UI_SUMMARY} span.search-close").first
            if clear_btn.count() and clear_btn.is_visible():
                clear_btn.click()
            else:
                search_input.fill("")
                search_input.dispatch_event("input")
            _ui_settle(page, 1000)
            _ui_wait_rows(page)
        except Exception as e:
            ck.error(group, f"Location: Table Search test ({test_code})", e)


def _check_options(ck, st, page):
    group = "Summary Options"
    offered = st["options"]
    missing = [o for o in REQUIRED_FIELDS[group] if _find(o, offered) is None]
    ck.add(group, "Summarize As offers every option", not missing, ", ".join(REQUIRED_FIELDS[group]),
           f"offered={offered}; missing={missing}")
    base_heads = st["headers"]
    item_view = defaultdict(lambda: {"stock": 0.0, "audited": 0.0, "damaged": 0.0})
    for r in st["rows"]:
        v = _row_vals(r)
        for k in ("stock", "audited", "damaged"):
            item_view[v["code"].upper()][k] += v[k]
    try:
        for option in REQUIRED_FIELDS[group]:
            label = _find(option, offered)
            spec = MODE_SPEC.get(option)
            if label is None or spec is None:
                continue
            rows, note = _ui_rows_retry(page, st, lambda: _ui_summarize(page, label), st["chips"].get("All", 0) > 0)
            st.setdefault("mode_rows", {})[option] = rows       # Auditor rows: Auditor Insights expectations
            heads = _ui_headers(page)
            want = [h for h in base_heads if _find(h, spec["drop"]) is None] + spec["add"]
            lost = [h for h in want if _find(h, heads) is None]
            extra = [h for h in heads if _find(h, want) is None]
            ck.add(group, f"{option}: table columns update", not lost and not extra,
                   f"Item view columns{' + ' + str(spec['add']) if spec['add'] else ''}"
                   f"{' − ' + str(spec['drop']) if spec['drop'] else ''}", f"missing={lost} extra={extra}")
            keys = [tuple(_txt(_cell(r, k)) for k in spec["key"]) for r in rows]
            dup = sorted({k for k in keys if keys.count(k) > 1})
            ck.add(group, f"{option}: one row per {' × '.join(spec['key'])}", not dup and bool(rows),
                   f"formula: count per ({', '.join(spec['key'])}) == 1 over {len(rows)} row(s)",
                   f"{len(rows)} row(s); repeated={dup[:5]}{note}")
            per = defaultdict(lambda: {"stock": [], "audited": 0.0, "damaged": 0.0})
            unit_rows = rows
            if option == "UOM":                              # compare only rows counted in the primary unit
                unit_rows = [r for r in rows if _key(_cell(r, "Audited UOM")) in ("", _key(_cell(r, "UOM (Primary)")))]
            for r in unit_rows:
                v = _row_vals(r)
                p = per[v["code"].upper()]
                p["stock"].append(v["stock"])
                p["audited"] += v["audited"]
                p["damaged"] += v["damaged"]
            bad = []
            for code, p in per.items():
                iv = item_view.get(code)
                if iv is None:
                    bad.append(f"{code}: not in the Item view")
                    continue
                stock_ok = (_near(sum(p["stock"]), iv["stock"]) if spec["stock"] == "sum"
                            else all(_near(s, iv["stock"]) for s in p["stock"]))
                if not (stock_ok and _near(p["audited"], iv["audited"]) and _near(p["damaged"], iv["damaged"])):
                    bad.append(f"{code}: stock {p['stock']} audited {p['audited']:g} damaged {p['damaged']:g} "
                               f"vs Item view {iv['stock']:g}/{iv['audited']:g}/{iv['damaged']:g}")
            stock_rule = "Σ stock" if spec["stock"] == "sum" else "stock of every row"
            want_per = [f"{code}: stk={iv['stock']:g}, aud={iv['audited']:g}, dam={iv['damaged']:g}"
                        for code in per if (iv := item_view.get(code))]
            got_per = [f"{code}: stk={'+'.join(f'{s:g}' for s in p['stock'])}, aud={p['audited']:g}, dam={p['damaged']:g}"
                       for code, p in per.items()]
            ck.add(group, f"{option}: rows add up to the Item view per item", not bad,
                   f"formula: per item {stock_rule}, Σ audited, Σ damaged = Item view → {_sample(want_per)}",
                   _sample(bad, 6, "; ") if bad else f"{_sample(got_per)} ({len(per)} item(s) match)")
            bad, want_var, got_var = [], [], []
            for r in unit_rows:                          # not audited line items: variance 0 (NOT_AUDITED_EXPECT)
                v = _row_vals(r, st["prices"])
                not_audited = _not_audited(v, (st.get("chip_lists") or {}).get(NOT_AUDITED_CHIP))
                want = 0 if not_audited else _calc(ROW_FORMULAS["Variance"], **v)
                want_var.append(f"{v['code']}: 0 (uncounted)" if not_audited
                                else _row_sample("Variance", ROW_FORMULAS["Variance"], v, want))
                got_var.append(f"{v['code']}: {v['variance']:+g}")
                if not _near(v["variance"], want):
                    bad.append(f"{v['code']}: {v['variance']:+g} vs {want:+g}")
            ck.add(group, f"{option}: Variance = {ROW_FORMULAS['Variance']} (audited) / 0 (not audited)", not bad,
                   f"formula: {ROW_FORMULAS['Variance']} (audited) / 0 (uncounted) → {_sample(want_var, 8)}",
                   _sample(bad, 6, "; ") if bad else _sample(got_var, 8))
            if option == "Location":
                _check_location_view(ck, st, page, rows)
    except Exception as e:
        ck.error(group, "Summarize As options", e)
    finally:
        try:
            _ui_summarize(page, _find("Item", offered) or "Item")
        except Exception as e:
            ck.error(group, "back to Item", e)


def _check_actions(ck, st, page):
    group = "Actions"
    if not _ui_page_rows(page) and st["chips"].get("All", 0) > 0:     # the table stopped loading
        _ui_reopen(page, st)
    pools = _ui_buttons(page)
    facts = {"status": st["status"], "rows": len(st["rows"])}
    for field in REQUIRED_FIELDS[group]:
        rule = ACTION_RULES[field]
        pool = pools[rule["where"]]
        label = _find(field, list(pool))
        want = bool(_calc(rule["show"], **facts))
        ck.add(group, f"{field} {'shown' if want else 'hidden'} ({rule['where']}, status {st['status']})",
               (label is not None) == want,
               f"formula: {rule['show']} → {_show(rule['show'], **facts)} = {want} → {'shown' if want else 'hidden'}",
               "shown" if label else "hidden")
        if label and rule.get("disabled"):
            want_off = bool(_calc(rule["disabled"], **facts))
            off = pool[label].is_disabled()
            ck.add(group, f"{field} {'disabled' if want_off else 'enabled'} (status {st['status']})", off == want_off,
                   f"formula: {rule['disabled']} → {_show(rule['disabled'], **facts)} = {want_off} → "
                   f"{'disabled' if want_off else 'enabled'}",
                   "disabled" if off else "enabled")
        if not label:
            continue
        try:
            how = rule.get("check")
            if how in ("open", "auditor_insights"):
                _check_auditor_insights(ck, st, page, pool[label])
            elif how == "xlsx":
                ok = bool(st["export_path"]) and os.path.getsize(st["export_path"]) > 0
                ck.add(group, f"{field} downloads the report", ok, "a non-empty .xlsx",
                       f"{os.path.basename(st['export_path'] or '-')}; sheets={list(st['sheets'])}")
            elif how == "pdf":
                _check_pdf(ck, st, page, label, pools)
            elif how == "clipboard":
                _check_clipboard(ck, st, page, pool[label])
        except Exception as e:
            ck.error(group, f"{field} check", e)
            _ui_close_menu(page)


def _check_clipboard(ck, st, page, button):
    group = "Actions"
    origin = re.match(r"^https?://[^/]+", page.url).group(0)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
    button.click()
    page.wait_for_timeout(1200)
    text = page.evaluate("() => navigator.clipboard.readText()")
    lines = [l for l in text.splitlines() if l.strip()]
    shown = _ui_page_rows(page)
    codes = [_row_vals(r)["code"] for r in shown]
    pasted = [l.split("\t") for l in lines[1:]]
    found = [x for x in codes if any(x in cells for cells in pasted)]
    head = lines[0].split("\t") if lines else []
    lost = [h for h in REQUIRED_FIELDS["Audit Report - Table Fields"] if h != "S.No" and _find(h, head) is None]
    ck.add(group, "Copy Table copies the header and every row shown", bool(lines) and not lost and len(found) == len(codes),
           f"formula: 1 header line (table fields) + {len(codes)} row(s) shown = {len(codes) + 1} line(s)",
           f"{len(lines)} line(s); rows found {len(found)}/{len(codes)}; header missing={lost}")


def _check_auditor_insights(ck, st, page, button):
    """Deep validation of Auditor Insights dialog per skill_audit/01-audit-details-and-kpis.md §4:
    1. Dialog lifecycle: opens cleanly, header title 'Auditor Summary'.
    2. Header action controls: Search input, Refresh button, Copy Table button, Close button.
    3. Table columns in thead: Auditor, Completed Inventory, Audited Value, Damaged Value,
       Elapsed Timing, Progress, Status, Action.
    4. Row-level data validation in tbody:
       - Auditor full name (from title tooltip or cell text).
       - Completed Inventory: formatAuditQuantity (non-negative numeric).
       - Audited Value & Damaged Value: formatAuditValue (non-negative numeric).
       - Elapsed Timing: format HH:mm (hours can exceed 24).
       - Progress: bar + percentage text between 0% and 100%.
       - Status: 'Yet to Start', 'In Progress', 'Completed', or 'Unknown'.
       - Action: 'Finish' or 'Reopen' link (or disabled).
    5. Header tile cross-check: auditor names in dialog match assigned auditors.
    6. Total row in tfoot:
       - 'Total' label in first cell.
       - Total Completed Inventory = sum of auditor row completed quantities.
       - Total Audited Value = sum of auditor row audited values.
       - Total Damaged Value = sum of auditor row damaged values.
       - Elapsed Timing, Progress, Status, Action display '--'.
    7. Functional search filtering & Finding F9 verification:
       - Type auditor name -> rows filter to matching auditor.
       - Verify F9: Total row ignores search filter (sums unfiltered Auditdata).
       - Clear search input -> restores all rows.
    8. Dialog close: clicking close-btn cleanly hides dialog.
    """
    group = "Auditor Insights"
    replies = []                                         # GetAuditorSummary replies: progress inputs per auditor
    on_reply = lambda r: replies.append(r) if AUDITOR_API.lower() in r.url.lower() else None
    page.on("response", on_reply)
    button.click()
    dlg = page.locator("div.auditor-summary-dialog").first
    try:
        dlg.wait_for(state="visible", timeout=25000)
    except Exception as e:
        page.remove_listener("response", on_reply)
        ck.add(group, "Auditor Insights dialog opens", False, "dialog visible", f"timed out: {e}")
        return

    # Wait for the auditor summary API call & table rows to finish loading (wait up to 25s)
    wait_spinner(page, timeout=25000)
    for _ in range(50):  # poll up to 25s (50 x 500ms)
        tr_loc = dlg.locator("tbody.p-datatable-tbody > tr")
        tf_loc = dlg.locator("tfoot.p-datatable-tfoot tr")
        if tr_loc.count() > 0 and tf_loc.count() > 0:
            if _txt(tr_loc.first.inner_text()):
                break
        page.wait_for_timeout(500)
    _ui_settle(page, 1500)
    page.remove_listener("response", on_reply)
    api_rows = []
    for reply in reversed(replies):                      # the latest reply that reads
        try:
            api_rows = _api_records(reply.json())
        except Exception:
            continue
        if api_rows:
            break

    # 1. Dialog title
    title_el = dlg.locator(".auditor-summary-title .title, .p-dialog-title").first
    title_text = _txt(title_el.inner_text()) if title_el.count() else ""
    ck.add(group, "Dialog title is 'Auditor Summary'", "auditor summary" in title_text.lower(), "Auditor Summary", title_text)

    # 2. Controls in header
    search_input = dlg.locator(".auditor-summary-actions input.p-inputtext, input[placeholder*='Search']").first
    refresh_btn = dlg.locator(".auditor-summary-actions button.btn-light, button:has(i.bi-arrow-clockwise)").first
    copy_btn = dlg.locator("app-table-copy-button button, button:has(i.bi-clipboard)").first
    close_btn = dlg.locator("button.close-btn, button:has(i.bi-x-lg)").first

    controls_ok = (search_input.count() > 0 and refresh_btn.count() > 0 and
                   copy_btn.count() > 0 and close_btn.count() > 0)
    ck.add(group, "Header controls present (Search, Refresh, Copy Table, Close)",
           controls_ok, "all 4 controls present",
           f"search={search_input.count() > 0}, refresh={refresh_btn.count() > 0}, copy={copy_btn.count() > 0}, close={close_btn.count() > 0}")

    # 3. Columns in thead
    raw_heads = [_txt(h) for h in dlg.locator("thead th").all_inner_texts()]
    req_cols = ["Auditor", "Completed Inventory", "Audited Value", "Damaged Value", "Elapsed Timing", "Progress", "Status", "Action"]
    missing_cols = [req for req in req_cols if not any(_key(req) in _key(h) for h in raw_heads)]
    ck.add(group, "All Auditor Insights table columns shown", not missing_cols,
           ", ".join(req_cols), f"missing={missing_cols}; actual={raw_heads}")

    # 4. Table rows in tbody
    row_els = dlg.locator("tbody.p-datatable-tbody > tr").all()
    ck.add(group, "Auditor rows rendered", len(row_els) > 0, "formula: auditor rows >= 1", f"{len(row_els)} row(s)")

    parsed_rows = []
    bad_quantities = []
    bad_values = []
    bad_timings = []
    bad_progresses = []
    bad_statuses = []
    bad_actions = []

    for r in row_els:
        tds = r.locator("td").all()
        if len(tds) < 8:
            continue
        # Auditor name: from title attr or inner text
        aud_name = _txt(tds[0].get_attribute("title") or tds[0].inner_text())
        completed_txt = _txt(tds[1].inner_text())
        aud_val_txt = _txt(tds[2].inner_text())
        dam_val_txt = _txt(tds[3].inner_text())
        timing_txt = _txt(tds[4].inner_text())
        prog_txt = _txt(tds[5].inner_text())
        status_txt = _txt(tds[6].inner_text())
        action_txt = _txt(tds[7].inner_text())

        completed = _qn(completed_txt)
        aud_val = _qn(aud_val_txt)
        dam_val = _qn(dam_val_txt)

        # Action link element & disabled state
        act_link = tds[7].locator("a, button").first
        act_disabled = False
        if act_link.count():
            aria_dis = (act_link.get_attribute("aria-disabled") or "").lower()
            cls_str = (act_link.get_attribute("class") or "").lower()
            act_disabled = aria_dis == "true" or "disabled" in cls_str or act_link.is_disabled()

        parsed_rows.append({
            "name": aud_name,
            "completed": completed,
            "audited_val": aud_val,
            "damaged_val": dam_val,
            "timing": timing_txt,
            "progress": prog_txt,
            "status": status_txt,
            "action": action_txt,
            "action_disabled": act_disabled,
        })

        # Validate Completed Inventory format (non-negative number)
        if completed < 0 or not re.match(r"^\d+(\.\d+)?$", completed_txt.replace(",", "")):
            bad_quantities.append(f"{aud_name}: {completed_txt}")

        # Validate Audited Value & Damaged Value
        if aud_val < 0 or dam_val < 0:
            bad_values.append(f"{aud_name}: aud={aud_val_txt}, dam={dam_val_txt}")

        # Elapsed Timing format HH:mm (hours can exceed 24)
        if not re.match(r"^\d{2,}:\d{2}$", timing_txt):
            bad_timings.append(f"{aud_name}: {timing_txt}")

        # Progress format (contains number %)
        m_prog = re.search(r"(\d+(\.\d+)?)\s*%", prog_txt)
        if not m_prog or not (0.0 <= float(m_prog.group(1)) <= 100.0):
            bad_progresses.append(f"{aud_name}: {prog_txt}")

        # Status: known label
        known_statuses = ("yet to start", "in progress", "completed", "unknown")
        if status_txt.lower() not in known_statuses:
            bad_statuses.append(f"{aud_name}: {status_txt}")

        # Action: Finish, Reopen, or empty
        if action_txt.lower() not in ("finish", "reopen", ""):
            bad_actions.append(f"{aud_name}: {action_txt}")

    aud_comp_str = ", ".join(f"{r['name']}: {r['completed']:g}" for r in parsed_rows)
    tot_comp = sum(r['completed'] for r in parsed_rows)
    ck.add(group, "Completed Inventory is non-negative numeric quantity",
           not bad_quantities, ">= 0 numeric qty per auditor",
           "; ".join(bad_quantities[:5]) if bad_quantities else f"{aud_comp_str} (Total: {tot_comp:g})")

    aud_val_str = "; ".join(f"{r['name']}: aud={r['audited_val']:.2f}, dam={r['damaged_val']:.2f}"
                            for r in parsed_rows if r['audited_val'] > 0 or r['damaged_val'] > 0)
    if not aud_val_str:
        aud_val_str = "all auditors: 0.00 / 0.00"
    else:
        zero_cnt = sum(1 for r in parsed_rows if r['audited_val'] == 0 and r['damaged_val'] == 0)
        if zero_cnt > 0:
            aud_val_str += f"; ({zero_cnt} other auditor(s): 0.00)"
    ck.add(group, "Audited Value and Damaged Value are non-negative numeric",
           not bad_values, ">= 0 for Audited & Damaged Value",
           "; ".join(bad_values[:5]) if bad_values else aud_val_str)

    aud_timing_str = ", ".join(f"{r['name']}: {r['timing']}" for r in parsed_rows)
    ck.add(group, "Elapsed Timing format is HH:mm",
           not bad_timings, "HH:mm on every row",
           "; ".join(bad_timings[:5]) if bad_timings else aud_timing_str)

    aud_prog_str = ", ".join(f"{r['name']}: {r['progress']}" for r in parsed_rows)
    ck.add(group, "Progress is formatted percentage between 0% and 100%",
           not bad_progresses, "0% to 100% formatted percentage per auditor",
           "; ".join(bad_progresses[:5]) if bad_progresses else aud_prog_str)

    aud_st_str = ", ".join(f"{r['name']}: {r['status']}" for r in parsed_rows)
    ck.add(group, "Status is one of Yet to Start / In Progress / Completed / Unknown",
           not bad_statuses, "known status labels",
           "; ".join(bad_statuses[:5]) if bad_statuses else aud_st_str)

    # Status formula rules:
    # - Yet to Start: auditor has not started counting (completed == 0, progress == 0%)
    # - In Progress: auditor has started counting (completed > 0 or progress > 0%)
    # - Completed: auditor has finished audit
    bad_status_rules = []
    for r in parsed_rows:
        st_low = r["status"].lower()
        if st_low == "yet to start":
            m_p = re.search(r"(\d+(\.\d+)?)\s*%", r["progress"])
            prog_val = float(m_p.group(1)) if m_p else 0.0
            if r["completed"] > 0 or prog_val > 0.0:
                bad_status_rules.append(f"{r['name']}: status='Yet to Start' but completed={r['completed']}, prog={r['progress']}")
        elif st_low in ("in progress", "completed"):
            pass  # in progress or completed
    ck.add(group, "Status consistency: Yet to Start requires completed = 0 and Progress = 0%",
           not bad_status_rules, "Yet to Start rows have 0 completed / 0% progress",
           "; ".join(bad_status_rules[:5]) or f"{len(parsed_rows)} row(s) match")

    # Action link name rule:
    # - When auditor status is Completed -> Action shows 'Reopen'
    # - When auditor status is Yet to Start or In Progress -> Action shows 'Finish'
    bad_action_texts = []
    for r in parsed_rows:
        st_low = r["status"].lower()
        act_low = r["action"].lower()
        if st_low in ("completed", "complete"):
            if act_low != "reopen":
                bad_action_texts.append(f"{r['name']}: status='{r['status']}' expected Action='Reopen', got '{r['action']}'")
        elif st_low in ("yet to start", "in progress"):
            if act_low != "finish":
                bad_action_texts.append(f"{r['name']}: status='{r['status']}' expected Action='Finish', got '{r['action']}'")
    ck.add(group, "Action link: Completed auditors show 'Reopen', others show 'Finish'",
           not bad_action_texts, "Completed -> Reopen, Yet to Start / In Progress -> Finish",
           "; ".join(bad_action_texts[:5]) or f"{len(parsed_rows)} row(s) match")

    # Action disabled rule:
    # - In Resolution or Completed audit status -> Action links (Finish/Reopen) are DISABLED
    # - Active / In Progress audit status -> Action links are ENABLED
    audit_status = st.get("status", "")
    audit_is_closed = audit_status in ("In Resolution", "Completed", "Auto Completed")
    bad_action_disabled = []
    for r in parsed_rows:
        if audit_is_closed and not r["action_disabled"]:
            bad_action_disabled.append(f"{r['name']}: audit is '{audit_status}', expected Action disabled, but was enabled")
        elif (not audit_is_closed and audit_status == "In Progress") and r["action_disabled"]:
            bad_action_disabled.append(f"{r['name']}: audit is '{audit_status}', expected Action enabled, but was disabled")
    ck.add(group, f"Action disabled state conforms to audit status ('{audit_status}')",
           not bad_action_disabled,
           "Action disabled when audit In Resolution / Completed; enabled when In Progress",
           "; ".join(bad_action_disabled[:5]) or f"all {len(parsed_rows)} row(s) conform")

    # 4b. Per auditor: each figure against its formula (AUDITOR_FORMULAS) over that auditor's report rows.
    # The Auditor view has one row per (Item Code, Auditor); without it the Item view rows are used.
    aud_rows = (st.get("mode_rows") or {}).get("Auditor") or st["rows"]
    exp_aud = _expected_auditors(aud_rows, st["prices"], [r["name"] for r in parsed_rows])
    qty_cards = st.get("qty") or {}
    stock_total = qty_cards.get(_find("Stock Quantity", list(qty_cards)) or "")
    one_auditor = len(parsed_rows) == 1 and st.get("stock_rows") and stock_total
    tiles = st.get("tiles") or {}
    random_map = _key(tiles.get(_find("Mapping Type", list(tiles)) or "", "")) == "random"
    uncounted = [v for v in map(_row_vals, st["rows"]) if _calc(RANDOM_UNCOUNTED, **v)]
    # auditors who pressed Finish Audit in this Audit.py run (audit/finish_audit.py records them)
    finished = [_txt(n).lower() for n in (getattr(st.get("config"), "finished_auditors", None) or [])]
    for i, r in enumerate(parsed_rows):
        aud_label = r["name"]
        e = exp_aud[aud_label]
        want = e["Completed Inventory"]
        parts = _sample([f"{v['audited']:g}" for v in e["vals"] if v["audited"]], 8, " + ") or "0"
        ck.add(group, f"Auditor '{aud_label}' | Completed Inventory", _near(r["completed"], want),
               f"formula: Σ AuditedQty (excl damaged) over {e['counted_rows']} counted row(s) = {parts} = {want:g}",
               f"{r['completed']:g}")

        want_a, want_d = e["Audited Value"], e["Damaged Value"]
        if want_a is None or want_d is None:
            val_ok = r["audited_val"] >= 0 and r["damaged_val"] >= 0
            exp_val = ("formula: Audited = Σ(audited * price), Damaged = Σ(damaged * price); "
                       "no price (export not read) → Audited >= 0, Damaged >= 0")
        else:
            val_ok = _near(r["audited_val"], want_a) and _near(r["damaged_val"], want_d)
            a_parts = _sample([f"{v['audited']:g} * {v['price']:.2f}" for v in e["vals"] if v["audited"]], 6, " + ") or "0"
            d_parts = _sample([f"{v['damaged']:g} * {v['price']:.2f}" for v in e["vals"] if v["damaged"]], 6, " + ") or "0"
            exp_val = (f"formula: Audited = Σ(audited * price) = {a_parts} = {want_a:.2f}; "
                       f"Damaged = Σ(damaged * price) = {d_parts} = {want_d:.2f}")
        ck.add(group, f"Auditor '{aud_label}' | Audited & Damaged Value", val_ok, exp_val,
               f"Audited: {r['audited_val']:.2f}, Damaged: {r['damaged_val']:.2f}",
               finding="spec 01 F4/F5 (cost source / duplicate stock rows) may apply"
               if not val_ok and want_a is not None else "")

        m_prog = re.search(r"(\d+(\.\d+)?)\s*%", r["progress"])
        shown_prog = float(m_prog.group(1)) if m_prog else None
        a = _api_auditor(api_rows, aud_label)
        act_prog, finding = f"{r['progress']}", ""
        if a is not None:                                # this auditor's assigned rows and stock (AUDITOR_API)
            remaining = _qn(a.get("remainingcount"))
            names = {"counted_rows": _qn(a.get("auditedcount")), "completed": r["completed"],
                     "assigned_rows": e["on_sheet_counted"] + remaining,
                     "assigned_stock": _qn(a.get("assignedinventorycount"))}
            want_p, api_p = _calc(AUDITOR_PROGRESS_FORMULA, **names), _qn(a.get("progress"))
            prog_ok = shown_prog is not None and abs(shown_prog - want_p) <= 0.5 + 1e-6 and _near(api_p, want_p, 0.01)
            exp_prog = (f"formula: {AUDITOR_PROGRESS_FORMULA} → {_show(AUDITOR_PROGRESS_FORMULA, **names)}"
                        f" = {want_p:.2f} → {round_half_up(want_p)} % (counted_rows = AuditedCount "
                        f"{names['counted_rows']:g}; assigned_rows = {e['on_sheet_counted']} on-sheet row(s) counted + "
                        f"RemainingCount {remaining:g}; assigned_stock = AssignedInventoryCount {names['assigned_stock']:g})")
            act_prog = f"{r['progress']} (API progress {api_p:.2f})"
        elif one_auditor:                                # the only auditor is assigned every stock-sheet row
            names = {"counted_rows": e["counted_rows"], "completed": want,
                     "assigned_rows": st["stock_rows"], "assigned_stock": stock_total}
            want_p = _calc(AUDITOR_PROGRESS_FORMULA, **names)
            prog_ok = shown_prog is not None and abs(shown_prog - round_half_up(want_p)) <= 1
            exp_prog = (f"formula: {AUDITOR_PROGRESS_FORMULA} → {_show(AUDITOR_PROGRESS_FORMULA, **names)}"
                        f" = {want_p:.2f} → {round_half_up(want_p)} %")
            finding = "counted_rows here = report rows per item; the server counts each count line (spec 01 §4)"
        else:
            names = {"counted_rows": e["counted_rows"], "completed": want}
            prog_ok = shown_prog is not None and 0.0 <= shown_prog <= 100.0
            exp_prog = (f"formula: {_show(AUDITOR_PROGRESS_FORMULA, **names)}; {AUDITOR_API} reply not read, so "
                        f"assigned_rows / assigned_stock unknown ({len(parsed_rows)} auditors) → 0 % - 100 %")
        ck.add(group, f"Auditor '{aud_label}' | Progress %", prog_ok, exp_prog, act_prog,
               finding=finding if not prog_ok else "")

        if a is not None and random_map:                 # Random: the uncounted stock rows split evenly
            slice_names = {"uncounted": len(uncounted), "auditors": len(parsed_rows), "last": i == len(parsed_rows) - 1}
            want_rem = _calc(RANDOM_SLICE, **slice_names)
            ck.add(group, f"Auditor '{aud_label}' | Assigned rows (Random)", _near(remaining, want_rem),
                   f"formula: on-sheet rows counted + {RANDOM_SLICE} → {e['on_sheet_counted']} + "
                   f"{_show(RANDOM_SLICE, **slice_names)} = {e['on_sheet_counted']} + {want_rem:g} = "
                   f"{e['on_sheet_counted'] + want_rem:g}",
                   f"{e['on_sheet_counted']} + RemainingCount {remaining:g} = {e['on_sheet_counted'] + remaining:g}")

        timing_ok = bool(re.match(r"^\d{2,}:\d{2}$", r["timing"]))
        if _auditor_finished(aud_label, finished):
            # the auditor pressed Finish Audit in this run (user, 2026-11-17): Completed + Reopen, owner or not
            status_ok = r["status"].lower() == "completed" and r["action"].lower() == "reopen"
            exp_st = "auditor pressed Finish Audit → Status Completed, Action Reopen; Timing HH:mm"
        else:
            status_ok = bool(_calc(AUDITOR_STATUS_RULE, counted_rows=e["counted_rows"], status=r["status"]))
            want_st = "In Progress / Completed" if e["counted_rows"] > 0 else "Yet to Start / Completed / Unknown"
            exp_st = f"formula: counted_rows = {e['counted_rows']} → Status {want_st}; Timing HH:mm"
        ck.add(group, f"Auditor '{aud_label}' | Status & Elapsed Timing", timing_ok and status_ok, exp_st,
               f"Status: {r['status']}, Timing: {r['timing']}, Action: {r['action']}")

    if api_rows and random_map and parsed_rows:          # Random: every stock row's stock assigned once
        got = sum(_qn((_api_auditor(api_rows, r["name"]) or {}).get("assignedinventorycount")) for r in parsed_rows)
        counted_stock = [exp_aud[r["name"]]["on_sheet_stock"] for r in parsed_rows]
        uncounted_stock = sum(v["stock"] for v in uncounted)
        want = sum(counted_stock) + uncounted_stock
        ck.add(group, "Σ assigned stock of all auditors (Random)", _near(got, want),
               f"formula: Σ stock of the on-sheet rows each auditor counted + Σ stock of the {len(uncounted)} uncounted "
               f"row(s) = {' + '.join(f'{s:g}' for s in counted_stock)} + {uncounted_stock:g} = {want:g}",
               f"Σ AssignedInventoryCount = {got:g}")

    # 5. Assigned auditors check (spec §4 & Finding F13)
    assigned_tile = st.get("tiles", {}).get(_find("Auditor(s)", list(st.get("tiles", {}))) or "")
    if assigned_tile:
        assigned_names = [a.strip().lower() for a in assigned_tile.split(",") if a.strip()]
        aud_names_in_dlg = [r["name"].lower() for r in parsed_rows]
        matched = [a for a in assigned_names if any(a in d or d in a for d in aud_names_in_dlg)]
        ck.add(group, "Assigned auditors from header are present in dialog",
               len(matched) == len(assigned_names),
               f"formula: auditors in the Auditor(s) tile = {len(assigned_names)} auditor(s) in the dialog",
               f"{len(matched)}/{len(assigned_names)} present: {matched}")

    # 6. Total row (tfoot)
    tfoot_tr = dlg.locator("tfoot.p-datatable-tfoot tr").first
    if tfoot_tr.count() > 0:
        tfoot_tds = tfoot_tr.locator("td").all()
        if len(tfoot_tds) >= 8:
            tfoot_label = _txt(tfoot_tds[0].inner_text())
            total_completed = _qn(tfoot_tds[1].inner_text())
            total_aud_val = _qn(tfoot_tds[2].inner_text())
            total_dam_val = _qn(tfoot_tds[3].inner_text())
            tfoot_timing = _txt(tfoot_tds[4].inner_text())
            tfoot_prog = _txt(tfoot_tds[5].inner_text())
            tfoot_status = _txt(tfoot_tds[6].inner_text())
            tfoot_action = _txt(tfoot_tds[7].inner_text())

            ck.add(group, "Total row label is 'Total'", "total" in tfoot_label.lower(), "Total", tfoot_label)

            n_aud = len(parsed_rows)
            terms = lambda f, fmt: _sample([format(r[f], fmt) for r in parsed_rows], 8, " + ") or "0"

            sum_completed = sum(r["completed"] for r in parsed_rows)
            ck.add(group, "Total Completed Inventory = Σ auditor completed inventory",
                   _near(total_completed, sum_completed),
                   f"formula: Σ Completed Inventory of {n_aud} auditor(s) = {terms('completed', 'g')} = {sum_completed:g}",
                   f"{total_completed:g}")

            sum_aud_val = sum(r["audited_val"] for r in parsed_rows)
            ck.add(group, "Total Audited Value = Σ auditor audited values",
                   _near(total_aud_val, sum_aud_val, 0.05),
                   f"formula: Σ Audited Value of {n_aud} auditor(s) = {terms('audited_val', '.2f')} = {sum_aud_val:.2f}",
                   f"{total_aud_val:.2f}")

            sum_dam_val = sum(r["damaged_val"] for r in parsed_rows)
            ck.add(group, "Total Damaged Value = Σ auditor damaged values",
                   _near(total_dam_val, sum_dam_val, 0.05),
                   f"formula: Σ Damaged Value of {n_aud} auditor(s) = {terms('damaged_val', '.2f')} = {sum_dam_val:.2f}",
                   f"{total_dam_val:.2f}")

            placeholders = [tfoot_timing, tfoot_prog, tfoot_status, tfoot_action]
            all_dashes = all(p in ("--", "-", "") for p in placeholders)
            ck.add(group, "Total row Elapsed/Progress/Status/Action show '--'",
                   all_dashes, "-- for all non-additive columns", f"placeholders={placeholders}")
    else:
        ck.add(group, "Total row present in tfoot", False, "tfoot with Total row", "MISSING")

    # 7. Search box filter functionality + F9 (Total ignores search filter)
    if search_input.count() > 0 and len(parsed_rows) >= 2:
        test_auditor = parsed_rows[0]["name"]
        try:
            search_input.fill(test_auditor)
            _ui_settle(page, 800)
            filtered_tr = dlg.locator("tbody.p-datatable-tbody > tr").all()
            exp_cnt = sum(1 for r in parsed_rows if test_auditor.lower() in r["name"].lower())
            ck.add(group, f"Search box filters rows by auditor name ('{test_auditor}')",
                   len(filtered_tr) == exp_cnt, f"formula: auditor name contains '{test_auditor}' = {exp_cnt} row(s)",
                   f"{len(filtered_tr)} row(s)")

            # Check Spec 01 Finding F9: Total row ignores search filter
            if tfoot_tr.count() > 0:
                tfoot_tds = tfoot_tr.locator("td").all()
                if len(tfoot_tds) >= 2:
                    current_tfoot_comp = _qn(tfoot_tds[1].inner_text())
                    sum_all = sum(r["completed"] for r in parsed_rows)
                    sum_filt = sum(r["completed"] for r in parsed_rows if test_auditor.lower() in r["name"].lower())
                    if sum_all != sum_filt and _near(current_tfoot_comp, sum_all):
                        ck.add(group, "Total row ignores search filter (Spec 01 F9)",
                               False, f"formula: Σ Completed Inventory of filtered rows = {sum_filt:g}",
                               f"shows grand total {current_tfoot_comp:g} (spec 01 F9: Total ignores search filter)",
                               status="KNOWN", finding="spec 01 F9")
                    else:
                        ck.add(group, "Total row reflects search filtered rows",
                               _near(current_tfoot_comp, sum_filt) or _near(current_tfoot_comp, sum_all),
                               f"formula: Σ Completed Inventory of filtered rows = {sum_filt:g} "
                               f"(or all rows = {sum_all:g})", f"{current_tfoot_comp:g}")

            # Clear search
            search_input.fill("")
            search_input.dispatch_event("input")
            _ui_settle(page, 800)
            restored_tr = dlg.locator("tbody.p-datatable-tbody > tr").all()
            ck.add(group, "Clearing search restores all auditor rows",
                   len(restored_tr) == len(parsed_rows),
                   f"formula: all auditor rows = {len(parsed_rows)} row(s)", f"{len(restored_tr)} row(s)")
        except Exception as e:
            ck.error(group, "Auditor Insights search filter test", e)

    # 8. Close dialog
    try:
        close_btn.click()
        dlg.wait_for(state="hidden", timeout=5000)
        ck.add(group, "Auditor Insights dialog closes cleanly", True, "dialog hidden", "closed")
    except Exception as e:
        ck.add(group, "Auditor Insights dialog closes cleanly", False, "dialog hidden", f"close failed: {e}")


# ======================================================================
# PDF CONTENT + EXPORT CONTENT VALIDATION
# ======================================================================

# ----------------------------------------------------------------------
# DATA BLOCK — PDF
# ----------------------------------------------------------------------
PDF_QTY_TOL = 0.0005           # quantities (4 decimals are printed in the PDF)
PDF_VALUE_TOL = 0.05           # money

# Sections of "Verified Items (Counted)". heading: regex whose group 1 is the (N) count.
# rule: which UI rows belong in it. Names: as _pdf_vals() (stock, audited, variance, resolution_status ...)
PDF_SECTIONS = OrderedDict([
    ("Accepted", {"heading": r"Variance Resolved.{0,6}?Accepted\s*\((\d+)\)",
                  "rule": "resolution_status in ('Accepted', 'Recount Accepted')", "status_col": True}),
    ("Investigate", {"heading": r"Variance Unresolved.{0,6}?Investigate\s*\((\d+)\)",
                     "rule": "resolution_status == 'Under Investigation'", "status_col": True}),
    ("Matched", {"heading": r"Matched Items\s*\((\d+)\)",
                 "rule": "resolution_status == '' and audited == stock", "status_col": False}),
])
# Rows of the "Adjustment Report" table (a subset of the Accepted section: only rows that change stock)
ADJUSTMENT_ROWS = "resolution_status in ('Accepted', 'Recount Accepted') and variance != 0"
ADJUSTMENT_TYPE_WORD = {1: "Increase", -1: "Decrease"}
# Counting rules for the header cards
PDF_COUNTS = OrderedDict([
    ("stock_lines", "stock > 0"),          # "10 stock lines"
    ("counted_lines", "auditor != ''"),    # "11 lines counted" (a counted 0 is still counted)
])
PDF_SECTION_ENDS = [r"Verified Items \(Counted\)", r"Unverified Items Summary", r"Closure Note"]


# ----------------------------------------------------------------------
# DATA BLOCK — EXPORT (xlsx)
# ----------------------------------------------------------------------
# UI field (as in REQUIRED_FIELDS) -> (header in the exported sheet, kind)
EXPORT_FIELDS = OrderedDict([
    ("Item Code", ("ItemCode", "text")), ("Item Name", ("ItemName", "text")),
    ("UOM (Primary)", ("UOM (Base)", "text")), ("Category", ("CategoryName", "text")),
    ("Stock Quantity", ("StockQty", "num")), ("Audited Quantity", ("AuditedQty", "num")),
    ("Variance", ("Variance", "num")), ("Variance Value", ("VarianceValue", "money")),
    ("Variance Type", ("VarianceType", "text")), ("Damaged Qty", ("DamagedQty", "num")),
    ("Cross Audited Qty", ("CrossAuditedQty", "num")), ("Cross Damaged Qty", ("CrossDamagedQty", "num")),
    ("Stock Location", ("StockLocation", "text")), ("Audited Location", ("AuditedLocation", "text")),
    ("Audited Date", ("AuditedDate", "date")), ("Auditor", ("AuditorName", "text")),
    ("Coordinates", ("Coordinates", "text")), ("Declaration Note", ("DeclarationNote", "text")),
    ("Remarks", ("Remarks", "text")), ("Resolution Status", ("ResolutionStatus", "text")),
])
EXPORT_EXTRA_HEADERS = ["CostPrice", "VarianceHistory"]       # in the file, not a UI column
EXPORT_DATE_FORMAT = "%m-%d-%Y"
EXPORT_TOL = {"num": 0.00005, "money": 0.005}                 # export must hold the full precision


# ----------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------
def _close(a, b, tol):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def _flat(text):
    """One line of text; − – → -, thousands commas removed (regexes below rely on it)."""
    t = (text or "").replace("\u2212", "-").replace("\u2013", "-").replace("\u00a0", " ")
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)
    return " ".join(t.split())


def _pdf_pages(path, data):
    """Text of each page. pdftotext -raw (reading order) > pypdf > built-in extractor (one 'page')."""
    exe = shutil.which("pdftotext")
    if exe:
        try:
            out = subprocess.run([exe, "-raw", path, "-"], capture_output=True, timeout=60).stdout.decode("utf-8", "ignore")
            pages = out.split("\f")
            if pages and not pages[-1].strip():
                pages.pop()
            if any(p.strip() for p in pages):
                return pages
        except Exception:
            pass
    try:
        from pypdf import PdfReader  # type: ignore
        pages = [p.extract_text() or "" for p in PdfReader(path).pages]
        if any(p.strip() for p in pages):
            return pages
    except Exception:
        pass
    text = _ui_pdf_text(data)
    return [text] if text.strip() else []


def _pdf_vals(r, prices=None):
    v = _row_vals(r, prices)
    v["resolution_status"] = _blank(_cell(r, "Resolution Status"))
    return v


def _expected_pdf(item_rows):
    """What the PDF must show, from the Item-view rows (pure: rows in, numbers out)."""
    vals = [_pdf_vals(r) for r in item_rows]
    stock_lines = [v for v in vals if _calc(PDF_COUNTS["stock_lines"], **v)]
    counted = [v for v in vals if _calc(PDF_COUNTS["counted_lines"], **v)]
    adj = [v for v in vals if _calc(ADJUSTMENT_ROWS, **v)]
    sections = OrderedDict((k, [v for v in vals if _calc(s["rule"], **v)]) for k, s in PDF_SECTIONS.items())
    placed = {id(v) for rows in sections.values() for v in rows}
    inc, dec = [v for v in adj if v["variance"] > 0], [v for v in adj if v["variance"] < 0]
    return {
        "items": len({v["code"].upper() for v in vals}),
        "stock_lines": len({v["code"].upper() for v in stock_lines}),
        "locations": len({v["stock_location"] for v in stock_lines if v["stock_location"]}),
        "verified_units": sum(v["audited"] for v in counted), "lines_counted": len(counted),
        "adj_inc": sum(v["variance"] for v in inc), "adj_dec": -sum(v["variance"] for v in dec),
        "val_inc": sum(v["variance_value"] for v in inc), "val_dec": -sum(v["variance_value"] for v in dec),
        "not_counted": sum(1 for v in vals if _calc(CHIP_RULES["Unverified"], **v)),
        "adj": adj, "sections": sections, "unplaced": [v for v in vals if id(v) not in placed],
    }


def _pdf_after(flat, start_rx, end_rxs):
    """Text from the end of start_rx to the first of end_rxs (or the end)."""
    m = re.search(start_rx, flat, re.I)
    if not m:
        return None
    rest, end = flat[m.end():], None
    for rx in end_rxs:
        e = re.search(rx, rest, re.I)
        if e and (end is None or e.start() < end):
            end = e.start()
    return rest if end is None else rest[:end]


def _pdf_segments(section, codes):
    """{CODE: text from that code to the next code} inside one section."""
    pos = sorted((m.start(), c_) for c_ in codes for m in [re.search(re.escape(c_), section, re.I)] if m)
    out = {}
    for i, (p, c_) in enumerate(pos):
        out[c_.upper()] = section[p:pos[i + 1][0] if i + 1 < len(pos) else len(section)]
    return out


def _nums(seg):
    return [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?", seg)]


def _g(flat, rx, n=1):
    m = re.search(rx, flat, re.I)
    return m.group(n) if m else None


def _strip_page_chrome(page):
    """A page without the repeated header and the footer."""
    t = _flat(page)
    t = re.sub(r"Audit Summary Report Audit Name\s*:\s*\S+", " ", t)
    t = re.sub(r"Page \d+ of \d+", " ", t)
    t = re.sub(r"Generated by Stockount\s*\W?\s*\d{1,2}/\d{1,2}/\d{4}\s*\d{1,2}:\d{2}\s*[ap]m", " ", t)
    return " ".join(t.split())


# ----------------------------------------------------------------------
# PDF content
# ----------------------------------------------------------------------
def _check_pdf_content(ck, st, pages, where):
    group = f"PDF Content ({where})"
    flat = _flat("\n".join(pages))
    exp = _expected_pdf(st["rows"])
    tiles = st.get("tiles") or {}
    tile = lambda f: tiles.get(_find(f, list(tiles)) or "", "")
    add = lambda check, ok, want, got, **kw: ck.add(group, check, ok, want, got, **kw)

    # ---- header -------------------------------------------------------
    name = _g(flat, r"Audit Name\s*:\s*(\S+)")
    add("Audit Name = the audit", name == st["audit"], st["audit"], name)
    d = _g(flat, r"AUDIT DATE\s*(\d{1,2}/\d{1,2}/\d{4})")
    t = _g(flat, r"AUDIT DATE\s*\d{1,2}/\d{1,2}/\d{4}\s*(\d{1,2}:\d{2}\s*[ap]m)")
    ui_when = _parse_date(tile("Date & Time"), DATE_FORMATS["Date & Time"])
    try:
        t = re.sub(r"\s*([ap]m)$", r" \1", t, flags=re.I) if t else t      # "9:45am" and "9:45 am" both read
        pdf_when = datetime.strptime(f"{d} {t.upper()}", "%d/%m/%Y %I:%M %p") if d and t else None
    except ValueError:
        pdf_when = None
    if ui_when is None:
        ck.not_run(group, "Audit Date = Date & Time tile", "tile not read")
    else:
        add("Audit Date = Date & Time tile", bool(pdf_when) and abs((pdf_when - ui_when).total_seconds()) <= 60,
            ui_when.strftime("%d/%m/%Y %I:%M %p").lower(), f"{d} {t}")
    tile_auditors = sorted(a.strip() for a in (tile("Auditor(s)") or tile("Auditor") or "").split(",") if a.strip())
    ui_auditors = tile_auditors if tile_auditors else sorted({v["auditor"] for v in map(_pdf_vals, st["rows"]) if v["auditor"]})
    pdf_auditors = sorted(a.strip() for a in (_g(flat, r"AUDITORS\s*(.+?)\s*Audit Summary") or "").split(",") if a.strip())
    add("Auditors = tile or report rows", pdf_auditors == ui_auditors or pdf_auditors == sorted({v["auditor"] for v in map(_pdf_vals, st["rows"]) if v["auditor"]}), ui_auditors, pdf_auditors)
    pdf_type = _g(flat, r"AUDIT TYPE\s*(.+?)\s*ITEMS INVOLVED")
    if tile("Audit Type"):
        want_type = tile("Audit Type")
        ok_type = _key(want_type) in _key(pdf_type) if pdf_type else False
        add("Audit Type = tile", ok_type, want_type, pdf_type)
    m = re.search(r"ITEMS INVOLVED\s*(\d+)\s*(\d+) stock lines?\s*\W{0,3}\s*(\d+) locations?", flat, re.I)
    got = tuple(int(x) for x in m.groups()) if m else None
    add("Items involved / stock lines / locations", got == (exp["items"], exp["stock_lines"], exp["locations"]),
        f"formula: distinct ItemCode = {exp['items']}; distinct ItemCode with {PDF_COUNTS['stock_lines']} = "
        f"{exp['stock_lines']}; distinct StockLocation of those = {exp['locations']}", got)
    m = re.search(r"VERIFIED \(COUNTED\)\s*([\d.]+)\s*units\s*(\d+) lines counted", flat, re.I)
    counted_rule = PDF_COUNTS["counted_lines"]
    add("Verified (counted) units and lines", bool(m) and _close(m.group(1), exp["verified_units"], PDF_QTY_TOL)
        and int(m.group(2)) == exp["lines_counted"],
        f"formula: Σ audited where {counted_rule} = {exp['verified_units']:g} units; "
        f"count({counted_rule}) = {exp['lines_counted']} lines",
        f"{m.group(1)} units, {m.group(2)} lines" if m else None)
    cards = st.get("qty") or {}
    if "Audited" in cards:
        add("Verified units = Audited Quantity card", bool(m) and _close(m.group(1), cards["Audited"], TOLERANCE),
            f"formula: Verified units = Audited Quantity card = {cards['Audited']:g}", m.group(1) if m else None)
    m = re.search(r"ADJUSTED QTY\s*\+([\d.]+)\s*-([\d.]+)\s*Net\s*([-+]?[\d.]+)\s*units", flat, re.I)
    want = (exp["adj_inc"], exp["adj_dec"], exp["adj_inc"] - exp["adj_dec"])
    add("Adjusted Qty  +increase  -decrease  net",
        bool(m) and all(_close(a, b, PDF_QTY_TOL) for a, b in zip(m.groups(), want)),
        f"formula: rows {ADJUSTMENT_ROWS}: Σ variance > 0 = +{want[0]:g}; Σ |variance < 0| = -{want[1]:g}; "
        f"net = {want[0]:g} - {want[1]:g} = {want[2]:g}",
        "+%s -%s net %s" % m.groups() if m else None)
    m = re.search(r"ADJUSTMENT VALUE\s*\+([\d.]+)\s*-([\d.]+)", flat, re.I)
    want = (exp["val_inc"], exp["val_dec"])
    add("Adjustment Value  +increase  -decrease",
        bool(m) and all(_close(a, b, PDF_VALUE_TOL) for a, b in zip(m.groups(), want)),
        f"formula: rows {ADJUSTMENT_ROWS}: Σ variance_value > 0 = +{want[0]:.2f}; "
        f"Σ |variance_value < 0| = -{want[1]:.2f}",
        "+%s -%s" % m.groups() if m else None)

    # ---- adjustment report -------------------------------------------
    sec = _pdf_after(flat, r"Adjustment Report", PDF_SECTION_ENDS[:1])
    if sec is None:
        add("Adjustment Report section shown", False, "shown", "MISSING")
    else:
        segs = _pdf_segments(sec, [v["code"] for v in exp["adj"]])
        lost = [v["code"] for v in exp["adj"] if v["code"].upper() not in segs]
        extra = sorted(set(re.findall(r"\b[A-Z]{2,}\d+\b", sec)) - {v["code"].upper() for v in exp["adj"]})
        add("Adjustment Report lists exactly the adjusted rows", not lost and not extra,
            f"formula: {ADJUSTMENT_ROWS} = {len(exp['adj'])} row(s): {[v['code'] for v in exp['adj']]}",
            f"missing={lost} extra={extra}")
        bad = {"Adj. Qty": [], "Adj. Value": [], "Type": [], "Loc": [], "Stock Qty": []}
        for v in exp["adj"]:
            seg = segs.get(v["code"].upper())
            if seg is None:
                continue
            ns = _nums(seg)
            if not any(_close(n, v["variance"], PDF_QTY_TOL) for n in ns):
                bad["Adj. Qty"].append(f"{v['code']}: want {v['variance']:+g} in {seg[:70]!r}")
            if not any(_close(n, v["variance_value"], PDF_VALUE_TOL) for n in ns):
                bad["Adj. Value"].append(f"{v['code']}: want {v['variance_value']:+g}")
            word = ADJUSTMENT_TYPE_WORD[1 if v["variance"] > 0 else -1]
            if word.lower() not in seg.lower():
                bad["Type"].append(f"{v['code']}: want {word}")
            if v["stock_location"] and v["stock_location"] not in seg:
                bad["Loc"].append(f"{v['code']}: want {v['stock_location']}")
            if not any(_close(n, v["stock"], PDF_QTY_TOL) for n in ns):
                bad["Stock Qty"].append(f"{v['code']}: want {v['stock']:g}")
        col_rule = OrderedDict([
            ("Adj. Qty", ("variance", lambda v: f"{v['variance']:+g}")),
            ("Adj. Value", ("variance_value", lambda v: f"{v['variance_value']:+.2f}")),
            ("Type", ("Increase if variance > 0 else Decrease",
                      lambda v: ADJUSTMENT_TYPE_WORD[1 if v["variance"] > 0 else -1])),
            ("Loc", ("stock_location", lambda v: v["stock_location"] or "-")),
            ("Stock Qty", ("stock", lambda v: f"{v['stock']:g}")),
        ])
        for col, items in bad.items():
            rule, shown = col_rule[col]
            per_row = _sample([f"{v['code']}: {shown(v)}" for v in exp["adj"]])
            add(f"Adjustment Report: {col} per row", not items,
                f"formula: {rule} per adjusted row → {per_row}", "; ".join(items[:8]) or "match")
        m = re.search(r"TOTAL\s*([\d.]+)\s*([\d.]+)", sec)
        want = (sum(abs(v["variance"]) for v in exp["adj"]), sum(abs(v["variance_value"]) for v in exp["adj"]))
        qty_terms = _sample([f"{abs(v['variance']):g}" for v in exp["adj"]], 8, " + ") or "0"
        val_terms = _sample([f"{abs(v['variance_value']):.2f}" for v in exp["adj"]], 8, " + ") or "0"
        add("Adjustment Report TOTAL = Σ|adj. qty|, Σ|adj. value|",
            bool(m) and _close(m.group(1), want[0], PDF_QTY_TOL) and _close(m.group(2), want[1], PDF_VALUE_TOL),
            f"formula: Σ|variance| = {qty_terms} = {want[0]:g}; Σ|variance_value| = {val_terms} = {want[1]:.2f}",
            "%s / %s" % m.groups() if m else None)

    # ---- verified items sections -------------------------------------
    heads = [(k, re.search(s["heading"], flat, re.I)) for k, s in PDF_SECTIONS.items()]
    stops = [m_.start() for _, m_ in heads if m_] + [m_.start() for rx in PDF_SECTION_ENDS[1:]
                                                       for m_ in [re.search(rx, flat, re.I)] if m_]
    for key, m_ in heads:
        rows = exp["sections"][key]
        rule = PDF_SECTIONS[key]["rule"]
        if m_ is None:
            add(f"Section '{key}' shown", not rows, f"formula: {rule} = {len(rows)} row(s)", "heading not in the PDF")
            continue
        add(f"Section '{key}' count (N) = rows meeting its rule", int(m_.group(1)) == len(rows),
            f"formula: {rule} = {len(rows)} row(s)", m_.group(1))
        end = min([s for s in stops if s > m_.start()] or [len(flat)])
        seg_all = flat[m_.end():end]
        segs = _pdf_segments(seg_all, [v["code"] for v in rows])
        problems = []
        for v in rows:
            seg = segs.get(v["code"].upper())
            if seg is None:
                problems.append(f"{v['code']}: not listed")
                continue
            ns = _nums(seg)
            miss = []
            if not any(_close(n, v["audited"], PDF_QTY_TOL) for n in ns):
                miss.append(f"audited {v['audited']:g}")
            if not any(_close(n, v["variance"], PDF_QTY_TOL) for n in ns):
                miss.append(f"variance {v['variance']:+g}")
            for loc in (v["stock_location"], v["audited_location"]):
                if loc and loc not in seg:
                    miss.append(f"location {loc}")
            if PDF_SECTIONS[key]["status_col"] and v["resolution_status"] not in seg:
                miss.append(f"status {v['resolution_status']}")
            if miss:
                problems.append(f"{v['code']}: missing {', '.join(miss)}")
        row_want = _sample([f"{v['code']}: aud={v['audited']:g}, var={v['variance']:+g}" for v in rows])
        add(f"Section '{key}': every row correct", not problems,
            f"formula: per row audited, variance = audited - stock, locations"
            f"{', resolution status' if PDF_SECTIONS[key]['status_col'] else ''} → {row_want or 'no rows'}",
            "; ".join(problems[:8]) or f"{len(rows)} row(s) match")
    add("Every report row is in a section", not exp["unplaced"],
        f"formula: rows meeting none of {list(PDF_SECTIONS)} = 0 of {len(st['rows'])} row(s)",
        [f"{v['code']} (status {v['resolution_status'] or '-'})" for v in exp["unplaced"]] or "none left out")

    # ---- unverified summary ------------------------------------------
    m = re.search(r"ITEMS ASSIGNED\s*(\d+)\s*COUNTED\s*(\d+)\s*NOT COUNTED \(UNVERIFIED\)\s*(\d+)", flat, re.I)
    want = (exp["items"], exp["lines_counted"], exp["not_counted"])
    got = tuple(int(x) for x in m.groups()) if m else None
    add("Unverified Items Summary: assigned / counted / not counted", got == want,
        f"formula: distinct ItemCode = {want[0]}; count({counted_rule}) = {want[1]}; "
        f"{CHIP_RULES['Unverified']} = {want[2]}", got)

    # ---- closure note and footer -------------------------------------
    note_want = getattr(st["config"], "closure_note", None) or getattr(st["config"], "fc_closure_note", None)
    pages_clean = [_strip_page_chrome(p) for p in pages]
    idx = next((i for i, p in enumerate(pages_clean) if "Closure Note" in p), None)
    if idx is None:
        add("Closure Note section shown", False, "shown", "MISSING")
    else:
        after = pages_clean[idx].split("Closure Note", 1)[1].strip()
        note_page = idx
        if not after and idx + 1 < len(pages_clean):
            after, note_page = pages_clean[idx + 1].strip(), idx + 1
        add("Closure Note has text", bool(after), "the note typed at Complete Audit", after[:120] or "EMPTY")
        if note_want:
            add("Closure Note = the note entered", _key(note_want) in _key(after), note_want, after[:120])
        if len(pages_clean) > 1:
            add("Closure Note heading and its text are on the same page", note_page == idx,
                "same page", f"heading on page {idx + 1}, text on page {note_page + 1}")
    n = len(pages)
    gen = re.findall(r"Generated by Stockount\s*\W?\s*\d{1,2}/\d{1,2}/\d{4}\s*\d{1,2}:\d{2}\s*[ap]m", flat, re.I)
    foot = [(int(a), int(b)) for a, b in re.findall(r"Page (\d+) of (\d+)", flat)]     # either order of the two footer parts
    add("Footer 'Generated by Stockount · date · Page i of N' on every page",
        len(foot) == n == len(gen) and [f[0] for f in foot] == list(range(1, n + 1)) and all(f[1] == n for f in foot),
        f"formula: 1 footer per page × {n} page(s) = Page 1 of {n} ... Page {n} of {n}, {n} 'Generated by' line(s)",
        f"pages {foot or 'none'}, generated lines {len(gen)}")
    add("Audit Name in the header of every page", len(re.findall(r"Audit Name\s*:\s*" + re.escape(st["audit"]), flat)) == n,
        f"formula: 1 per page × {n} page(s) = {n}x {st['audit']}",
        len(re.findall(r"Audit Name\s*:\s*" + re.escape(st["audit"]), flat)))


def _pdf_signature(pages):
    """The PDF without the 'Generated ... ' time, to compare two downloads."""
    return re.sub(r"Generated by Stockount\s*\W?\s*\d{1,2}/\d{1,2}/\d{4}\s*\d{1,2}:\d{2}\s*[ap]m", "",
                  _flat("\n".join(pages)))


def _check_pdf(ck, st, page, label, pools):
    """REPLACES the old _check_pdf. Downloads the PDF from every place it is offered (table button, ⋮ menu),
    checks it is a PDF, checks its CONTENT against the UI (first download), and that the downloads match."""
    group, codes = "Actions", sorted({_row_vals(r)["code"] for r in st["rows"]})
    sources = [("table button", lambda: pools["table"][label].click())]
    menu_label = _find("Download PDF", list(pools["menu"]))
    if menu_label:
        def from_menu():
            page.locator(f"{UI_SUMMARY} button.dots-btn").first.click()
            page.wait_for_timeout(800)
            page.locator(f"{UI_SUMMARY} .dropdown-container").first.locator(
                "button, a, li", has_text=re.compile(rf"^\s*{re.escape(menu_label)}\s*$")).first.click()
        sources.append(("⋮ menu", from_menu))
    done = OrderedDict()
    for where, click in sources:
        with page.expect_download(timeout=90000) as info:
            click()
        path = os.path.join(ck.folder, f"{ck.prefix}Audit_Summary_{_key(where)}.pdf")
        info.value.save_as(path)
        data = open(path, "rb").read()
        pages = _pdf_pages(path, data)
        text = "\n".join(pages)
        found = [x for x in codes if x in text]
        is_pdf = data[:5] == b"%PDF-"
        if is_pdf and not text.strip():
            ck.add(group, f"Download PDF ({where}) is a PDF", True, "a PDF", f"{len(data)} bytes")
            ck.not_run(group, f"Download PDF ({where}) content", "PDF text is not readable (install poppler-utils or pypdf)")
            continue
        named = st["audit"] in text
        ck.add(group, f"Download PDF ({where}) is a PDF that names the audit and lists every item",
               is_pdf and named and len(found) == len(codes),
               f"a PDF naming {st['audit']} with {len(codes)} item code(s)",
               f"{len(data)} bytes, {len(pages)} page(s); audit named={named}; items found {len(found)}/{len(codes)}; "
               f"missing={[x for x in codes if x not in found][:10]}")
        done[where] = pages
        if len(done) == 1:                                   # full content check once
            try:
                _check_pdf_content(ck, st, pages, where)
            except Exception as e:
                ck.error("PDF Content", f"content check ({where})", e)
        _ui_close_menu(page)
    if len(done) > 1:
        (w1, p1), (w2, p2) = list(done.items())[:2]
        same = _pdf_signature(p1) == _pdf_signature(p2)
        ck.add("PDF Content", f"PDF from {w1} = PDF from {w2} (ignoring the generated time)", same,
               "same content", "same" if same else "DIFFERENT")


# ----------------------------------------------------------------------
# Export content
# ----------------------------------------------------------------------
def _exp_records(df):
    return [{_key(k): _txt(v) for k, v in r.items()} for _, r in df.iterrows()]


def _exp_as_ui(rec):
    """An export row under the UI field names, so _row_vals() and CHIP_RULES work on it."""
    return OrderedDict((ui, rec.get(_key(h), "")) for ui, (h, _k) in EXPORT_FIELDS.items())


def _exp_equal(kind, field, ev, uv):
    if kind in ("num", "money"):
        return _close(_qn(ev), _qn(uv), EXPORT_TOL[kind])
    if kind == "date":
        if not _blank(ev) and not _blank(uv):          # both empty (e.g. an item not audited): equal
            return True
        a, b = _parse_date(ev, EXPORT_DATE_FORMAT), _parse_date(uv, DATE_FORMATS["Audited Date"])
        return bool(a and b and a.date() == b.date())
    return _blank(ev).lower() == _blank(uv).lower()


def _check_export(ck, st):
    group, sheets = "Export Content", st["sheets"]
    if not sheets:
        ck.not_run(group, "Export content", "the export was not downloaded or read")
        return
    chips = REQUIRED_FIELDS["Audit Summary Counts"]
    all_name = _find("All", list(sheets))
    recs = {n: _exp_records(df) for n, df in sheets.items()}

    # ---- one sheet per chip ------------------------------------------
    for chip in chips:
        label = _find(chip, list(sheets))
        known = chip == "Not Found" and label is None
        ck.add(group, f"Sheet for '{chip}' exists", label is not None, "a sheet", label or "MISSING",
               status="KNOWN" if known else None, finding="spec 03 F13" if known else "")

    # ---- headers ------------------------------------------------------
    want_heads = [h for h, _k in EXPORT_FIELDS.values()]
    for name, df in sheets.items():
        cols = [_key(c_) for c_ in df.columns]
        lost = [h for h in want_heads if _key(h) not in cols]
        extra = [c_ for c_ in df.columns if _key(c_) not in {_key(h) for h in want_heads + EXPORT_EXTRA_HEADERS}]
        ck.add(group, f"Sheet '{name}': headers", not lost and not extra, ", ".join(want_heads),
               f"missing={lost} unexpected={extra}")

    # ---- rows per sheet = rows of the chip -----------------------------
    lists, ui_chips = st.get("chip_lists") or {}, st["chips"]
    rows_ui = {_row_vals(r)["code"].upper() for r in st["rows"]}
    all_ui = [_exp_as_ui(r) for r in recs.get(all_name, [])]
    for chip in chips:
        label = _find(chip, list(sheets))
        if label is None:
            continue
        codes = [r.get("itemcode", "").upper() for r in recs[label]]
        if chip == "All":
            want_codes, source = rows_ui, "UI rows"
        elif chip in lists:
            want_codes, source = lists[chip], "the rows the chip lists in the UI"
        else:
            want_codes = {_row_vals(r)["code"].upper() for r in all_ui if _calc(CHIP_RULES[chip], **_row_vals(r))}
            source = f"rule {CHIP_RULES[chip]} on the All sheet"
        chip_label = _find(chip, list(ui_chips))
        count = ui_chips.get(chip_label) if chip_label else None
        dup = sorted({c_ for c_ in codes if codes.count(c_) > 1})
        diff_extra, diff_lost = sorted(set(codes) - want_codes), sorted(want_codes - set(codes))
        ck.add(group, f"Sheet '{label}': rows = {chip} chip", set(codes) == want_codes and not dup
               and (count is None or len(codes) == count),
               f"formula: {source} = {len(want_codes)} row(s); chip count = {count}",
               f"{len(codes)} row(s); only in export={diff_extra[:6]} only in UI={diff_lost[:6]} repeated={dup[:6]}")

    if all_name is None:
        return
    # ---- All sheet vs the UI table, field by field ---------------------
    ui = {_row_vals(r)["code"].upper(): r for r in st["rows"]}
    for field, (h, kind) in EXPORT_FIELDS.items():
        if field == "Item Code":
            continue
        if _find(field, st["headers"]) is None:
            ck.not_run(group, f"All sheet: {field} = UI table", "no such column in the UI table")
            continue
        bad = []
        for rec in recs[all_name]:
            code = rec.get("itemcode", "").upper()
            r = ui.get(code)
            if r is None:
                bad.append(f"{code}: not in the UI table")
            elif not _exp_equal(kind, field, rec.get(_key(h), ""), _cell(r, field)):
                bad.append(f"{code}: export {rec.get(_key(h), '')!r} vs UI {_cell(r, field)!r}")
        ck.add(group, f"All sheet: {field} = UI table", not bad,
               f"formula: export {h} == UI {field} per row ({kind}) = {len(recs[all_name])} row(s) equal",
               "; ".join(bad[:8]) or f"{len(recs[all_name])} row(s) equal")

    # ---- the file's own arithmetic (needs no UI) ------------------------
    price = lambda rec: _qn(rec.get("costprice", ""))
    na_codes = (lists.get(NOT_AUDITED_CHIP))
    audited = [rec for rec in recs[all_name] if not _not_audited(_row_vals(_exp_as_ui(rec)), na_codes)]
    for field, rule in ROW_FORMULAS.items():
        h, kind = EXPORT_FIELDS[field]
        bad, want_rows = [], []
        for rec in audited:
            v = _row_vals(_exp_as_ui(rec), {rec.get("itemcode", "").upper(): price(rec)})
            want = _calc(rule, **v)
            want_rows.append(_row_sample(field, rule, v, want))
            got = rec.get(_key(h), "")
            ok = _blank(got) == _blank(want) if isinstance(want, str) else _close(_qn(got), want, EXPORT_TOL[kind])
            if not ok:
                bad.append(f"{v['code']}: file {got!r} vs {want if isinstance(want, str) else round(want, 6)!r}")
        ck.add(group, f"All sheet: {field} = {rule} (file's own numbers)", not bad,
               f"formula: {rule} (price = CostPrice) on {len(audited)} audited row(s) → {_sample(want_rows)}",
               "; ".join(bad[:8]) or f"{len(audited)} row(s) match")
    bad = [f"{rec.get('itemcode')}: {rec.get('auditeddate')!r}" for rec in recs[all_name]
           if _blank(rec.get("auditeddate")) and not _parse_date(rec["auditeddate"], EXPORT_DATE_FORMAT)]
    ck.add(group, f"All sheet: AuditedDate format {EXPORT_DATE_FORMAT}", not bad, EXPORT_DATE_FORMAT,
           "; ".join(bad[:8]) or "all dates match")

    # ---- totals = Quantity Summary cards --------------------------------
    cards = st.get("qty") or {}
    for card, col in (("Stock", "stockqty"), ("Audited", "auditedqty"), ("Damaged", "damagedqty")):
        if card in cards:
            tot = sum(_qn(r.get(col, "")) for r in recs[all_name])
            ck.add(group, f"All sheet: Σ {col} = {card} card", _near(tot, cards[card]),
                   f"formula: Σ {col} over {len(recs[all_name])} row(s) = {card} card = {cards[card]:g}",
                   f"Σ {col} = {round(tot, 6):g}")


def _check_charts(ck, st):
    group, charts = "Charts", st["charts"]
    bar_data, pie_data = charts.get("bar") or {}, charts.get("pie") or {}
    shown = OrderedDict((_txt(ds.get("label")), ds.get("data") or []) for ds in bar_data.get("datasets", []))
    cats = [_txt(x) for x in bar_data.get("labels", [])]
    for field in REQUIRED_FIELDS[group]:
        ck.add(group, f"{field} series shown", _find(field, list(shown)) is not None, "shown", f"series={list(shown)}")
    if not st["prices"]:
        ck.not_run(group, "Chart values", "no cost price (export not read)")
        return
    bar, overall, pie, facts = _expected_charts(st["rows"], st["prices"])
    st["chart_facts"] = facts
    for field, rule in CHART_FORMULAS.items():
        label = _find(field, list(shown))
        if label is None:
            continue
        got = {cat: float(v or 0) for cat, v in zip(cats, shown[label])}
        want = {cat: vals[field] for cat, vals in bar.items() if cat != "-"}   # no bar for uncategorised items
        bad = [f"{cat}: chart {got.get(cat, 0.0):g} vs {w:g}" for cat, w in want.items() if not _near(got.get(cat, 0.0), w)]
        bad += [f"{cat}: chart {v:g}, not expected" for cat, v in got.items() if cat not in want and abs(v) > TOLERANCE]
        ck.add(group, f"{field} per category = Σ {rule}", not bad,
               f"formula: Σ {rule} per category (counted items) → "
               + ("; ".join(f"{cat}: {w:.2f}" for cat, w in want.items()) or "no category"),
               "; ".join(bad) or "; ".join(f"{cat}: {v:g}" for cat, v in got.items()))
    labels = [_txt(x) for x in pie_data.get("labels", [])]
    data = (pie_data.get("datasets") or [{}])[0].get("data") or []
    got = dict(zip(labels, data))
    for field in CHART_FORMULAS:
        label = _find(field, labels)
        ck.add(group, f"Overall Variance {field} % = {DOUGHNUT_FORMULA.split(' if ')[0]}",
               label is not None and _near(got.get(label), pie[field], 0.01),
               f"formula: {DOUGHNUT_FORMULA} (value = Σ {CHART_FORMULAS[field]}, stock_value = total variance) → "
               f"{_show(DOUGHNUT_FORMULA, value=overall[field], stock_value=facts.get('total_variance', facts['stock_value']))}"
               f" = {pie[field]}",
               got.get(label) if label else "MISSING")
    st["doughnut_sum"] = sum(float(x or 0) for x in data)


def _ui_facts(st):
    """Named values for KNOWN_FINDINGS."""
    vals = [_row_vals(r) for r in st["rows"]]
    unverified = [v for v in vals if _calc(CHIP_RULES["Unverified"], **v)]
    excess = [v for v in vals if _calc(CHIP_RULES["Excess Line Item"], **v)]
    conflict = [v for v in vals if _calc(CHIP_RULES["Location Conflict"], **v)]
    return {"off_sheet_counted": (st.get("chart_facts") or {}).get("off_sheet_counted", []),
            "doughnut_sum": st.get("doughnut_sum", 100),
            "conflict_unverified_or_excess": sum(1 for v in conflict if v in unverified or v in excess),
            "unverified_negative": sum(1 for v in unverified if v["variance"] < 0),
            "export_read": bool(st["sheets"]),
            "export_not_found_sheet": any(_key(n) == "notfound" for n in st["sheets"]),
            "completed": st["status"] in ("Completed", "Auto Completed"),
            "not_found_with_auditor": sum(1 for v in vals if _calc(CHIP_RULES["Not Found"], **v))}


def _check_findings(ck, st):
    facts = _ui_facts(st)
    for fid, title, cond in KNOWN_FINDINGS:
        seen = bool(_calc(cond, **facts))
        ck.add("Spec findings", f"{fid}: {title}", True, f"formula: {cond} = False (not seen)",
               f"seen ({_show(cond, **facts)} = True; {facts})" if seen else f"not seen ({_show(cond, **facts)} = False)",
               status="KNOWN" if seen else "PASS", finding=f"spec {fid}" if seen else "")


# ----------------------------------------------------------------------
# Move to Not Found (Complete Audit popup) — changes the audit
# ----------------------------------------------------------------------
def _named_chips(chips):
    """{required chip name: count} for the chips of REQUIRED_FIELDS (labels matched like everywhere else)."""
    out = {}
    for name in REQUIRED_FIELDS["Audit Summary Counts"]:
        label = _find(name, list(chips))
        if label is not None:
            out[name] = chips[label]
    return out


def _check_moved_rows(ck, group, moved, rows_after, completer, expect=None):
    """Every row of the step-2 items against expect (default MOVE_NOT_FOUND_EXPECT; pure: tested offline)."""
    for field, (ok_rule, known_rule, finding) in (expect or MOVE_NOT_FOUND_EXPECT).items():
        bad, known = [], []
        for code in moved:
            r = rows_after.get(code.upper())
            if r is None:
                bad.append(f"{code}: row missing after the move")
                continue
            v = dict(_row_vals(r), resolution_status=_blank(_cell(r, "Resolution Status")), completer=completer)
            if _calc(ok_rule, **v):
                continue
            (known if known_rule and _calc(known_rule, **v) else bad).append(f"{code}: {_cell(r, field)!r}")
        status = "FAIL" if bad else "KNOWN" if known else "PASS"
        ck.add(group, f"Step-2 items: {field} ({ok_rule})", not bad,
               f"formula: {ok_rule} on all {len(moved)} step-2 row(s) → {_sample(moved, 8)}",
               "; ".join((bad or known)[:10]) + (f" (known: {known_rule})" if known and not bad else "")
               or f"{len(moved)} row(s) meet it",
               status=status, finding=f"spec {finding}" if (bad or known) and finding else "")


def check_move_to_not_found(page, config, folder=None) -> bool:
    """Complete Audit > Yes > "Unverified items" step with config.complete_choice ("Move to Not Found" or
    "Keep as Unverified") > Proceed to Resolution on config.ap_audit_name, then check the popup count, the
    chips and every step-2 item against UNVERIFIED_CHOICE_RULES[choice] (spec 03 §3.1-3.2).
    CHANGES THE AUDIT: it goes In Resolution (with Move to Not Found the Un Verified items become Not Found)."""
    from audit.complete_audit_popup import _enter_resolution      # imported here: that module imports this one
    from audit.stock_audit_checks import Results
    audit = config.ap_audit_name
    choice = getattr(config, "complete_choice", "Move to Not Found")
    if choice not in UNVERIFIED_CHOICE_RULES:
        raise ValueError(f"complete_choice {choice!r} is not one of {list(UNVERIFIED_CHOICE_RULES)}")
    chip_rules, row_rules = UNVERIFIED_CHOICE_RULES[choice]
    folder, prefix = (folder, "") if folder else run_files(config, f"Summary_{_key(choice)}")
    os.makedirs(folder, exist_ok=True)
    section(f"UNVERIFIED ITEMS: {choice.upper()}  >  {audit}")
    group, ck = f"Unverified step: {choice}", _UIChecks(page, folder, prefix)
    try:
        _ui_open_summary(page, config)
        _ui_summarize(page, "Item")
        _ui_chip(page, "All")
        before = _named_chips(_ui_chips(page))
        status = _ui_tiles(page).get("Status", "")
        _ui_chip(page, _find(NOT_AUDITED_CHIP, list(_ui_chips(page))))
        moved = [_row_vals(r)["code"] for r in _ui_all_rows(page)]
        _ui_chip(page, "All")
        name = page.locator(".profile-name").first
        completer = _txt(name.text_content()) if name.count() else ""
        print(f"   before: status={status}, chips={before}, Un Verified items={moved}, completer={completer!r}")
        if not moved:
            ck.not_run(group, choice, f"no Un Verified item, so no 'Unverified items' step (status {status})")
        else:
            res, flow = Results(), {}
            _enter_resolution(page, config, res, flow)
            popup = flow.get("unverified")
            ck.add(group, "Unverified step: 'There are N items not counted' = Un Verified items",
                   popup is not None and _calc(MOVE_NOT_FOUND_POPUP, popup=popup, before=before),
                   f"formula: {MOVE_NOT_FOUND_POPUP} → N = {before.get('Unverified')}",
                   f"N = {popup}; choice {choice!r}; popup steps: {[row[1] for row in res.rows]}")
            _ui_open_summary(page, config)
            _ui_summarize(page, "Item")
            _ui_chip(page, "All")
            after_status = _ui_tiles(page).get("Status", "")
            ck.add(group, f"Status after Proceed to Resolution = {MOVE_NOT_FOUND_STATUS}",
                   after_status == MOVE_NOT_FOUND_STATUS, MOVE_NOT_FOUND_STATUS, after_status)
            after = _named_chips(_ui_chips(page))
            for chip, rule in chip_rules.items():
                want = _calc(rule, before=before, moved=len(moved))
                ck.add(group, f"{chip} chip after '{choice}' = {rule}", after.get(chip) == want,
                       f"formula: {rule} → {_show(rule, before=before, moved=len(moved))} = {want}",
                       f"{after.get(chip)} (before {before.get(chip)}, step-2 items {len(moved)})")
            rows_after = {_row_vals(r)["code"].upper(): r for r in _ui_all_rows(page)}
            _check_moved_rows(ck, group, moved, rows_after, completer, row_rules)
    except Exception as e:
        ck.error(group, choice, e)
    path = save_to_run_report(config, ck.rows) or _ui_write_report(ck, folder, config,
                                                                   name=f"Unverified_{_key(choice)}.xlsx")
    counts = Counter(r["Status"] for r in ck.rows)
    print("\n" + "=" * 70 + f"\n  UNVERIFIED ITEMS: {choice.upper()} — {audit}\n" + "=" * 70)
    print(f"  {dict(counts)}   report: {path}")
    return counts.get("FAIL", 0) == 0


# ----------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------
def validate_summary_ui(page, config, folder=None, label="UI") -> bool:
    """Validate the Audit Summary page of config.ap_audit_name from the UI against the data block above.
    Read-only: nothing that changes the audit is clicked. In an Audit.py run the checks go into the run
    workbook (audit/run_report.py), and the downloaded export, PDFs and FAIL screenshots go straight into the
    run folder named Summary_<label>_...; run on its own, all of it (plus Summary_UI_Validation.xlsx) goes into
    a new Summary_<label>_<audit>_<time> folder in config.e2e_output_dir."""
    audit = config.ap_audit_name
    folder, prefix = (folder, "") if folder else run_files(config, f"Summary_{label}")
    os.makedirs(folder, exist_ok=True)
    section(f"AUDIT SUMMARY UI VALIDATION  >  {audit}")
    ck, st = _UIChecks(page, folder, prefix), {"audit": audit, "config": config, "prices": {}, "sheets": {},
                                               "export_path": None}
    try:
        st["tab"], st["list_row"] = _ui_open_summary(page, config)
        _ui_summarize(page, "Item")
        _ui_chip(page, "All")
        st["tiles"], st["chips"] = _ui_tiles(page), _ui_chips(page)
        st["status"] = st["tiles"].get(_find("Status", list(st["tiles"])) or "", "")
        bar = page.locator(f"{UI_SUMMARY} div.progress-bar").first
        st["progress_bar"] = float(bar.get_attribute("aria-valuenow")) if bar.count() and bar.get_attribute("aria-valuenow") else None
        st["qty"], st["value"] = _ui_cards(page, "Qty"), _ui_cards(page, "Value")
        st["headers"], st["rows"] = _ui_headers(page), _ui_all_rows(page)
        st["charts"], st["options"] = _ui_charts(page), _ui_options(page)
        print(f"   read: {len(st['rows'])} row(s), chips={dict(st['chips'])}, status={st['status']}")
    except Exception as e:
        ck.error("Audit Summary", "open and read the page", e)
        path = save_to_run_report(config, ck.rows) or _ui_write_report(ck, folder, config)
        print(f"   report: {path}")
        return False
    try:
        st["export_path"], st["sheets"] = _ui_export(page, folder, prefix)
        st["prices"] = _ui_prices(st["sheets"])
    except Exception as e:
        ck.error("Actions", "Export download", e)
    steps = [("Audit Information", lambda: _check_information(ck, st)),
             ("Audit Summary Counts", lambda: _check_counts(ck, st, page)),
             ("Export Content", lambda: _check_export(ck, st)),
             ("Quantity Summary", lambda: _check_quantities(ck, st)),
             ("Audit Report - Table Fields", lambda: _check_table(ck, st)),
             ("Charts", lambda: _check_charts(ck, st)),
             ("Summary Options", lambda: _check_options(ck, st, page)),
             ("Actions", lambda: _check_actions(ck, st, page)),
             ("Spec findings", lambda: _check_findings(ck, st))]
    for group, fn in steps:
        try:
            fn()
        except Exception as e:
            ck.error(group, "checks of this group", e)
    path = save_to_run_report(config, ck.rows) or _ui_write_report(ck, folder, config)
    counts = Counter(r["Status"] for r in ck.rows)
    print("\n" + "=" * 70 + f"\n  AUDIT SUMMARY UI VALIDATION — {audit}\n" + "=" * 70)
    print(f"  {dict(counts)}   report: {path}")
    return counts.get("FAIL", 0) == 0
