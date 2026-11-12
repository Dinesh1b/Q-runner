"""
Audit Summary page — test cases (TC-SUM-xx), read-only.

Runs on Config.ap_audit_name and checks every part of the page against its own report rows:
  A  Audit Details tiles and top buttons      H  Search
  B  Auditor Insights dialog                  I  Column filters
  C  Category Wise Variance (bar chart)       J  Sort
  D  Overall Variance (doughnut chart)        K  Paging
  E  Filter badges                            L  Export
  F  Summarize As views                       M  Combined filters
  G  Qty / Value cards                        N  No side effects

The cost price of each item comes from the page itself: the item is searched with the Value
cards on (card value / qty), or Variance Value / Variance when a search can't single it out.
Archive, Complete Audit and the Auditor Insights "Finish" are never clicked.

Writes Summary_Page_Tests_<run>.xlsx (Test Cases + Bugs) under Config.e2e_output_dir.
"""
import math
import os
import re
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime

import pandas as pd

from audit.A_audit_Summary import (
    N, Config as SummaryCfg, audit_row, click_audit, click_badge, select_branch, select_navigation_option,
    wait_spinner,
)
from audit.e2e_complete_resolution import _sign_ok
from audit.e2e_stock_audit import SUMMARIZE_AS, _metrics
from audit.finish_complete_flow import _close_guide
from audit.settings_tests import SettingsRun, write_report
from audit.stock_audit_checks import ROWS_JS, _clean, _num

SUMMARY   = "app-audit-summary"
SUMMARIZE = f"{SUMMARY} h6:has-text('Summarize As') ~ p-dropdown"
TOGGLE    = f"{SUMMARY} div.summary-toggle button.toggle-btn"
SEARCH    = f"{SUMMARY} input[placeholder='Search Item Code / Item Name']"
HEADERS   = f"{SUMMARY} thead th"
BODY      = f"{SUMMARY} tbody.p-datatable-tbody"
PAGINATOR = f"{SUMMARY} .p-paginator"
PAGE_SIZE = f"{PAGINATOR} p-dropdown"
EXPORT    = f"{SUMMARY} button.warning-button:has-text('Export')"
INSIGHTS  = "div.auditor-summary-dialog"
OVERLAY   = ".p-column-filter-overlay:visible"
PANEL_LI  = ".p-dropdown-panel:visible li.p-dropdown-item"

TILES = ["Audit Name", "Date & Time", "Auditor(s)", "Group", "Audit Type", "Frequency - Mapping Type",
         "Progress", "Status"]
TOP_BUTTONS = ["Stock Audit", "Auditor Insights", "Archive", "Complete Audit"]      # never clicked
INSIGHTS_HEADERS = ["Auditor", "Completed Inventory", "Audited Value", "Damaged Value", "Elapsed Timing",
                    "Progress", "Status", "Action"]
INSIGHTS_SUMS = ["Completed Inventory", "Audited Value", "Damaged Value"]
BAR_DATASETS = ["Available Value", "Stock Loss", "Excess Value"]
CARD_COLUMNS = [("stock", "Stock Quantity"), ("audited", "Audited Quantity"), ("damaged", "Damaged Qty")]
FILTER_COLUMNS = ["Category", "Audited Location", "UOM (Primary)", "Variance Type", "Auditor",
                  "Declaration Note", "Resolution Status", "Remarks"]
SPLIT_COLUMNS = {"Stock Location", "Audited Location", "Auditor"}       # cells like "Unassigned, w1-4252"
NUMERIC = ["Stock Quantity", "Audited Quantity", "Variance", "Variance Value", "Damaged Qty",
           "Cross AuditedQty", "Cross DamagedQty"]
DATES = ["Audited Date"]
COMPOSITE = ["Stock Location", "Audited Location", "Variance History", "Coordinates"]
PAGE_SIZES = ["25", "50", "100", "200"]
EXPORT_CORE = ["Item Code", "Item Name", "Category", "Stock Location", "Audited Location", "UOM",
               "Stock Quantity", "Audited Quantity", "Variance", "Variance Value", "Variance Type",
               "Damaged Qty", "Auditor"]
EXPORT_ALIASES = {"UOM": ["UOM (Primary)", "UOM (Base)", "Primary UOM"], "Category": ["Category Name"],
                  "Stock Quantity": ["Stock Qty"], "Audited Quantity": ["Audited Qty"],
                  "Damaged Qty": ["Damaged Quantity"], "Auditor": ["Auditor Name"]}   # export headers: ItemCode, StockQty...
EXPORT_NUMBERS = ["Stock Quantity", "Audited Quantity", "Variance", "Variance Value", "Damaged Qty"]
EXPORT_SHEETS = {"Not Found": "Line Items Not Found"}      # badge -> export sheet name, where they differ
DATE_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m-%d-%y %H:%M", "%m-%d-%Y %H:%M",
                "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M", "%b %d, %Y, %I:%M %p")
MAX_COST_SEARCH = 40       # items whose cost price is read by searching them
MAX_FILTER_OPTIONS = 5     # options tried per column filter
NO_MATCH = "zz-no-such-item-zz"


# ======================================================
# ROW RULES
# ======================================================
def _unverified(r):
    """Never counted: no auditor and no audited date. The page shows such a line's variance as "-" or,
    in newer builds, as minus the stock with type Negative, yet lists it under Un Verified."""
    if _clean(r.get("Variance")) == "-":
        return True
    return _qty(r, "Audited Quantity") == 0 and _blank(r.get("Auditor")) == "-" and _blank(r.get("Audited Date")) == "-"


def _qty(r, col):
    return _num(r.get(col))


def _eq(a, b, tol=0.05):
    a, b = float(a or 0), float(b or 0)
    return abs(a - b) <= max(tol, abs(b) * 1e-4)


def _blank(v):
    return "-" if _clean(v) in ("", "-") else _clean(v)


def _cell_values(r, column):
    v = _clean(r.get(column))
    return {_blank(p) for p in (v.split(",") if column in SPLIT_COLUMNS else [v])}


# Badge -> rule every row listed under it must meet (Positive / Negative include Excess lines / Not Found)
RULES = OrderedDict([
    ("All", lambda r: True),
    ("Matched Line Item", lambda r: not _unverified(r) and _num(r.get("Variance")) == 0),
    ("Un Verified", _unverified),
    ("Not Found", lambda r: not _unverified(r) and _qty(r, "Stock Quantity") > 0 and _qty(r, "Audited Quantity") == 0),
    ("Excess Line Item", lambda r: _qty(r, "Stock Quantity") == 0 and _qty(r, "Audited Quantity") > 0),
    ("Positive Variance", lambda r: not _unverified(r) and _num(r.get("Variance")) > 0),
    ("Negative Variance", lambda r: not _unverified(r) and _num(r.get("Variance")) < 0),
    ("Location Conflict", lambda r: N.norm(r.get("Stock Location")) != N.norm(r.get("Audited Location"))),
    ("Cross Checked Audit", lambda r: _clean(r.get("Cross AuditedQty")) not in ("", "-", "0")),
    ("Damaged Report", lambda r: _qty(r, "Damaged Qty") > 0),
])
UNSURE_RULES = {"Cross Checked Audit"}     # rule not confirmed: mismatches are reported as info


def chart_expected(rows, costs):
    """Per category: Available = Σ min(stock, audited) × cost, Stock Loss = Σ |negative variance value|
    (Not Found included), Excess = Σ positive variance value (excess lines included).
    Un Verified rows are left out. Also returns the items whose cost price is unknown."""
    exp, unknown = OrderedDict(), set()
    for r in rows:
        if _unverified(r):
            continue
        e = exp.setdefault(_blank(r.get("Category")), dict.fromkeys(BAR_DATASETS, 0.0))
        value = _num(r.get("Variance Value"))
        e["Stock Loss" if value < 0 else "Excess Value"] += abs(value)
        held = min(_qty(r, "Stock Quantity"), _qty(r, "Audited Quantity"))
        if held and r["Item Code"] not in costs:
            unknown.add(r["Item Code"])
        elif held:
            e["Available Value"] += held * costs[r["Item Code"]]
    return exp, unknown


def by_auditor(view_rows, costs):
    """Σ audited / damaged qty and value per auditor (lower-case name), from the Auditor view."""
    out, unknown = defaultdict(lambda: dict.fromkeys(("audited", "damaged", "audited_value", "damaged_value"), 0.0)), set()
    for r in view_rows:
        name = _blank(r.get("Auditor"))
        if name == "-":
            continue
        audited, damaged = _qty(r, "Audited Quantity"), _qty(r, "Damaged Qty")
        e = out[name.lower()]
        e["audited"] += audited
        e["damaged"] += damaged
        if (audited or damaged) and r["Item Code"] not in costs:
            unknown.add(r["Item Code"])
        elif audited or damaged:
            e["audited_value"] += audited * costs[r["Item Code"]]
            e["damaged_value"] += damaged * costs[r["Item Code"]]
    return out, unknown


# ======================================================
# PAGE HELPERS
# ======================================================
def _settle(page, ms=1500):
    wait_spinner(page)
    page.wait_for_timeout(ms)


def _need(st, *keys):
    """NOT RUN outcome when base data a case needs could not be read."""
    missing = [k for k in keys if not st.get(k)]
    return {"status": "NOT RUN", "actual": f"no base data: {', '.join(missing)}"} if missing else None


def _not_run(actual):
    return {"status": "NOT RUN", "actual": actual}


def _evidence(page, st, what):
    """Screenshot the failing state, once per case: interactive cases put the page back before they
    end, so the runner's own FAIL screenshot no longer shows the failure."""
    if st.get("shot") or not st.get("folder"):
        return
    path = os.path.join(st["folder"], f"{st.get('case', 'TC-SUM')}_{what}.png")
    try:
        page.screenshot(path=path, full_page=True)
        st["shot"] = path
    except Exception:
        pass


def _page_rows(page):
    headers = [_clean(h) for h in page.locator(HEADERS).all_inner_texts()]
    return [dict(zip(headers, [_clean(c) for c in cells]))
            for cells in page.locator(BODY).first.evaluate(ROWS_JS) if len(cells) == len(headers)]


