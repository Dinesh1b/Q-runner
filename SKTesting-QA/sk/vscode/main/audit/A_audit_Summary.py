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
        return stock != audited

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


def A_audit_Summary(page, config):
    """Audit Summary checks: the UI validation (fields, values and formulas of the data block in
    the UI VALIDATION section), then the Excel compare. config.summary_ui_validation /
    config.summary_excel_compare = False skip either one. config.summary_move_not_found = True also runs
    Complete Audit > Move to Not Found > Proceed to Resolution (the audit goes In Resolution), checks it
    and validates the page again."""
    ok = True
    if getattr(config, "summary_ui_validation", True):
        ok = validate_summary_ui(page, config) and ok
    if getattr(config, "summary_move_not_found", False):
        ok = check_move_to_not_found(page, config) and ok
        if getattr(config, "summary_ui_validation", True):
            ok = validate_summary_ui(page, config) and ok
    if getattr(config, "summary_excel_compare", True):
        ok = _excel_compare(page, config) and ok
    return ok


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
    ("Location Conflict", "stock_location != audited_location"),
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
    ("cost", "max_cost if on_sheet else 0"),               # highest stock-sheet cost; off-sheet = 0 (F5)
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
    ("Auditor Insights", {"where": "top", "show": "True", "check": "open"}),
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
    its code is in the list the NOT_AUDITED_CHIP chip shows, or, without that list, it meets the chip's rule."""
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
    pie = OrderedDict((ds, _calc(DOUGHNUT_FORMULA, value=v, stock_value=stock_value)) for ds, v in overall.items())
    return bar, overall, pie, {"stock_value": stock_value, "off_sheet_counted": off_sheet}


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


def _ui_export(page, folder):
    """Download Export; {sheet: rows under its ItemCode header row} and the file path."""
    with page.expect_download(timeout=60000) as info:
        page.locator(f"{UI_SUMMARY} button.warning-button", has_text="Export").first.click()
    path = os.path.join(folder, info.value.suggested_filename or "Audit Summary Report.xlsx")
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
    def __init__(self, page, folder):
        self.page, self.folder, self.rows = page, folder, []

    def add(self, group, check, ok, expected, actual, status=None, finding=""):
        status = status or ("PASS" if ok else "FAIL")
        shot = ""
        if status == "FAIL" and sum(r["Status"] == "FAIL" for r in self.rows) < 40:
            shot = os.path.join(self.folder, f"FAIL_{len(self.rows) + 1:03d}_{_key(check)[:30]}.png")
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
    progress, label, names = _expected_progress(st["rows"], stock_rows, st["qty"])
    shown = re.search(r"(\d+(?:\.\d+)?)\s*%", get("Progress"))
    bar = st.get("progress_bar")
    ok = bool(shown) and float(shown.group(1)) == label and (bar is None or _near(bar, progress, 0.01))
    ck.add(group, "Progress = formula", ok, f"{progress:.2f} -> label {label}% ({PROGRESS_FORMULA}; {names})",
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
               f"{want} ({CHIP_RULES.get(field, '-')})", chips[label])
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
                ck.add(group, f"{field} lists {chips[label]} row(s)", False, chips[label],
                       f"{actual} (spec {known[0]}: count and list rules differ)", status="KNOWN",
                       finding=f"spec {known[0]}")
                continue
            ck.add(group, f"{field} lists {chips[label]} row(s)", len(listed) == chips[label], chips[label], actual)
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
        ck.add(group, f"{field} (Qty) = Σ {qty_rule}", _near(st["qty"][label], want), want, st["qty"][label])
        priced = [v for v in vals if v["price"] is not None]
        if len(priced) < len(vals):
            ck.not_run(group, f"{field} (Value)", f"no price for {len(vals) - len(priced)} row(s) (export not read)")
            continue
        want = sum(_calc(value_rule, **v) for v in vals)
        got = st["value"].get(_find(field, list(st["value"])) or "")
        ck.add(group, f"{field} (Value) = Σ {value_rule}", _near(got, want), round(want, 2), got)