def _wait_table(page, ok=None, timeout_ms=10000):
    """Wait until the table has finished refreshing after a search or sort. A refresh first empties the table
    (spinner) while the badges still show the old counts, so: the rows and badges read the same twice in a
    row, the table is empty only when the All badge is 0, and `ok(rows)` holds when given. Returns False
    after `timeout_ms` without raising, so the caller then sees the page as it is."""
    prev = None
    for _ in range(max(1, timeout_ms // 400)):
        rows, badges = _page_rows(page), read_badges(page)
        snap = ([r.get("Item Code") for r in rows], tuple(badges.items()))
        ready = (bool(rows) or badges.get("All") == 0) and (ok is None or ok(rows))
        if ready and snap == prev:
            return True
        prev = snap if ready else None
        page.wait_for_timeout(400)
    return False


def _pager(page, which):
    return page.locator(f"{PAGINATOR} button.p-paginator-{which}").first


def _enabled(btn):
    return btn.count() > 0 and btn.is_enabled() and "p-disabled" not in (btn.get_attribute("class") or "")


def _first_page(page):
    if _enabled(_pager(page, "first")):
        _pager(page, "first").click()
        _settle(page, 1000)


def walk_pages(page, limit=100):
    """Rows of each page of the report table; leaves it on page 1."""
    _first_page(page)
    pages = [_page_rows(page)]
    while len(pages) < limit and _enabled(_pager(page, "next")):
        _pager(page, "next").click()
        _settle(page, 1000)
        pages.append(_page_rows(page))
    _first_page(page)
    return pages


def read_rows(page):
    return [r for rows in walk_pages(page) for r in rows]


def read_badges(page):
    out = OrderedDict()
    for t in page.locator(f"{SUMMARY} span.badge-custom").all_inner_texts():
        m = re.match(r"^(.*?)\s*\((\d+)\)$", _clean(t))
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def read_tiles(page):
    tiles = OrderedDict()
    for t in page.locator(f"{SUMMARY} div.audit-info-tile .tile-row").all():
        label = _clean(t.locator(".tile-label").inner_text())
        tiles[label] = _clean(t.inner_text())[len(label):].strip()
    return tiles


def _dropdown_options(page, dropdown):
    dropdown.click()
    page.wait_for_timeout(600)
    options = [_clean(t) for t in page.locator(PANEL_LI).all_inner_texts()]
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    return options


def _summarize(page, option, tries=3):
    """Switch Summarize As to `option`. The dropdown click times out now and then (page still busy), so each
    try waits for the spinner, uses short timeouts and closes any half-open panel before trying again."""
    dd = page.locator(SUMMARIZE).first
    item = page.locator(PANEL_LI, has_text=re.compile(rf"^\s*{re.escape(option)}\s*$")).first
    last = None
    for _ in range(tries):
        if _clean(dd.locator(".p-dropdown-label").inner_text()) == option:
            return
        _settle(page, 500)
        try:
            dd.scroll_into_view_if_needed(timeout=5000)
            dd.click(timeout=8000)
            item.wait_for(state="visible", timeout=5000)
            item.click(timeout=5000)
            _settle(page, 2000)
        except Exception as e:
            last = e
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)
    label = _clean(dd.locator(".p-dropdown-label").inner_text())
    if label != option:
        raise RuntimeError(f"Summarize As stayed on {label!r}, not {option!r}"
                           + (f" ({str(last).splitlines()[0]})" if last else ""))


def read_views(page, options):
    """Rows of every Summarize As option except Item; back on Item afterwards."""
    views = {}
    try:
        for option in options:
            if option != "Item":
                _summarize(page, option)
                views[option] = read_rows(page)
    finally:
        _summarize(page, "Item")
    return views


def _toggle(page, mode):
    btn = page.locator(TOGGLE, has_text=mode).first
    if "active" not in (btn.get_attribute("class") or ""):
        btn.click()
        _settle(page, 1200)


def _value_cards(page):
    _toggle(page, "Value")
    try:
        return _metrics(page)
    finally:
        _toggle(page, "Qty")


def _search(page, term, timeout_ms=10000):
    """Type `term` in the search box and wait for the table to refresh to rows that all match it. A fixed
    wait read the rows mid-refresh at times (old rows, or an empty table with the old badges). If the rows
    still don't match after `timeout_ms`, the caller sees them as they are."""
    box = page.locator(SEARCH).first
    if box.input_value() == term:
        return
    box.fill(term)
    _settle(page, 2500)
    _wait_table(page, lambda rows: len(_matches(rows, term)) == len(rows), timeout_ms)


def derive_costs(page, rows):
    """{item code: cost price} and where each came from: "search" (the item searched with the
    Value cards on: card value / qty) or "row" (Variance Value / Variance)."""
    items = OrderedDict((r["Item Code"], r) for r in rows)
    costs, source = {}, {}
    _toggle(page, "Value")
    try:
        for code, r in list(items.items())[:MAX_COST_SEARCH]:
            _search(page, code)
            if [x.get("Item Code") for x in _page_rows(page)] != [code]:
                continue                      # the code is part of another code: the cards mix items
            value = _metrics(page)
            for metric, col in CARD_COLUMNS:
                if _qty(r, col):
                    costs[code], source[code] = value.get(metric, 0) / _qty(r, col), "search"
                    break
    finally:
        _search(page, "")
        _toggle(page, "Qty")
    for code, r in items.items():
        if code not in costs and not _unverified(r) and _num(r.get("Variance")):
            costs[code], source[code] = _num(r.get("Variance Value")) / _num(r.get("Variance")), "row"
    return costs, source


# ---- Auditor Insights
def _open_insights(page):
    dlg = page.locator(INSIGHTS).first
    if not dlg.is_visible():
        page.locator(f"{SUMMARY} button.text-app-primary", has_text="Auditor Insights").first.click()
        dlg.wait_for(state="visible", timeout=15000)
        _settle(page, 1500)
    return dlg


def _close_insights(page):
    dlg = page.locator(INSIGHTS).first
    if dlg.is_visible():
        dlg.locator("button.close-btn").first.click()
        dlg.wait_for(state="hidden", timeout=5000)


def read_insights(page):
    """Headers, auditor rows and the Total row of Auditor Insights (the dialog is left open)."""
    dlg = _open_insights(page)
    headers = [_clean(h) for h in dlg.locator("thead th").all_inner_texts()]
    rows = [dict(zip(headers, [_clean(c) for c in cells])) for cells in dlg.locator("tbody").first.evaluate(ROWS_JS)
            if len(cells) == len(headers) and _clean(cells[0]).lower() != "total"]
    total = dict(zip(headers, [_clean(t) for t in dlg.locator("tfoot td").all_inner_texts()]))
    return headers, rows, total


def _insights_search(page, term):
    _open_insights(page).locator("input[placeholder='Search...']").first.fill(term)
    page.wait_for_timeout(1500)


# ---- Charts (Chart.js data through the Angular debug API)
CHARTS_JS = """() => [...document.querySelectorAll('app-audit-summary p-chart')].map(pc => {
    const card = pc.closest('.cardDetail');
    let cmp = null;
    try { cmp = window.ng ? window.ng.getComponent(pc) : null; } catch (e) {}
    return {card: card ? card.className : '', type: cmp ? cmp.type : pc.getAttribute('type'),
            data: cmp && cmp.data ? JSON.parse(JSON.stringify(cmp.data)) : null};
})"""


def read_charts(page):
    return {("bar" if "barChart" in ch["card"] else "pie" if "pieChart" in ch["card"] else ch["type"]): ch
            for ch in page.evaluate(CHARTS_JS)}


def _bar(st):
    """Categories, {dataset: {category: value}} and dataset colours, or None when unreadable."""
    data = (st.get("charts") or {}).get("bar", {}).get("data")
    if not data:
        return None
    labels = [_clean(l) for l in data.get("labels", [])]
    sets, colours = OrderedDict(), []
    for ds in data.get("datasets", []):
        sets[_clean(ds.get("label"))] = {lab: float(v or 0) for lab, v in zip(labels, ds.get("data", []))}
        colours.append(str(ds.get("backgroundColor", "")).lower())
    return labels, sets, colours


def _pie(st):
    """Labels, values and colours of the doughnut, or None when unreadable."""
    data = (st.get("charts") or {}).get("pie", {}).get("data")
    if not data:
        return None
    ds = (data.get("datasets") or [{}])[0]
    colours = ds.get("backgroundColor") or []
    return ([_clean(l) for l in data.get("labels", [])], [float(v or 0) for v in ds.get("data", [])],
            [str(c).lower() for c in (colours if isinstance(colours, list) else [colours])])


# ---- Column filters
NO_SCROLL_FOCUS = """() => { if (window.__noScrollFocus) return; window.__noScrollFocus = true;
    const focus = HTMLElement.prototype.focus;
    HTMLElement.prototype.focus = function (opts) { return focus.call(this, Object.assign({}, opts, {preventScroll: true})); }; }"""


ALL = "__all__"     # _set_filter: Select All
STATES_JS = """ov => [...ov.querySelectorAll('.custom-filter-option')].map(o => [
    o.classList.contains('custom-filter-select-all') ? '__all__' : (o.querySelector('label') || {}).innerText || '',
    !!o.querySelector(".p-checkbox-box[data-p-highlight='true']")])"""


def _open_filter(page, column):
    """Open the column's filter overlay; None when the column has no filter."""
    th = page.locator(HEADERS).filter(
        has=page.locator("span", has_text=re.compile(rf"^\s*{re.escape(column)}\s*$"))).first
    btn = th.locator("p-columnfilter button").first
    if btn.count() == 0:
        return None
    # PrimeNG closes the overlay on any scroll, so nothing may scroll while it is open: the overlay focuses
    # its first checkbox (focus is patched not to scroll) and the button is clicked by script (a real click
    # first scrolls a button that is off screen, as the right-hand columns are in a short window).
    page.evaluate(NO_SCROLL_FOCUS)
    ov = page.locator(OVERLAY).last
    for _ in range(4):                        # after an Apply the button can need a second click
        _js_click(btn)
        try:
            ov.wait_for(state="visible", timeout=3000)
            page.wait_for_timeout(500)
            if ov.count():                    # still open once the page has settled
                return ov
        except Exception:
            pass
    raise RuntimeError(f"the {column} filter did not open")


def _option_states(ov):
    """{label: ticked} of an open filter overlay; Select All is under ALL."""
    return OrderedDict((label if label == ALL else _clean(label), ticked) for label, ticked in ov.evaluate(STATES_JS))


def _js_click(locator):
    """Click without scrolling: any scroll closes the column filter overlay (PrimeNG hides it)."""
    locator.wait_for(state="attached", timeout=5000)
    locator.evaluate("e => e.click()")


def _set_filter(page, column, wanted):
    """Tick exactly `wanted` (a set of option labels, or ALL) in the column filter and Apply.
    It sets a state rather than toggling, so a try that loses the overlay half way is just redone."""
    error = None
    for _ in range(3):
        try:
            ov = _open_filter(page, column)
            if ov is None:
                raise RuntimeError(f"no filter on {column}")
            for _ in range(2):
                states = _option_states(ov)
                target = {l: wanted == ALL or l in wanted for l in states if l != ALL}
                if wanted == ALL and not states.get(ALL):
                    _js_click(ov.locator(".custom-filter-select-all .p-checkbox-box").first)
                else:
                    boxes = ov.locator(".custom-filter-option:not(.custom-filter-select-all)")
                    for n, (label, ticked) in enumerate((l, t) for l, t in states.items() if l != ALL):
                        if ticked != target[label]:
                            _js_click(boxes.nth(n).locator(".p-checkbox-box"))
                page.wait_for_timeout(300)
                if all(_option_states(ov).get(l) == t for l, t in target.items()):
                    break
            else:
                raise RuntimeError(f"{column} filter options did not take the wanted state")
            _js_click(ov.locator("button", has_text="Apply").first)
            try:
                ov.wait_for(state="hidden", timeout=5000)
            except Exception:
                page.keyboard.press("Escape")
            _settle(page, 1500)
            return
        except Exception as e:
            error = e
            page.keyboard.press("Escape")
            _settle(page, 800)
    raise error


# ---- Navigation
def open_summary(page, Config):
    """Audit list -> branch -> the audit's row (read) -> Audit Summary; returns the row by list header."""
    page.click("a[href='/home/audit']")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)   # the list keeps polling at times
    except Exception:
        pass
    select_branch(page, Config.Branch)
    wait_spinner(page)
    page.wait_for_selector("button.audit-name-link", timeout=45000)
    page.wait_for_timeout(1500)
    row = audit_row(page, Config.ap_audit_name)
    if row.count() == 0:
        raise RuntimeError(f"audit {Config.ap_audit_name} is not in the audit list")
    headers = [_clean(h) for h in row.locator("xpath=ancestor::table[1]/thead//th").all_inner_texts()]
    info = OrderedDict(zip(headers, [_clean(c) for c in row.locator("td").all_inner_texts()]))
    click_audit(page, Config.ap_audit_name)
    select_navigation_option(page, "Audit Summary")
    _settle(page, 1500)
    _close_guide(page)
    return info


def _reset(page, Config, st):
    """Summarize As Item, Qty cards, no search, All badge, page 1; the page is reopened after
    sort / filter cases (st["dirty"])."""
    if st.pop("dirty", False) or page.locator(SUMMARY).count() == 0:
        open_summary(page, Config)
    _close_insights(page)
    _search(page, "")
    _summarize(page, "Item")
    _toggle(page, "Qty")
    click_badge(page, SummaryCfg(), "All")
    _first_page(page)


# ======================================================
# A — AUDIT DETAILS
# ======================================================
def tc_load(page, Config, st):
    st["list_row"] = open_summary(page, Config)
    _summarize(page, "Item")
    _toggle(page, "Qty")
    click_badge(page, SummaryCfg(), "All")
    errors = []

    def part(key, fn):
        try:
            st[key] = fn()
        except Exception as e:
            errors.append(f"{key}: {str(e).splitlines()[0][:80]}")

    part("tiles", lambda: read_tiles(page))
    part("qty", lambda: _metrics(page))
    part("badges", lambda: read_badges(page))
    part("rows", lambda: read_rows(page))
    part("charts", lambda: read_charts(page))
    part("value", lambda: _value_cards(page))
    part("options", lambda: _dropdown_options(page, page.locator(SUMMARIZE).first))
    if st.get("rows") and st.get("options"):
        part("views", lambda: read_views(page, st["options"]))
        if st.get("views") is not None:
            st["views"]["Item"] = st["rows"]
    if st.get("rows"):
        part("derived", lambda: derive_costs(page, st["rows"]))
        derived, source = st.get("derived") or ({}, {})
        # item master costs, when the caller knows them, are the expected values; derived ones fill gaps
        known = {c: v for c, v in st.get("known_costs", {}).items() if v is not None}
        st["costs"] = {**derived, **known}
        st["cost_source"] = {**source, **{c: "item master" for c in known}}
    part("insights", lambda: read_insights(page))
    part("closed", lambda: _close_insights(page) or True)
    if all(k in st for k in ("tiles", "badges", "qty")):
        st["start"] = (st["tiles"].get("Status"), dict(st["badges"]), dict(st["qty"]))

    rows = st.get("rows") or []
    views = {k: len(v) for k, v in (st.get("views") or {}).items()}
    charts = sorted(k for k, v in (st.get("charts") or {}).items() if v.get("data"))
    sources = dict(Counter((st.get("cost_source") or {}).values()))
    actual = (f"{len(rows)} row(s); badges={dict(st.get('badges') or {})}; qty cards={st.get('qty')} "
              f"value cards={st.get('value')}; views={views}; charts={charts}; "
              f"cost price for {len(st.get('costs') or {})}/{len({r.get('Item Code') for r in rows})} item(s) {sources}; "
              f"auditors={len((st.get('insights') or (None, []))[1])}")
    return not errors and bool(rows), actual + (f"; errors: {'; '.join(errors)}" if errors else "")


def tc_tiles(st):
    if "tiles" not in st:                     # read failed; an empty card that was read is a FAIL
        return _need(st, "tiles")
    t = st["tiles"]
    missing = [k for k in TILES if k not in t]
    empty = [k for k in TILES if k in t and not t[k]]
    return not missing and not empty, f"missing={missing} empty={empty}; " + "; ".join(f"{k}: {v}" for k, v in t.items())


def tc_name_group(st, Config):
    miss = _need(st, "tiles")
    if miss:
        return miss
    t = st["tiles"]
    ok = t.get("Audit Name") == Config.ap_audit_name and (t.get("Group") or "").lower() == Config.Group_Name.lower()
    return ok, (f"Audit Name={t.get('Audit Name')} (expected {Config.ap_audit_name}); "
                f"Group={t.get('Group')} (expected {Config.Group_Name})")


def tc_type_status(st):
    miss = _need(st, "tiles", "list_row")
    if miss:
        return miss
    t, row = st["tiles"], st["list_row"]
    kind = next((v for k, v in row.items() if "type" in k.lower() and "mapping" not in k.lower()), None)
    status = next((v for k, v in row.items() if "status" in k.lower()), None)
    ok = (kind or "").lower() == (t.get("Audit Type") or "").lower() and (status or "").lower() == (t.get("Status") or "").lower()
    return ok, (f"tiles: type={t.get('Audit Type')} status={t.get('Status')}; "
                f"audit list: type={kind} status={status} (row {dict(row)})")


def tc_auditors(st):
    miss = _need(st, "tiles", "insights")
    if miss:
        return miss
    tile = sorted({n.strip().lower() for n in (st["tiles"].get("Auditor(s)") or "").split(",") if n.strip()})
    shown = sorted({r.get("Auditor", "").lower() for r in st["insights"][1]})
    return tile == shown, f"tile={tile} Auditor Insights={shown}"


def tc_progress(st):
    miss = _need(st, "tiles", "badges")
    if miss:
        return miss
    text, b = st["tiles"].get("Progress") or "", st["badges"]
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    counted = f"{(b.get('All', 0) - b.get('Un Verified', 0)) / b['All'] * 100:.0f}%" if b.get("All") else "-"
    return bool(m) and 0 <= float(m.group(1)) <= 100, \
        f"tile={text!r}; info: lines counted (All − Un Verified) ÷ All = {counted}"


def _date(text):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(_clean(text), fmt)
        except ValueError:
            pass
    return None


def tc_date(st):
    miss = _need(st, "tiles")
    if miss:
        return miss
    text = st["tiles"].get("Date & Time") or ""
    d = _date(text)
    return d is not None, f"{text!r} -> {d:%Y-%m-%d %H:%M}" if d else f"{text!r} is not a date"


def tc_buttons(page, st):
    if page.locator(SUMMARY).count() == 0:
        return _not_run("the Audit Summary page is not open")
    shown = OrderedDict((b, page.locator(f"{SUMMARY} button.text-app-primary", has_text=b).first.is_visible())
                        for b in TOP_BUTTONS)
    return all(shown.values()), "; ".join(f"{b}: {'shown' if v else 'MISSING'}" for b, v in shown.items()) + " (not clicked)"


# ======================================================
# B — AUDITOR INSIGHTS
# ======================================================
def tc_insights_columns(st):
    miss = _need(st, "insights")
    if miss:
        return miss
    headers, rows, _ = st["insights"]
    return headers == INSIGHTS_HEADERS, f"columns={headers}; auditors={[r.get('Auditor') for r in rows]}"


def tc_insights_values(st, column, key):
    miss = _need(st, "insights", "views", *(("costs",) if "value" in key else ()))
    if miss:
        return miss
    if "Auditor" not in st["views"]:
        return _not_run("no Summarize As: Auditor view to compare with")
    sums, unknown = by_auditor(st["views"]["Auditor"], st.get("costs") or {})
    rows = st["insights"][1]
    lines, bad = [], []
    for r in rows:
        got, want = _num(r.get(column)), sums.get(r.get("Auditor", "").lower(), {}).get(key, 0.0)
        lines.append(f"{r.get('Auditor')}: {got:g} (expected {want:g})")
        if not _eq(got, want):
            bad.append(r.get("Auditor"))
    listed = {r.get("Auditor", "").lower() for r in rows}
    extra = sorted(n for n in sums if n not in listed)
    if "value" in key and unknown:
        return _not_run(f"cost price unknown for {sorted(unknown)}; " + "; ".join(lines))
    return not bad and not extra, "; ".join(lines) + (f"; counted by {extra} but not listed" if extra else "")


def tc_insights_status(st):
    miss = _need(st, "insights")
    if miss:
        return miss
    lines, bad = [], []
    for r in st["insights"][1]:
        pct, status, elapsed = _num(r.get("Progress")), (r.get("Status") or "").lower(), r.get("Elapsed Timing") or ""
        ok = (0 <= pct <= 100
              and (("yet to start" in status) if pct == 0 else ("progress" in status or "complete" in status))
              and re.fullmatch(r"\d{1,3}:\d{2}(:\d{2})?", elapsed) is not None)
        lines.append(f"{r.get('Auditor')}: {r.get('Progress')} / {r.get('Status')} / {elapsed}")
        if not ok:
            bad.append(r.get("Auditor"))
    return not bad, "; ".join(lines) + (f"; inconsistent: {bad}" if bad else "")


def tc_insights_total(st):
    miss = _need(st, "insights")
    if miss:
        return miss
    _, rows, total = st["insights"]
    lines = [(c, sum(_num(r.get(c)) for r in rows), _num(total.get(c))) for c in INSIGHTS_SUMS]
    return all(_eq(t, s) for _, s, t in lines), "; ".join(f"{c}: Total={t:g} rows={s:g}" for c, s, t in lines)


def tc_insights_cards(st):
    miss = _need(st, "insights", "qty", "value")
    if miss:
        return miss
    total = st["insights"][2]
    pairs = [("Completed Inventory", "Audited qty card", st["qty"].get("audited")),
             ("Audited Value", "Audited value card", st["value"].get("audited")),
             ("Damaged Value", "Damaged value card", st["value"].get("damaged"))]
    return all(_eq(_num(total.get(c)), card) for c, _, card in pairs), \
        "; ".join(f"{c}: Total={_num(total.get(c)):g} {name}={card}" for c, name, card in pairs)