def _check_table(ck, st):
    group, heads = "Audit Report - Table Fields", st["headers"]
    missing = [f for f in REQUIRED_FIELDS[group] if _find(f, heads) is None]
    ck.add(group, "All table fields shown", not missing, ", ".join(REQUIRED_FIELDS[group]),
           f"missing={missing}; order on screen: {heads}")
    not_audited_codes = (st.get("chip_lists") or {}).get(NOT_AUDITED_CHIP)
    audited_rows = [r for r in st["rows"] if not _not_audited(_row_vals(r), not_audited_codes)]
    for field, rule in ROW_FORMULAS.items():           # variance formulas: audited line items only
        bad, checked = [], 0
        for r in audited_rows:
            v = _row_vals(r, st["prices"])
            if "price" in rule and v["price"] is None:
                continue
            checked += 1
            want = _calc(rule, **v)
            got = {"Variance": v["variance"], "Variance Value": v["variance_value"],
                   "Variance Type": v["variance_type"]}.get(field)
            if not (got == want if isinstance(want, str) else _near(got, want)):
                bad.append(f"{v['code']}: {got} vs {want}")
        if not checked:
            ck.not_run(group, f"{field} = {rule}", "no price (export not read)")
        else:
            ck.add(group, f"{field} = {rule}", not bad, f"{checked} row(s) match", "; ".join(bad[:8]) or f"{checked} row(s) match")
    fmt = DATE_FORMATS["Audited Date"]
    bad = [f"{_row_vals(r)['code']}: {_cell(r, 'Audited Date')!r}" for r in st["rows"]
           if _blank(_cell(r, "Audited Date")) and not _parse_date(_cell(r, "Audited Date"), fmt)]
    ck.add(group, f"Audited Date format {fmt}", not bad, fmt, "; ".join(bad[:8]) or "all dates match")
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
    ck.add(group, "Line items that were not audited", True, source, f"{len(codes)} item(s): {codes[:20]}",
           status="PASS" if codes else "NOT RUN")
    for field, (rule, finding) in NOT_AUDITED_EXPECT.items():
        if not not_audited:
            break
        bad = [f"{_row_vals(r)['code']}: {_cell(r, field)!r}" for r in not_audited if not _calc(rule, **_row_vals(r))]
        ck.add(group, f"Not audited: {field} ({rule})", not bad, f"{len(not_audited)} row(s) meet it",
               "; ".join(bad[:10]) or f"{len(not_audited)} row(s) meet it",
               finding=f"spec {finding}" if bad and finding else "")
    for field, rule in AUDITED_EXPECT.items():
        bad = [f"{_row_vals(r)['code']}: {_cell(r, field)!r}" for r in audited_rows if not _calc(rule, **_row_vals(r))]
        ck.add(group, f"Audited: {field} shown ({rule})", not bad, f"{len(audited_rows)} row(s) meet it",
               "; ".join(bad[:10]) or f"{len(audited_rows)} row(s) meet it")


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
                   "unique rows", f"{len(rows)} row(s); repeated={dup[:5]}{note}")
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
            ck.add(group, f"{option}: rows add up to the Item view per item", not bad,
                   f"stock {spec['stock']}, audited and damaged summed", "; ".join(bad[:6]) or f"{len(per)} item(s) match")
            bad = []
            for r in unit_rows:                          # not audited line items: variance 0 (NOT_AUDITED_EXPECT)
                v = _row_vals(r, st["prices"])
                not_audited = _not_audited(v, (st.get("chip_lists") or {}).get(NOT_AUDITED_CHIP))
                want = 0 if not_audited else _calc(ROW_FORMULAS["Variance"], **v)
                if not _near(v["variance"], want):
                    bad.append(f"{v['code']}: {v['variance']:g} vs {want:g}")
            ck.add(group, f"{option}: Variance = {ROW_FORMULAS['Variance']} (audited) / 0 (not audited)", not bad,
                   "every row", "; ".join(bad[:6]) or f"{len(unit_rows)} row(s) match")
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
               (label is not None) == want, "shown" if want else "hidden", "shown" if label else "hidden")
        if label and rule.get("disabled"):
            want_off = bool(_calc(rule["disabled"], **facts))
            off = pool[label].is_disabled()
            ck.add(group, f"{field} {'disabled' if want_off else 'enabled'} (status {st['status']})", off == want_off,
                   "disabled" if want_off else "enabled", "disabled" if off else "enabled")
        if not label:
            continue
        try:
            how = rule.get("check")
            if how == "open":
                pool[label].click()
                dlg = page.locator("div.auditor-summary-dialog").first
                dlg.wait_for(state="visible", timeout=15000)
                heads = [_txt(h) for h in dlg.locator("thead th").all_inner_texts()]
                dlg.locator("button.close-btn").first.click()
                dlg.wait_for(state="hidden", timeout=5000)
                ck.add(group, f"{field} opens and closes", bool(heads), "dialog with columns", f"columns={heads}")
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