def tc_insights_search(page, Config, st):
    miss = _need(st, "insights")
    if miss:
        return miss
    names = [r.get("Auditor", "") for r in st["insights"][1]]
    if not names:
        return _not_run("no auditor rows")
    term = min(names, key=lambda n: sum(n.lower() in x.lower() for x in names))
    want = sorted(x for x in names if term.lower() in x.lower())
    before = st["insights"][2]
    _reset(page, Config, st)
    try:
        _insights_search(page, term)
        _, rows, total = read_insights(page)
        shown = sorted(r.get("Auditor", "") for r in rows)
        same = all(_eq(_num(total.get(c)), _num(before.get(c))) for c in INSIGHTS_SUMS)
        if shown != want or not same:
            _evidence(page, st, "search")
    finally:
        _insights_search(page, "")
    return shown == want and same, (f"search {term!r}: shown={shown} expected={want}; Total "
                                    + ("unchanged" if same else f"changed to {total} (was {before})"))


def tc_insights_no_match(page, Config, st):
    miss = _need(st, "insights")
    if miss:
        return miss
    _reset(page, Config, st)
    try:
        _insights_search(page, NO_MATCH)
        rows = read_insights(page)[1]
        if rows:
            _evidence(page, st, "search")
    finally:
        _insights_search(page, "")
    back = read_insights(page)[1]
    return not rows and len(back) == len(st["insights"][1]), \
        f"search {NO_MATCH!r}: {len(rows)} auditor row(s); after clearing: {len(back)} of {len(st['insights'][1])}"


def tc_insights_close(page, Config, st):
    miss = _need(st, "insights")
    if miss:
        return miss
    _reset(page, Config, st)
    _open_insights(page)
    _close_insights(page)
    return not page.locator(INSIGHTS).first.is_visible(), "dialog closed"


# ======================================================
# C — CATEGORY WISE VARIANCE (bar)
# ======================================================
def tc_bar_categories(st):
    miss = _need(st, "rows")
    if miss:
        return miss
    bar = _bar(st)
    if not bar:
        return _not_run("bar chart data not readable")
    exp, _ = chart_expected(st["rows"], st.get("costs") or {})
    cats = sorted({_blank(r.get("Category")) for r in st["rows"]})
    missing = sorted(c for c, e in exp.items() if any(e.values()) and c not in bar[0])
    extra = [c for c in bar[0] if c not in cats]
    return not missing and not extra, f"chart={bar[0]}; report categories={cats}; missing={missing} extra={extra}"


def tc_bar_datasets(st):
    bar = _bar(st)
    if not bar:
        return _not_run("bar chart data not readable")
    raw = [ds.get("label") for ds in st["charts"]["bar"]["data"].get("datasets", [])]
    return list(bar[1]) == BAR_DATASETS, f"datasets={raw}"


def tc_bar_values(st, dataset):
    miss = _need(st, "rows")
    if miss:
        return miss
    bar = _bar(st)
    if not bar:
        return _not_run("bar chart data not readable")
    shown = bar[1].get(dataset)
    if shown is None:
        return False, f"no {dataset!r} dataset in {list(bar[1])}"
    exp, unknown = chart_expected(st["rows"], st.get("costs") or {})
    lines, bad = [], []
    for cat in sorted(set(exp) | set(shown)):
        got, want = shown.get(cat, 0.0), exp.get(cat, {}).get(dataset, 0.0)
        line = f"{cat}: chart={got:g} expected={want:g}"
        if not _eq(got, want):
            bad.append(cat)
            if dataset == "Excess Value":           # name the rows that explain the gap
                excess = {r["Item Code"]: _num(r.get("Variance Value")) for r in st["rows"]
                          if _blank(r.get("Category")) == cat and RULES["Excess Line Item"](r) and not _unverified(r)}
                if excess and _eq(got, want - sum(excess.values())):
                    line += (" = Positive Variance without the excess line item(s) "
                             + ", ".join(f"{c} {v:g}" for c, v in excess.items()))
        lines.append(line)
    if dataset == "Available Value" and unknown:
        return _not_run(f"cost price unknown for {sorted(unknown)}; " + "; ".join(lines))
    return not bad, "; ".join(lines)


def tc_bar_card(st, dataset, card):
    """Σ Available + Σ <dataset> over all categories = the <card> value card."""
    miss = _need(st, "rows", "value")
    if miss:
        return miss
    bar = _bar(st)
    if not bar:
        return _not_run("bar chart data not readable")
    avail, other = sum(bar[1].get("Available Value", {}).values()), sum(bar[1].get(dataset, {}).values())
    want, note = st["value"].get(card, 0.0), ""
    if card == "stock":
        unver = [r for r in st["rows"] if _unverified(r) and _qty(r, "Stock Quantity")]
        unknown = [r["Item Code"] for r in unver if r["Item Code"] not in (st.get("costs") or {})]
        if unknown:
            return _not_run(f"cost price unknown for Un Verified items {unknown}")
        left_out = sum(_qty(r, "Stock Quantity") * st["costs"][r["Item Code"]] for r in unver)
        if left_out:
            want, note = want - left_out, f" less Un Verified stock value {left_out:g}"
    return _eq(avail + other, want), (f"Available {avail:g} + {dataset} {other:g} = {avail + other:g}; "
                                      f"{card} value card {st['value'].get(card)}{note} -> expected {want:g}")


# ======================================================
# D — OVERALL VARIANCE (doughnut)
# ======================================================
def tc_pie_labels(st):
    bar, pie = _bar(st), _pie(st)
    if not bar or not pie:
        return _not_run("chart data not readable")
    return pie[0] == list(bar[1]) and pie[2] == bar[2], \
        f"doughnut labels={pie[0]} colours={pie[2]}; bar datasets={list(bar[1])} colours={bar[2]}"


def tc_pie_share(st):
    miss = _need(st, "rows")
    if miss:
        return miss
    pie = _pie(st)
    if not pie:
        return _not_run("doughnut data not readable")
    exp, unknown = chart_expected(st["rows"], st.get("costs") or {})
    if unknown:
        return _not_run(f"cost price unknown for {sorted(unknown)}")
    totals = [sum(e[ds] for e in exp.values()) for ds in BAR_DATASETS]
    want = [t / sum(totals) * 100 if sum(totals) else 0.0 for t in totals]
    got = dict(zip(pie[0], pie[1]))
    bad = [ds for ds, w in zip(BAR_DATASETS, want) if abs(got.get(ds, 0.0) - w) > 1]
    info, bar = "", _bar(st)
    if bar:
        bt = [sum(bar[1].get(ds, {}).values()) for ds in BAR_DATASETS]
        info = f"; info: shares of the bar totals {bt} would be {[round(t / sum(bt) * 100, 1) if sum(bt) else 0 for t in bt]}"
    return not bad, (f"doughnut={[got.get(ds) for ds in BAR_DATASETS]} expected={[round(w, 1) for w in want]} "
                     f"from totals {dict(zip(BAR_DATASETS, totals))}{info}")


def tc_pie_sum(st):
    pie = _pie(st)
    if not pie:
        return _not_run("doughnut data not readable")
    return abs(sum(pie[1]) - 100) <= 1, f"slices {pie[1]} add up to {sum(pie[1]):g}"


# ======================================================
# E — FILTER BADGES
# ======================================================
def tc_badges_shown(st):
    miss = _need(st, "badges")
    if miss:
        return miss
    missing = [b for b in RULES if b not in st["badges"]]
    return not missing, f"badges={dict(st['badges'])}; missing={missing}"


def tc_badge_rows(page, Config, st):
    """Click every badge and read its rows (kept for the rule check)."""
    miss = _need(st, "badges")
    if miss:
        return miss
    _reset(page, Config, st)
    badge_rows, lines, bad = OrderedDict(), [], []
    try:
        for badge in st["badges"]:
            count = click_badge(page, SummaryCfg(), badge)
            _settle(page, 800)
            rows = read_rows(page)
            badge_rows[badge] = rows
            lines.append(f"{badge}: badge={count} rows={len(rows)}")
            if count != len(rows):
                bad.append(badge)
                _evidence(page, st, "badge")
    finally:
        click_badge(page, SummaryCfg(), "All")
    st["badge_rows"] = badge_rows             # only once every badge was read (TC-43 / 115 use it)
    return not bad, "; ".join(lines)


def tc_badge_rules(st):
    miss = _need(st, "badge_rows")
    if miss:
        return miss
    lines, bad = [], []
    for badge, rows in st["badge_rows"].items():
        rule = RULES.get(badge)
        broken = [r.get("Item Code") for r in rows if rule and not rule(r)]
        if broken:
            lines.append(f"{badge}: {broken}" + (" (info: rule not confirmed)" if badge in UNSURE_RULES else ""))
            if badge not in UNSURE_RULES:
                bad.append(badge)
    return not bad, "; ".join(lines) or f"every row meets its badge rule ({len(st['badge_rows'])} badges)"


def tc_badge_counts(st):
    miss = _need(st, "badges", "rows")
    if miss:
        return miss
    lines, bad = [], []
    for badge, count in st["badges"].items():
        if badge not in RULES:
            continue
        want = sum(1 for r in st["rows"] if RULES[badge](r))
        lines.append(f"{badge}: {count} (expected {want}{', info' if badge in UNSURE_RULES and want != count else ''})")
        if want != count and badge not in UNSURE_RULES:
            bad.append(badge)
    return not bad, "; ".join(lines)


def tc_badge_sums(st):
    miss = _need(st, "badges")
    if miss:
        return miss
    b = st["badges"]
    g = lambda k: b.get(k, 0)
    checks = [
        ("All = Matched + Positive + Negative + Un Verified",
         g("All") == g("Matched Line Item") + g("Positive Variance") + g("Negative Variance") + g("Un Verified")),
        ("Excess Line Item ≤ Positive Variance", g("Excess Line Item") <= g("Positive Variance")),
        ("Not Found ≤ Negative Variance", g("Not Found") <= g("Negative Variance")),
        ("Location Conflict / Damaged Report / Cross Checked ≤ All",
         all(g(k) <= g("All") for k in ("Location Conflict", "Damaged Report", "Cross Checked Audit"))),
    ]
    return all(ok for _, ok in checks), "; ".join(f"{name}: {'ok' if ok else 'NO'}" for name, ok in checks)


# ======================================================
# F — SUMMARIZE AS
# ======================================================
def tc_summarize_options(st, expected, kind):
    if "options" not in st:                   # read failed; an empty list that was read is a FAIL
        return _need(st, "options")
    return sorted(st["options"]) == sorted(expected), f"shown={st['options']} expected for {kind}={expected}"


def tc_views_variance(st):
    miss = _need(st, "views")
    if miss:
        return miss
    bad, n = [], 0
    for view, rows in st["views"].items():
        for r in rows:
            if _unverified(r):
                continue
            n += 1
            var = _num(r.get("Variance"))
            if var != _qty(r, "Audited Quantity") - _qty(r, "Stock Quantity") or not _sign_ok(var, r.get("Variance Type", "")):
                bad.append(f"{view}/{r.get('Item Code')}: {r.get('Audited Quantity')} − {r.get('Stock Quantity')} "
                           f"-> {r.get('Variance')} {r.get('Variance Type')}")
    return not bad, "; ".join(bad)[:400] or f"{n} row(s) in {sorted(st['views'])} match"


def tc_views_value(st):
    miss = _need(st, "views", "costs")
    if miss:
        return miss
    costs, bad, unknown, n = st["costs"], [], set(), 0
    for view, rows in st["views"].items():
        for r in rows:
            code = r.get("Item Code")
            if _unverified(r):
                continue
            if code not in costs:
                if _num(r.get("Variance")):
                    unknown.add(code)
                continue
            n += 1
            if not _eq(_num(r.get("Variance Value")), _num(r.get("Variance")) * costs[code]):
                bad.append(f"{view}/{code}: {r.get('Variance Value')} vs {r.get('Variance')} × {costs[code]:g}")
    own = sorted(c for c, s in (st.get("cost_source") or {}).items() if s == "row")
    return not bad, ("; ".join(bad)[:400] or f"{n} row(s) match") \
        + (f"; cost price from the row itself for {own}" if own else "") \
        + (f"; cost price unknown for {sorted(unknown)}" if unknown else "")


def tc_views_totals(st):
    miss = _need(st, "views", "qty")
    if miss:
        return miss
    lines, bad = [], []
    for view, rows in st["views"].items():
        sums = {m: sum(_qty(r, c) for r in rows) for m, c in CARD_COLUMNS}
        off = [m for m in sums if not _eq(sums[m], st["qty"].get(m))]
        lines.append(f"{view}: " + "/".join(f"{sums[m]:g}" for m, _ in CARD_COLUMNS) + (f" (off: {off})" if off else ""))
        if off:
            bad.append(view)
    return not bad, "; ".join(lines) + f"; cards stock/audited/damaged={st['qty']}"


def tc_item_view_unique(st):
    miss = _need(st, "rows")
    if miss:
        return miss
    codes = Counter(r.get("Item Code") for r in st["rows"])
    repeated = sorted(c for c, n in codes.items() if n > 1)
    return not repeated, f"{len(codes)} item(s); repeated={repeated}"


def tc_views_add_up(st):
    miss = _need(st, "views")
    if miss:
        return miss
    item = {r.get("Item Code"): r for r in st["rows"]}
    bad, checked = [], []
    for view, rows in st["views"].items():
        if view == "Item":
            continue
        cols = ["Audited Quantity"] + (["Stock Quantity"] if view != "Auditor" else [])
        checked.append(f"{view} ({', '.join(cols)})")
        sums = defaultdict(lambda: defaultdict(float))
        for r in rows:
            for c in cols:
                sums[r.get("Item Code")][c] += _qty(r, c)
        for code, r in item.items():
            for c in cols:
                got = sums[code][c] if code in sums else 0.0
                if not _eq(got, _qty(r, c)):
                    bad.append(f"{view}/{code} {c}: {got:g} vs {r.get(c)}")
    return not bad, ("; ".join(bad)[:400] or "every view adds up per item") + f"; checked {checked}"


# ======================================================
# G — QTY / VALUE CARDS
# ======================================================
def tc_value_cards(st):
    miss = _need(st, "rows", "value", "costs")
    if miss:
        return miss
    costs = st["costs"]
    unknown = sorted({r["Item Code"] for r in st["rows"]
                      if r["Item Code"] not in costs and any(_qty(r, c) for _, c in CARD_COLUMNS)})
    if unknown:
        return _not_run(f"cost price unknown for {unknown}")
    want = {m: sum(_qty(r, c) * costs.get(r["Item Code"], 0) for r in st["rows"]) for m, c in CARD_COLUMNS}
    bad = [m for m in want if not _eq(st["value"].get(m), want[m])]
    return not bad, f"value cards={st['value']} expected={ {m: round(v, 2) for m, v in want.items()} }"


def tc_qty_back(page, Config, st):
    miss = _need(st, "qty")
    if miss:
        return miss
    _reset(page, Config, st)
    _toggle(page, "Value")
    _toggle(page, "Qty")
    back = _metrics(page)
    active = _clean(page.locator(f"{TOGGLE}.active").first.inner_text())
    return back == st["qty"] and active == "Qty", f"after Value -> Qty: {back} (was {st['qty']}); active={active}"


def tc_cost_master(st):
    """The cost price the page works with (item searched with the Value cards on, or Variance Value /
    Variance) = the item master cost the run was set up with."""
    known = {c: v for c, v in st.get("known_costs", {}).items() if v is not None}
    if not known:
        return _not_run("no item master cost prices given (run on an existing audit)")
    if not st.get("derived"):
        return _need(st, "derived")
    derived, source = st["derived"]
    lines, bad = [], []
    for code, cost in sorted(known.items()):
        if code not in derived:
            continue                          # not on the summary, or no quantity to derive it from
        lines.append(f"{code}: page {derived[code]:g} ({source.get(code)}) master {cost:g}")
        if not _eq(derived[code], cost):
            bad.append(code)
    if not lines:
        return _not_run(f"no item with a cost price read on the page among {sorted(known)}")
    return not bad, "; ".join(lines)


# ======================================================
# H — SEARCH
# ======================================================
def _matches(rows, term):
    t = term.lower()
    return [r for r in rows if t in r.get("Item Code", "").lower() or t in r.get("Item Name", "").lower()]


def _search_terms(rows):
    """{"code", "name", "partial"}: an item code and an item name that a search singles out, and part of
    a code ("" when the rows have none)."""
    codes = [r.get("Item Code", "") for r in rows if r.get("Item Code")]
    names = [r.get("Item Name", "") for r in rows if r.get("Item Name")]
    unique = lambda t: sum(t.lower() in x.lower() for x in codes + names) == 1
    code = next((c for c in codes if unique(c)), codes[0] if codes else "")
    name = next((n for n in names if unique(n)), names[0] if names else "")
    return {"code": code, "name": name, "partial": code[1:-1] if len(code) > 2 else code, "no match": NO_MATCH}


def tc_search(page, Config, st, which):
    miss = _need(st, "rows")
    if miss:
        return miss
    term = _search_terms(st["rows"])[which]
    if not term:
        return _not_run(f"no item {which} to search for")
    want = _matches(st["rows"], term)
    want_codes = sorted(r["Item Code"] for r in want)
    _reset(page, Config, st)
    try:
        _search(page, term)
        shown, badges, cards = read_rows(page), read_badges(page), _metrics(page)
        shown_codes = sorted(r.get("Item Code") for r in shown)
        off_badges = {b: f"{badges.get(b)}≠{n}" for b, n in
                      ((b, sum(1 for r in want if rule(r))) for b, rule in RULES.items() if b not in UNSURE_RULES)
                      if badges.get(b) != n}
        off_cards = {m: f"{cards.get(m)}≠{v:g}" for m, v in
                     ((m, sum(_qty(r, c) for r in want)) for m, c in CARD_COLUMNS) if not _eq(cards.get(m), v)}
        ok = shown_codes == want_codes and not off_badges and not off_cards
        if not ok:
            _evidence(page, st, "search")
    finally:
        _search(page, "")
    return ok, (f"{which} {term!r}: rows={shown_codes} expected={want_codes}; "
                f"badges {off_badges or 'ok'}; cards {off_cards or 'ok'}")


def tc_search_clear(page, Config, st):
    miss = _need(st, "rows", "badges", "qty")
    if miss:
        return miss
    _reset(page, Config, st)
    _search(page, st["rows"][0]["Item Code"])
    _search(page, "")
    rows, badges, cards = read_rows(page), dict(read_badges(page)), _metrics(page)
    ok = len(rows) == len(st["rows"]) and badges == dict(st["badges"]) and cards == st["qty"]
    return ok, (f"after clearing: rows={len(rows)}/{len(st['rows'])}; "
                f"badges {'same' if badges == dict(st['badges']) else badges}; cards {'same' if cards == st['qty'] else cards}")


# ======================================================
# I — COLUMN FILTERS
# ======================================================
def tc_column_filter(page, Config, st, column):
    miss = _need(st, "rows")
    if miss:
        return miss
    _reset(page, Config, st)
    rows, total = st["rows"], len(st["rows"])
    split = Counter(v for r in rows for v in _cell_values(r, column))
    whole = {_blank(r.get(column)) for r in rows}
    ov = _open_filter(page, column)
    if ov is None:
        return False, f"no filter on {column}"
    labels = [l for l in _option_states(ov) if l != ALL]
    page.keyboard.press("Escape")
    _settle(page, 500)
    if not labels:
        st["dirty"] = True
        if set(split) <= {"-"}:
            return _not_run("every value in this column is blank: the filter has nothing to offer")
        return False, f"the filter offers no options; column values {sorted(split)}"
    options = {_blank(l) for l in labels}
    # options are either the single values ("Unassigned", "w1") or whole cells ("Unassigned, w1")
    by_cell = options == whole and options != set(split)
    match = (lambda r, o: _blank(r.get(column)) == o) if by_cell else (lambda r, o: o in _cell_values(r, column))
    lines, bad, follows = [], [], None
    try:
        for n, label in enumerate(labels[:MAX_FILTER_OPTIONS]):
            if n:                                 # one tick per Apply: switching straight from one option to
                _set_filter(page, column, set())  # the next (untick + tick) now and then applied nothing
            _set_filter(page, column, {label})
            opt, shown = _blank(label), read_rows(page)
            if follows is None:
                follows = read_badges(page).get("All") == len(shown)
            want = sum(1 for r in rows if match(r, opt))
            wrong = [r.get("Item Code") for r in shown if not match(r, opt)]
            lines.append(f"{label or '(blank)'}: {len(shown)}/{want}" + (f" wrong={wrong}" if wrong else ""))
            if len(shown) != want or wrong:
                bad.append(label)
                _evidence(page, st, "option")
        _set_filter(page, column, set())          # nothing ticked -> no filter
        cleared = len(read_rows(page))
        _set_filter(page, column, ALL)
        selected_all = len(read_rows(page))
        if selected_all != total:
            _evidence(page, st, "select_all")
        _set_filter(page, column, set())
        if len(read_rows(page)) != total:
            st["dirty"] = True
    except Exception:
        st["dirty"] = True
        raise
    # a blank value need not be offered as an option; what Select All then shows is checked below
    options_ok = options in (set(split), whole, set(split) - {"-"}, whole - {"-"})
    blanks = sum(1 for r in rows if _blank(r.get(column)) == "-")
    hidden = (f" (hides {total - selected_all} row(s); {blanks} row(s) have no {column} and no option)"
              if selected_all != total else "")
    ok = options_ok and not bad and cleared == total and selected_all == total
    return ok, (f"options={labels} (column values {sorted(split)}); " + "; ".join(lines)
                + f"; unticked={cleared}/{total}; Select All={selected_all}/{total}{hidden}"
                + f"; info: badges follow the filter={follows}")