def _check_pdf(ck, st, page, label, pools):
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
    for where, click in sources:
        with page.expect_download(timeout=90000) as info:
            click()
        path = os.path.join(ck.folder, f"Audit_Summary_{_key(where)}.pdf")
        info.value.save_as(path)
        data = open(path, "rb").read()
        text = _ui_pdf_text(data)
        found = [x for x in codes if x in text]
        is_pdf = data[:5] == b"%PDF-"
        if is_pdf and not text.strip():
            ck.add(group, f"Download PDF ({where}) is a PDF", True, "a PDF", f"{len(data)} bytes")
            ck.not_run(group, f"Download PDF ({where}) lists every item", "PDF text is not readable without a PDF library")
            continue
        figures = {k: (m.group(1) if (m := re.search(rx, text)) else "-") for k, rx in PDF_FIGURES.items()}
        named = st["audit"] in text
        ck.add(group, f"Download PDF ({where}) is a PDF that names the audit and lists every item",
               is_pdf and named and len(found) == len(codes),
               f"a PDF naming {st['audit']} with {len(codes)} item code(s)",
               f"{len(data)} bytes; audit named={named}; items found {len(found)}/{len(codes)}; "
               f"missing={[x for x in codes if x not in found][:10]}; PDF figures {figures}")
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
           f"header with the table fields + {len(codes)} row(s)",
           f"{len(lines)} line(s); rows found {len(found)}/{len(codes)}; header missing={lost}")


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
               "; ".join(f"{cat}: {w:g}" for cat, w in want.items()),
               "; ".join(bad) or "; ".join(f"{cat}: {v:g}" for cat, v in got.items()))
    labels = [_txt(x) for x in pie_data.get("labels", [])]
    data = (pie_data.get("datasets") or [{}])[0].get("data") or []
    got = dict(zip(labels, data))
    for field in CHART_FORMULAS:
        label = _find(field, labels)
        ck.add(group, f"Overall Variance {field} % = {DOUGHNUT_FORMULA.split(' if ')[0]}",
               label is not None and _near(got.get(label), pie[field], 0.01),
               f"{pie[field]} (value {overall[field]:g} ÷ stock value {facts['stock_value']:g})",
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
        ck.add("Spec findings", f"{fid}: {title}", True, "not seen", f"seen ({cond}; {facts})" if seen else "not seen",
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
        ck.add(group, f"Step-2 items: {field} ({ok_rule})", not bad, f"{len(moved)} row(s) meet it",
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
    folder = folder or os.path.join(getattr(config, "e2e_output_dir", os.getcwd()),
                                    f"Summary_{_key(choice)}_{audit}_{datetime.now():%m%d_%H%M}")
    os.makedirs(folder, exist_ok=True)
    section(f"UNVERIFIED ITEMS: {choice.upper()}  >  {audit}")
    group, ck = f"Unverified step: {choice}", _UIChecks(page, folder)
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
                   f"N = {before.get('Unverified')} ({MOVE_NOT_FOUND_POPUP})",
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
                ck.add(group, f"{chip} chip after '{choice}' = {rule}", after.get(chip) == want, want,
                       f"{after.get(chip)} (before {before.get(chip)}, step-2 items {len(moved)})")
            rows_after = {_row_vals(r)["code"].upper(): r for r in _ui_all_rows(page)}
            _check_moved_rows(ck, group, moved, rows_after, completer, row_rules)
    except Exception as e:
        ck.error(group, choice, e)
    path = _ui_write_report(ck, folder, config, name=f"Unverified_{_key(choice)}.xlsx")
    counts = Counter(r["Status"] for r in ck.rows)
    print("\n" + "=" * 70 + f"\n  UNVERIFIED ITEMS: {choice.upper()} — {audit}\n" + "=" * 70)
    print(f"  {dict(counts)}   report: {path}")
    return counts.get("FAIL", 0) == 0


# ----------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------
def validate_summary_ui(page, config, folder=None) -> bool:
    """Validate the Audit Summary page of config.ap_audit_name from the UI against the data block above.
    Read-only: nothing that changes the audit is clicked. Writes Summary_UI_Validation.xlsx into folder
    (default: a new Summary_UI_<audit>_<time> folder in config.e2e_output_dir, the report folder)."""
    audit = config.ap_audit_name
    folder = folder or os.path.join(getattr(config, "e2e_output_dir", os.getcwd()),
                                    f"Summary_UI_{audit}_{datetime.now():%m%d_%H%M}")
    os.makedirs(folder, exist_ok=True)
    section(f"AUDIT SUMMARY UI VALIDATION  >  {audit}")
    ck, st = _UIChecks(page, folder), {"audit": audit, "config": config, "prices": {}, "sheets": {}, "export_path": None}
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
        path = _ui_write_report(ck, folder, config)
        print(f"   report: {path}")
        return False
    try:
        st["export_path"], st["sheets"] = _ui_export(page, folder)
        st["prices"] = _ui_prices(st["sheets"])
    except Exception as e:
        ck.error("Actions", "Export download", e)
    steps = [("Audit Information", lambda: _check_information(ck, st)),
             ("Audit Summary Counts", lambda: _check_counts(ck, st, page)),
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
    path = _ui_write_report(ck, folder, config)
    counts = Counter(r["Status"] for r in ck.rows)
    print("\n" + "=" * 70 + f"\n  AUDIT SUMMARY UI VALIDATION — {audit}\n" + "=" * 70)
    print(f"  {dict(counts)}   report: {path}")
    return counts.get("FAIL", 0) == 0