# ======================================================
# J — SORT
# ======================================================
def _sort_key(kind, value):
    v = _clean(value)
    if v in ("", "-"):
        return None
    if kind == "numeric":
        return _num(v) if re.match(r"^[-+]?\d", v.replace(",", "")) else None
    return _date(v) if kind == "date" else v.lower()


def _natural(text):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", text)]


def _ordered(keys, desc, kind):
    """Keys in ascending / descending order; text may also be in natural order ("Item 2" < "Item 10")."""
    for ks in [keys] + ([[_natural(k) for k in keys]] if kind == "text" else []):
        try:
            if all((a >= b) if desc else (a <= b) for a, b in zip(ks, ks[1:])):
                return True
        except TypeError:
            pass
    return False


def _sort(page, column):
    """Click the column header twice: (rows, aria-sort) after each click."""
    th = page.locator(f"{HEADERS}[psortablecolumn]").filter(
        has_text=re.compile(rf"^\s*{re.escape(column)}\s*$")).first
    label = th.locator(".th-filter-wrap > span").first      # the filter button sits in the same header
    out = []
    for _ in range(2):
        (label if label.count() else th).click()
        _settle(page, 1200)
        _wait_table(page)                  # a sort reloads the table: don't read it mid-refresh
        out.append((_page_rows(page), th.get_attribute("aria-sort")))
    return out


def tc_sort(page, Config, st, kind):
    miss = _need(st, "rows")
    if miss:
        return miss
    _reset(page, Config, st)
    columns = [_clean(t) for t in page.locator(f"{HEADERS}[psortablecolumn]").all_inner_texts()]
    groups = {"numeric": [c for c in columns if c in NUMERIC], "date": [c for c in columns if c in DATES],
              "composite": [c for c in columns if c in COMPOSITE]}
    groups["text"] = [c for c in columns if not any(c in g for g in groups.values())]
    if not groups[kind]:
        return _not_run(f"no sortable {kind} column among {columns}")
    st["dirty"] = True                     # the table stays sorted: reopen the page afterwards
    lines, bad = [], []
    for column in groups[kind]:
        (asc, aria_a), (desc, aria_d) = _sort(page, column)
        if kind == "composite":
            same = sorted(r.get("Item Code") for r in asc) == sorted(r.get("Item Code") for r in desc)
            lines.append(f"{column}: {'same rows' if same else 'ROWS CHANGED'} (aria {aria_a}/{aria_d}, info)")
            if not same:
                bad.append(column)
            continue
        keys = [[k for k in (_sort_key(kind, r.get(column, "")) for r in rows) if k is not None] for rows in (asc, desc)]
        ok_a, ok_d = _ordered(keys[0], False, kind), _ordered(keys[1], True, kind)
        ok_aria = aria_a == "ascending" and aria_d == "descending"
        lines.append(f"{column}: asc {'ok' if ok_a else 'WRONG'} desc {'ok' if ok_d else 'WRONG'} aria {aria_a}/{aria_d}")
        if not (ok_a and ok_d and ok_aria):
            bad.append(column)
            _evidence(page, st, "sort")
    return not bad, "; ".join(lines)


# ======================================================
# K — PAGING
# ======================================================
def _set_page_size(page, size):
    dd = page.locator(PAGE_SIZE).first
    if _clean(dd.inner_text()) != size:
        dd.click()
        page.locator(PANEL_LI, has_text=re.compile(rf"^\s*{size}\s*$")).first.click()
        _settle(page, 1500)


def tc_page_sizes(page, Config, st):
    miss = _need(st, "rows")
    if miss:
        return miss
    _reset(page, Config, st)
    dd = page.locator(PAGE_SIZE).first
    try:
        dd.wait_for(state="visible", timeout=15000)   # renders after the rows, e.g. when the page was reopened
    except Exception:
        return False, "no rows-per-page control"
    current = _clean(dd.inner_text())
    st["page_sizes"] = _dropdown_options(page, dd)
    return st["page_sizes"] == PAGE_SIZES, f"options={st['page_sizes']} (current {current})"


def tc_paging(page, Config, st):
    miss = _need(st, "rows", "page_sizes")
    if miss:
        return miss
    _reset(page, Config, st)
    total, lines, bad, walks = len(st["rows"]), [], [], OrderedDict()
    try:
        for size in st["page_sizes"]:
            _set_page_size(page, size)
            pages = walk_pages(page)
            walks[size] = pages
            first, count = min(total, int(size)), max(1, math.ceil(total / int(size)))
            ok = len(pages[0]) == first and len(pages) == count and all(len(p) <= int(size) for p in pages)
            lines.append(f"{size}/page: page 1 has {len(pages[0])} (expected {first}), {len(pages)} page(s) (expected {count})")
            if not ok:
                bad.append(size)
                _evidence(page, st, "paging")
    finally:
        _set_page_size(page, PAGE_SIZES[0])
    st["walks"] = walks                       # only once every size was walked (TC-103 uses it)
    return not bad, "; ".join(lines)


def tc_paging_rows(st):
    miss = _need(st, "walks", "rows")
    if miss:
        return miss
    want = Counter(r.get("Item Code") for r in st["rows"])
    lines, bad = [], []
    for size, pages in st["walks"].items():
        seen = Counter(r.get("Item Code") for p in pages for r in p)
        repeated = sorted(c for c, n in seen.items() if n > want.get(c, 0))
        missing = sorted(c for c in want if seen.get(c, 0) < want[c])
        lines.append(f"{size}/page: {sum(seen.values())} row(s)" + (f" repeated={repeated}" if repeated else "")
                     + (f" missing={missing}" if missing else ""))
        if repeated or missing:
            bad.append(size)
    return not bad, "; ".join(lines)


# ======================================================
# L — EXPORT
# ======================================================
def _hn(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _export_col(df, name):
    wanted = [_hn(n) for n in [name] + EXPORT_ALIASES.get(name, [])]
    return next((c for w in wanted for c in df.columns if _hn(c) == w), None)


def _read_export(path):
    """{sheet: data rows under its Item Code header row} of the exported file."""
    raws = ({"All": pd.read_csv(path, header=None, dtype=str)} if path.lower().endswith(".csv")
            else pd.read_excel(path, header=None, dtype=str, sheet_name=None))
    sheets = OrderedDict()
    for name, raw in raws.items():
        raw = raw.fillna("")
        for i in range(min(15, len(raw))):
            cells = [_clean(c) for c in raw.iloc[i]]
            if "itemcode" in [_hn(c) for c in cells]:
                df = raw.iloc[i + 1:].copy()
                df.columns = [c if c and c not in cells[:j] else f"{c}#{j}" for j, c in enumerate(cells)]
                keep = df[_export_col(df, "Item Code")].map(_clean)
                sheets[name] = df[(keep != "") & (keep.str.lower() != "total")]
                break
    return sheets


def tc_export(page, Config, st, folder):
    miss = _need(st, "rows")
    if miss:
        return miss
    _reset(page, Config, st)
    try:
        with page.expect_download(timeout=60000) as info:
            page.locator(EXPORT).first.click()
    except Exception as e:
        messages = [_clean(t)[:120] for t in page.locator(".swal2-popup:visible, .p-toast-message").all_inner_texts()]
        return False, f"no file downloaded ({str(e).splitlines()[0][:80]}); messages={messages}"
    path = os.path.join(folder, info.value.suggested_filename or "audit_summary_export.xlsx")
    info.value.save_as(path)
    sheets = st["export_sheets"] = _read_export(path)
    st["export"] = sheets.get("All", next(iter(sheets.values()), None))
    found = ", ".join(f"{n} ({len(d)})" for n, d in sheets.items()) or "no sheet with an Item Code header row"
    return os.path.getsize(path) > 0 and st["export"] is not None, \
        f"{os.path.basename(path)}, {os.path.getsize(path)} bytes; sheets: {found}"


def tc_export_rows(st):
    if st.get("export") is None:
        return _not_run("no exported file")
    return len(st["export"]) == len(st["rows"]), f"export={len(st['export'])} row(s), report={len(st['rows'])}"


def tc_export_columns(st):
    df = st.get("export")
    if df is None or not st.get("rows"):
        return _not_run("no exported file")
    missing = [c for c in EXPORT_CORE if _export_col(df, c) is None]
    others = [c for c in st["rows"][0] if c not in ("S.No", "Audited Image") and c not in EXPORT_CORE
              and _export_col(df, c) is None]
    return not missing, (f"export columns={[c for c in df.columns if c and '#' not in c]}; missing={missing}; "
                         f"info: other report columns not exported={others}")


def tc_export_values(st):
    df = st.get("export")
    if df is None:
        return _not_run("no exported file")
    code_col, cost_col = _export_col(df, "Item Code"), _export_col(df, "Cost Price")
    cols = {c: _export_col(df, c) for c in EXPORT_NUMBERS}
    report, costs = {r["Item Code"]: r for r in st["rows"]}, st.get("costs") or {}
    bad, n = [], 0
    for _, x in df.iterrows():
        code = _clean(x[code_col])
        r = report.get(code)
        if r is None:
            bad.append(f"{code}: not in the report")
            continue
        n += 1
        for c, col in cols.items():
            if col is None:
                continue
            a, b = _clean(x[col]), r.get(c, "")
            if not ((a == b) if "-" in (a, b) else _eq(_num(a), _num(b))):
                bad.append(f"{code} {c}: export={a} report={b}")
        if cost_col and code in costs and not _eq(_num(x[cost_col]), costs[code]):
            bad.append(f"{code} cost price: export={_clean(x[cost_col])} page={costs[code]:g}")
    compared = [c for c, col in cols.items() if col] + (["Cost Price"] if cost_col else [])
    return not bad, ("; ".join(bad)[:400] or f"{n} row(s) match") + f"; compared {compared}"


def tc_export_badge_sheets(st):
    sheets = st.get("export_sheets")
    if not sheets:
        return _not_run("no exported file")
    if not st.get("badge_rows"):
        return _not_run("no badge rows from TC-SUM-42 to compare with")
    lines, bad = [], []
    for badge, rows in st["badge_rows"].items():
        df = sheets.get(EXPORT_SHEETS.get(badge, badge))
        if df is None:
            continue                                    # a missing sheet is TC-SUM-116
        got = sorted(_clean(c) for c in df[_export_col(df, "Item Code")])
        want = sorted(r.get("Item Code") for r in rows)
        lines.append(f"{badge}: {len(got)} row(s)" + ("" if got == want else f" (sheet {got} ≠ page {want})"))
        if got != want:
            bad.append(badge)
    if not lines:
        return _not_run(f"no export sheet is named after a badge (sheets {list(sheets)})")
    return not bad, "; ".join(lines)


def tc_export_sheet_names(st):
    sheets = st.get("export_sheets")
    if not sheets:
        return _not_run("no exported file")
    wanted = {b: EXPORT_SHEETS.get(b, b) for b in (st.get("badges") or RULES)}
    missing = [b for b, s in wanted.items() if s not in sheets]
    other = [s for s in sheets if s not in wanted.values()]
    return not missing, f"sheets={list(sheets)}; no sheet for badge(s) {missing}; other sheets {other}"


# ======================================================
# M — COMBINED FILTERS
# ======================================================
def _pick_badge(st):
    """A badge with rows on the page whose rule some report rows meet."""
    return next((b for b in ("Positive Variance", "Location Conflict", "Damaged Report", "Negative Variance",
                             "Matched Line Item")
                 if (st.get("badges") or {}).get(b) and any(RULES[b](r) for r in st["rows"])), None)


def tc_badge_and_search(page, Config, st):
    miss = _need(st, "rows", "badges")
    if miss:
        return miss
    badge = _pick_badge(st)
    if not badge:
        return _not_run("no badge with rows")
    code = next(r["Item Code"] for r in st["rows"] if RULES[badge](r))
    term = code[1:-1] or code
    want = sorted(r["Item Code"] for r in _matches(st["rows"], term) if RULES[badge](r))
    _reset(page, Config, st)
    click_badge(page, SummaryCfg(), badge)
    try:
        _search(page, term)
        shown = sorted(r.get("Item Code") for r in read_rows(page))
        if shown != want:
            _evidence(page, st, "rows")
    finally:
        _search(page, "")
    return shown == want, f"{badge} + search {term!r}: rows={shown} expected={want}"


def tc_badge_and_filter(page, Config, st):
    miss = _need(st, "rows", "badges")
    if miss:
        return miss
    badge, column = _pick_badge(st), "Category"
    if not badge:
        return _not_run("no badge with rows")
    opt = Counter(v for r in st["rows"] if RULES[badge](r) for v in _cell_values(r, column)).most_common(1)[0][0]
    want = sorted(r["Item Code"] for r in st["rows"] if RULES[badge](r) and opt in _cell_values(r, column))
    _reset(page, Config, st)
    click_badge(page, SummaryCfg(), badge)
    try:
        ov = _open_filter(page, column)
        if ov is None:
            return False, f"no {column} filter"
        label = next((l for l in _option_states(ov) if l != ALL and _blank(l) == opt), None)
        page.keyboard.press("Escape")
        _settle(page, 500)
        if label is None:
            st["dirty"] = True
            return False, f"{column} filter does not offer {opt!r}"
        _set_filter(page, column, {label})
        shown = sorted(r.get("Item Code") for r in read_rows(page))
        if shown != want:
            _evidence(page, st, "rows")
        _set_filter(page, column, set())
    except Exception:
        st["dirty"] = True
        raise
    return shown == want, f"{badge} + {column} {opt!r}: rows={shown} expected={want}"


# ======================================================
# N — NO SIDE EFFECTS
# ======================================================
def tc_unchanged(page, Config, st):
    miss = _need(st, "tiles", "badges", "qty", "start")
    if miss:
        return miss
    st["dirty"] = True
    _reset(page, Config, st)
    now = ((read_tiles(page)).get("Status"), dict(read_badges(page)), _metrics(page))
    return now == st["start"], f"status / badges / cards now={now}; at the start={st['start']}"


# ======================================================
# ENTRY POINT
# ======================================================
MINOR_CASES = {"TC-SUM-116"}     # completeness of the export, not wrong numbers


def _severity(case):
    # an error, a page that does not load, or data changed by a read-only run
    if case["Actual Result"].startswith("error:") or case["Group"][0] == "N" or case["Test Case ID"] == "TC-SUM-01":
        return "Critical", "High"
    minor = case["Group"][0] in "AJK" or case["Test Case ID"] in MINOR_CASES
    return ("Minor", "Low") if minor else ("Major", "Medium")


def run_summary_page_tests(page, Config, folder=None, known_costs=None) -> bool:
    """folder: where the report goes (default a new Summary_<time> folder); known_costs: {item code:
    item master cost price} when the caller set the audit up, used as the expected cost prices."""
    audit = Config.ap_audit_name
    folder = folder or os.path.join(Config.e2e_output_dir, f"Summary_{datetime.now():%m%d_%H%M}")
    os.makedirs(folder, exist_ok=True)
    kind = getattr(Config, "summary_inventory_type", "Unit")
    options = SUMMARIZE_AS.get(kind, SUMMARIZE_AS["Unit"])
    run, st = SettingsRun(page, folder), {"folder": folder, "known_costs": dict(known_costs or {})}

    def case(tc_id, *args):
        st["case"], st["shot"] = tc_id, None
        run.case(tc_id, *args)
        last = run.cases[-1]
        if st["shot"] and last["Status"] == "FAIL":      # the state where it failed, then the end state
            last["Attachment"] = "\n".join(p for p in (st["shot"], last["Attachment"]) if p)
    opened = [f"Open audit {audit} > Audit Summary."]
    view_steps = opened + ["Select each Summarize As option and read every table page."]
    value_steps = opened + ["Read every table page.", "Click Value and read the cards; search each item for its cost price."]
    try:
        # ---------------- A
        case("TC-SUM-01", "A Audit Details", "Audit Summary opens and its data loads",
             ["Open Audits, select the branch and note the audit's row."] + opened
             + ["Read the tiles, cards, badges, every table page, both charts, each Summarize As view and Auditor Insights."],
             "The page opens and every part can be read.", tc_load, page, Config, st)
        case("TC-SUM-02", "A Audit Details", "Audit Details shows all 8 tiles with values", opened + ["Read the Audit Details tiles."],
             f"{', '.join(TILES)} all have a value.", tc_tiles, st)
        case("TC-SUM-03", "A Audit Details", "Audit Name and Group tiles match the audit", opened,
             f"Audit Name = {audit}; Group = {Config.Group_Name}.", tc_name_group, st, Config)
        case("TC-SUM-04", "A Audit Details", "Audit Type and Status tiles match the audit list",
             ["Note the audit's Type and Status in the audit list."] + opened + ["Read the Audit Type and Status tiles."],
             "Same values as the audit list row.", tc_type_status, st)
        case("TC-SUM-05", "A Audit Details", "Auditor(s) tile lists the auditors in Auditor Insights",
             opened + ["Read the Auditor(s) tile.", "Click Auditor Insights and read the auditor names."],
             "Same auditors in both.", tc_auditors, st)
        case("TC-SUM-06", "A Audit Details", "Progress tile is a percentage from 0 to 100", opened,
             "Progress shows N% with 0 ≤ N ≤ 100.", tc_progress, st)
        case("TC-SUM-07", "A Audit Details", "Date & Time tile is a valid date and time", opened,
             "Date & Time parses as a date.", tc_date, st)
        case("TC-SUM-08", "A Audit Details", "Stock Audit, Auditor Insights, Archive and Complete Audit buttons are shown",
             opened, "All four buttons are visible (they are not clicked).", tc_buttons, page, st)

        # ---------------- B
        insights = opened + ["Click Auditor Insights."]
        auditor_view = opened + ["Summarize As: Auditor; add up each auditor's rows.", "Click Auditor Insights."]
        case("TC-SUM-11", "B Auditor Insights", "Auditor Insights opens with all columns", insights,
             f"Columns: {', '.join(INSIGHTS_HEADERS)}.", tc_insights_columns, st)
        case("TC-SUM-12", "B Auditor Insights", "Completed Inventory = audited qty each auditor counted", auditor_view,
             "Completed Inventory = Σ Audited Quantity of the auditor's rows.", tc_insights_values, st,
             "Completed Inventory", "audited")
        case("TC-SUM-13", "B Auditor Insights", "Audited Value = audited qty × cost price per auditor", auditor_view,
             "Audited Value = Σ Audited Quantity × cost price of the auditor's rows.", tc_insights_values, st,
             "Audited Value", "audited_value")
        case("TC-SUM-14", "B Auditor Insights", "Damaged Value = damaged qty × cost price per auditor", auditor_view,
             "Damaged Value = Σ Damaged Qty × cost price of the auditor's rows.", tc_insights_values, st,
             "Damaged Value", "damaged_value")
        case("TC-SUM-15", "B Auditor Insights", "Progress, Status and Elapsed Timing are consistent", insights,
             "Progress 0–100; 0% → Yet to Start, otherwise In Progress / Completed; Elapsed Timing is hh:mm.",
             tc_insights_status, st)
        case("TC-SUM-16", "B Auditor Insights", "Total row = sum of the auditor rows", insights,
             "Total Completed Inventory / Audited Value / Damaged Value = sum of the rows.", tc_insights_total, st)
        case("TC-SUM-17", "B Auditor Insights", "Total row = the summary cards", insights + ["Compare with the Qty and Value cards."],
             "Completed Inventory = Audited qty card; Audited / Damaged Value = Audited / Damaged value cards.",
             tc_insights_cards, st)
        case("TC-SUM-18", "B Auditor Insights", "Search lists only matching auditors and keeps the overall Total",
             insights + ["Search an auditor name."],
             "Only auditors whose name contains the text are listed; the Total row stays the overall total.",
             tc_insights_search, page, Config, st)
        case("TC-SUM-19", "B Auditor Insights", "Search with no match lists no auditor; clearing lists all again",
             insights + [f"Search {NO_MATCH!r}.", "Clear the search."], "No auditor rows, then every auditor again.",
             tc_insights_no_match, page, Config, st)
        case("TC-SUM-20", "B Auditor Insights", "Close button closes Auditor Insights", insights + ["Click the close button."],
             "The dialog closes.", tc_insights_close, page, Config, st)

        # ---------------- C
        chart = value_steps + ["Read the Category Wise Variance chart data."]
        case("TC-SUM-21", "C Category Wise Variance", "Bar chart lists every category in the report", chart,
             "One bar per category with stock or variance; no unknown category.", tc_bar_categories, st)
        case("TC-SUM-22", "C Category Wise Variance", "Bars are Available Value, Stock Loss and Excess Value", chart,
             f"Datasets: {', '.join(BAR_DATASETS)}.", tc_bar_datasets, st)
        case("TC-SUM-23", "C Category Wise Variance", "Available Value per category = Σ min(stock, audited) × cost price",
             chart, "Available Value = Σ Available qty × cost price, Available qty = min(Stock Qty, Audited Qty) "
             "(stock 10 / audited 5 → 5; 10 / 15 → 10; 10 / 10 → 10).", tc_bar_values, st, "Available Value")
        case("TC-SUM-24", "C Category Wise Variance", "Stock Loss per category = Negative Variance value", chart,
             "Stock Loss = Σ |Variance Value| of the Negative Variance rows (Not Found included, Un Verified left out).",
             tc_bar_values, st, "Stock Loss")
        case("TC-SUM-25", "C Category Wise Variance", "Excess Value per category = Positive Variance value", chart,
             "Excess Value = Σ Variance Value of the Positive Variance rows, excess line items (stock 0) included.",
             tc_bar_values, st, "Excess Value")
        case("TC-SUM-26", "C Category Wise Variance", "Available + Stock Loss = Stock value card", chart,
             "Σ Available Value + Σ Stock Loss = Stock value card (Un Verified stock left out).", tc_bar_card, st,
             "Stock Loss", "stock")
        case("TC-SUM-27", "C Category Wise Variance", "Available + Excess = Audited value card", chart,
             "Σ Available Value + Σ Excess Value = Audited value card.", tc_bar_card, st, "Excess Value", "audited")

        # ---------------- D
        doughnut = value_steps + ["Read the Category Wise Variance and Overall Variance chart data."]
        case("TC-SUM-31", "D Overall Variance", "Doughnut slices match the bar datasets", doughnut,
             "Labels and colours = Available Value, Stock Loss, Excess Value in the bar chart's order and colours.",
             tc_pie_labels, st)
        case("TC-SUM-32", "D Overall Variance", "Each slice is its share of Available + Stock Loss + Excess", doughnut,
             "Slice % = value ÷ (Available + Stock Loss + Excess) × 100 (±1).", tc_pie_share, st)
        case("TC-SUM-33", "D Overall Variance", "Doughnut slices add up to 100%", doughnut,
             "The slices add up to 100 (±1).", tc_pie_sum, st)

        # ---------------- E
        badges = opened + ["Click each filter badge and read every table page."]
        case("TC-SUM-41", "E Filter badges", "All 10 filter badges are shown", opened,
             f"Badges: {', '.join(RULES)}.", tc_badges_shown, st)
        case("TC-SUM-42", "E Filter badges", "Each badge count = rows listed under it", badges,
             "The number on each badge = the rows it lists.", tc_badge_rows, page, Config, st)
        case("TC-SUM-43", "E Filter badges", "Rows under each badge meet its rule", badges,
             "Matched: variance 0; Un Verified: '-'; Not Found: stock > 0, audited 0; Excess Line Item: stock 0, "
             "audited > 0; Positive / Negative: variance > 0 / < 0; Location Conflict: counted at another location; "
             "Damaged Report: damaged > 0.", tc_badge_rules, st)
        case("TC-SUM-44", "E Filter badges", "Badge counts = rows of All that meet each rule", opened + ["Read the All rows."],
             "Each badge count = the All rows that meet its rule.", tc_badge_counts, st)
        case("TC-SUM-45", "E Filter badges", "Badge counts add up", opened,
             "All = Matched + Positive + Negative + Un Verified; Excess ≤ Positive; Not Found ≤ Negative; "
             "Location Conflict, Damaged Report, Cross Checked ≤ All.", tc_badge_sums, st)

        # ---------------- F
        case("TC-SUM-51", "F Summarize As", f"Summarize As offers {', '.join(options)}", opened + ["Open Summarize As."],
             f"Options for {kind} inventory: {', '.join(options)}.", tc_summarize_options, st, options, kind)
        case("TC-SUM-52", "F Summarize As", "Every view: Variance = Audited − Stock, Variance Type matches its sign",
             view_steps, "Variance = Audited − Stock; Positive > 0, Negative < 0, '-' = 0.", tc_views_variance, st)
        case("TC-SUM-53", "F Summarize As", "Every view: Variance Value = Variance × cost price", view_steps + value_steps[1:],
             "Variance Value = Variance × the item's cost price.", tc_views_value, st)
        case("TC-SUM-54", "F Summarize As", "Every view: Stock / Audited / Damaged totals = the summary cards", view_steps,
             "Column totals = Stock / Audited / Damaged cards.", tc_views_totals, st)
        case("TC-SUM-55", "F Summarize As", "Item view lists each item once", opened + ["Read every table page."],
             "No item code twice.", tc_item_view_unique, st)
        case("TC-SUM-56", "F Summarize As", "Auditor / Location / UOM views add up to the Item view per item", view_steps,
             "Per item, the rows of each view add up to the Item view (audited; stock for Location / UOM).",
             tc_views_add_up, st)

        # ---------------- G
        case("TC-SUM-61", "G Qty / Value", "Value cards = Σ qty × cost price", value_steps,
             "Stock / Audited / Damaged value = Σ quantity × cost price.", tc_value_cards, st)
        case("TC-SUM-62", "G Qty / Value", "Qty button brings back the quantity cards", opened + ["Click Value, then Qty."],
             "The cards show the quantities again and Qty is active.", tc_qty_back, page, Config, st)
        case("TC-SUM-63", "G Qty / Value", "Cost price behind the Value cards = item master cost", value_steps,
             "Each item's cost price read on the page (Value card ÷ qty after searching it) = its item master cost.",
             tc_cost_master, st)

        # ---------------- H
        search = opened + ["Type in Search Item Code / Item Name and read the rows, badges and cards.", "Clear the search."]
        found = "Only rows whose code or name contains the text; badges and cards recalculated for those rows."
        case("TC-SUM-71", "H Search", "Search by item code", search, found, tc_search, page, Config, st, "code")
        case("TC-SUM-72", "H Search", "Search by item name", search, found, tc_search, page, Config, st, "name")
        case("TC-SUM-73", "H Search", "Search by part of an item code", search, found, tc_search, page, Config, st, "partial")
        case("TC-SUM-74", "H Search", "Search with no match shows no rows and zero badges / cards", search,
             "No rows; every badge and card is 0.", tc_search, page, Config, st, "no match")
        case("TC-SUM-75", "H Search", "Clearing the search brings back every row, badge and card", search,
             "Same rows, badges and cards as before the search.", tc_search_clear, page, Config, st)

        # ---------------- I
        for n, column in enumerate(FILTER_COLUMNS, 81):
            case(f"TC-SUM-{n}", "I Column filters", f"Column filter: {column}",
                 opened + [f"Open the {column} column filter.", f"Tick each option (up to {MAX_FILTER_OPTIONS}) and Apply.",
                           "Untick it; then Select All and Apply; then untick Select All."],
                 "Options = the column's values; each option lists only its rows; no option / Select All lists every row.",
                 tc_column_filter, page, Config, st, column)

        # ---------------- J
        sort = opened + ["Click the column header (ascending), then again (descending)."]
        case("TC-SUM-91", "J Sort", "Number columns sort ascending and descending", sort,
             "Rows in number order both ways; aria-sort ascending / descending.", tc_sort, page, Config, st, "numeric")
        case("TC-SUM-92", "J Sort", "Text columns sort ascending and descending", sort,
             "Rows in alphabetical order both ways; aria-sort ascending / descending.", tc_sort, page, Config, st, "text")
        case("TC-SUM-93", "J Sort", "Audited Date sorts ascending and descending", sort,
             "Rows in date order both ways; aria-sort ascending / descending.", tc_sort, page, Config, st, "date")
        case("TC-SUM-94", "J Sort", "Location / history columns keep the same rows when sorted", sort,
             "The same rows are listed (order not checked for list values).", tc_sort, page, Config, st, "composite")

        # ---------------- K
        paging = opened + ["Choose each rows-per-page size and go through every page."]
        case("TC-SUM-101", "K Paging", "Rows per page offers 25 / 50 / 100 / 200", opened + ["Open the rows-per-page list."],
             "Options 25, 50, 100, 200.", tc_page_sizes, page, Config, st)
        case("TC-SUM-102", "K Paging", "Each page size shows the right rows and page count", paging,
             "Page 1 has min(rows, size) rows; pages = ceil(rows ÷ size).", tc_paging, page, Config, st)
        case("TC-SUM-103", "K Paging", "Going through all pages lists every row once", paging,
             "Every row appears once over all pages.", tc_paging_rows, st)

        # ---------------- L
        export = opened + ["Click Export and open the downloaded file."]
        case("TC-SUM-111", "L Export", "Export downloads the report", export, "A file downloads with the report rows.",
             tc_export, page, Config, st, folder)
        case("TC-SUM-112", "L Export", "Export has one row per report row", export,
             "Export rows = All badge rows.", tc_export_rows, st)
        case("TC-SUM-113", "L Export", "Export has the report columns", export,
             f"Columns include {', '.join(EXPORT_CORE)}.", tc_export_columns, st)
        case("TC-SUM-114", "L Export", "Export values = the report", export,
             "Per item, Stock / Audited / Variance / Variance Value / Damaged = the report table; "
             "Cost Price = the cost price the page uses.", tc_export_values, st)
        case("TC-SUM-115", "L Export", "Each badge sheet lists the same rows as the badge", export,
             "Every badge's sheet has exactly the rows the page lists under that badge.", tc_export_badge_sheets, st)
        case("TC-SUM-116", "L Export", "Export has a sheet for every filter badge", export,
             f"One sheet per badge: {', '.join(RULES)}.", tc_export_sheet_names, st)

        # ---------------- M
        case("TC-SUM-121", "M Combined filters", "Badge + search lists rows that meet both",
             opened + ["Click a filter badge.", "Search part of an item code."],
             "Only rows that meet the badge rule and match the search.", tc_badge_and_search, page, Config, st)
        case("TC-SUM-122", "M Combined filters", "Badge + column filter lists rows that meet both",
             opened + ["Click a filter badge.", "Filter Category on one value."],
             "Only rows that meet the badge rule and have that category.", tc_badge_and_filter, page, Config, st)

        # ---------------- N
        case("TC-SUM-130", "N No side effects", "Audit status, badges and cards unchanged after the tests",
             ["Reopen the Audit Summary after all cases."], "Same status, badges and cards as at the start.",
             tc_unchanged, page, Config, st)
    finally:
        try:
            _close_insights(page)
        except Exception:
            pass
        ok, _ = write_report(
            run, folder, audit, Config, label="AUDIT SUMMARY PAGE TESTS", file_prefix="Summary_Page_Tests",
            sub_module="Audit Summary",
            preconditions=f"1. User is logged in as the audit owner.\n2. Audit {audit} has counted lines.",
            impact="Variances are reviewed and resolved on wrong numbers or an incomplete list.",
            fix="Check the summary API and the page's chart, card and filter calculations against the report rows.",
            severity=_severity)
    return ok
