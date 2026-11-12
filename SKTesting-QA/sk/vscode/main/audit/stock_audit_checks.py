"""
Stock Audit (v2) page checks — run by A_SA after its Excel loop.

Tests the new page features and cross-checks the numbers end to end:
  Excel rows counted -> Recently audited list -> Count summary
                     -> Audit Declaration (Finish audit) -> Audit Summary

Nothing irreversible is clicked: Finish audit only opens the declaration
page (no notes chosen, the final "Finish Audit" button is not pressed), and
Complete Audit, Archive, Export, Print and row Delete are never clicked.
"""
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from audit.Auditor_1 import (
    ASV2_ADD_ITEM_BTN, ASV2_CONTINUOUS, ASV2_LIST_COUNT, ASV2_LIST_REFRESH,
)
from audit.A_audit_Summary import (
    BizRules, Config as SummaryCfg, click_badge, collect_all, navigate_to_audit,
)

STOCK_PAGE   = "app-audit-stock-v2"
STOCK_FORM   = "app-audit-stock-v2 form.asv2-form"
STATUS_VALUE = "app-audit-stock-v2 .asv2-status-value"
FINISH_BTN   = "button[data-tour-id='finish-audit-btn']"
SWAP_BTN     = "app-audit-stock-v2 button.asv2-swap-btn"
LIST         = "app-audit-stock-list-v2"
LIST_SEARCH  = f"{LIST} input[placeholder='Search code / name']"
COUNT_DLG    = "div.count-summary-dialog"
COUNT_DLG_CLOSE = f"{COUNT_DLG} button.asv2-dialog-close, {COUNT_DLG} button.cs-close"   # new / older builds
PRINT_DLG    = "div.lp-print-dialog"
DECLARATION  = "app-audit-declaration"
SUMMARY      = "app-audit-summary"

ROWS_JS = """(tbody) => [...tbody.querySelectorAll(':scope > tr')].map(tr =>
    [...tr.querySelectorAll(':scope > td')].map(td => (td.innerText || '').trim()))"""

# (code, audited, damaged, audit location in effect when counted)
Entered = Tuple[str, float, Optional[float], Optional[str]]


# --------------------------------------------------------------
# RESULT COLLECTOR
# --------------------------------------------------------------
class Results:
    def __init__(self):
        self.rows: List[Tuple[str, str, bool, str]] = []

    def check(self, area: str, name: str, ok: bool, detail="") -> bool:
        self.rows.append((area, name, bool(ok), str(detail)))
        print(f"   {'PASS' if ok else 'FAIL'}  {area} > {name}  {detail}")
        return bool(ok)

    def section(self, area: str, fn, *args) -> None:
        print(f"\n🔷 {area}")
        try:
            fn(*args)
        except Exception as e:
            self.check(area, "section ran", False, f"error: {str(e).splitlines()[0][:160]}")

    def report(self, title: str = "STOCK AUDIT v2 — FEATURE / CROSS-CHECK SUMMARY") -> bool:
        passed = sum(1 for r in self.rows if r[2])
        failed = len(self.rows) - passed
        print("\n" + "=" * 110)
        print(f"  {title}")
        print("=" * 110)
        print(f"  {'Area':<22} {'Check':<46} {'Result':<6}  Detail")
        print("  " + "-" * 106)
        for area, name, ok, detail in self.rows:
            print(f"  {area:<22} {name[:46]:<46} {'PASS' if ok else 'FAIL':<6}  {detail[:60]}")
        print("  " + "-" * 106)
        print(f"  TOTAL: {len(self.rows)}   PASS: {passed}   FAIL: {failed}")
        print("=" * 110)
        return failed == 0


# --------------------------------------------------------------
# SMALL HELPERS
# --------------------------------------------------------------
def _num(text) -> float:
    s = str(text or "").replace(",", "").strip()
    m = re.match(r"^[-+]?\d+(\.\d+)?", s)       # resolution pages show "+3"
    return float(m.group()) if m else 0.0


def _first_int(text) -> Optional[int]:
    m = re.search(r"\d+", text or "")
    return int(m.group()) if m else None


def _clean(text) -> str:
    return " ".join(str(text or "").split())


def read_list_count(page) -> Optional[int]:
    try:
        return _first_int(page.locator(ASV2_LIST_COUNT).inner_text(timeout=5000))
    except Exception:
        return None


def _table(page, scope: str) -> Tuple[Dict[str, int], List[List[str]]]:
    """Header index (upper-cased text) and data rows of the first table in scope."""
    headers = [_clean(h).upper() for h in page.locator(f"{scope} thead th").all_inner_texts()]
    body = page.locator(f"{scope} tbody").first
    rows = [r for r in body.evaluate(ROWS_JS) if len(r) == len(headers)]
    return {h: i for i, h in enumerate(headers)}, rows


# --------------------------------------------------------------
# RECENTLY AUDITED LIST HELPERS
# --------------------------------------------------------------
def _list_search(page, text: str) -> None:
    box = page.locator(LIST_SEARCH)
    box.fill(text)
    box.press("Enter")          # the list filters on Enter, not while typing
    page.wait_for_timeout(1500)


def _list_all_auditors(page, on: bool) -> None:
    switch = page.locator(f"{LIST} label.aslv2-switch")
    if switch.locator("input[type='checkbox']").is_checked() != on:
        switch.click()
        page.wait_for_timeout(1500)


def _list_page_size(page, size: str = "100") -> None:
    page.locator(f"{LIST} .apg-size p-dropdown").first.click()
    options = page.locator("li.p-dropdown-item:visible")
    options.first.wait_for(state="visible", timeout=5000)
    wanted = options.filter(has_text=re.compile(rf"^\s*{size}\s*$"))
    (wanted if wanted.count() else options.last).first.click()
    page.wait_for_timeout(1500)


def _list_read_all(page) -> Tuple[Dict[str, int], List[List[str]]]:
    idx, rows = _table(page, LIST)
    for _ in range(50):
        nxt = page.locator(f"{LIST} button[aria-label='Next page']")
        if nxt.count() == 0 or nxt.is_disabled():
            break
        nxt.click()
        page.wait_for_timeout(1200)
        rows += _table(page, LIST)[1]
    first = page.locator(f"{LIST} button[aria-label='First page']")
    if first.count() and first.is_enabled():
        first.click()
        page.wait_for_timeout(800)
    return idx, rows


def _list_totals(idx, rows) -> Dict[str, Dict[str, float]]:
    per_code: Dict[str, Dict[str, float]] = {}
    for r in rows:
        t = per_code.setdefault(r[idx["ITEM CODE"]], {"audited": 0.0, "damaged": 0.0, "entries": 0})
        t["audited"] += _num(r[idx["AUDITED QTY"]])
        if "DAMAGED QTY" in idx:
            t["damaged"] += _num(r[idx["DAMAGED QTY"]])
        t["entries"] += 1
    return per_code


# --------------------------------------------------------------
# 1. PAGE / TOOLBAR
# --------------------------------------------------------------
def check_toolbar(page, res: Results, state: dict) -> None:
    area = "Toolbar"
    state["status"] = _clean(page.locator(STATUS_VALUE).inner_text())
    progress = page.locator(f"{STOCK_PAGE} .asv2-status [role='progressbar']").get_attribute("aria-valuenow")
    res.check(area, "Audit status shown", bool(state["status"]), f"{state['status']} ({progress}%)")

    for name, sel in [
        ("Count summary button", f"{STOCK_PAGE} button:has-text('Count summary')"),
        ("Finish audit button", FINISH_BTN),
        ("Add item button", ASV2_ADD_ITEM_BTN),
        ("Barcode scanner button", f"{STOCK_PAGE} button[aria-label='Open barcode scanner']"),
    ]:
        res.check(area, name, page.locator(sel).first.is_visible())

    switch = page.locator(ASV2_CONTINUOUS)
    hidden = switch.locator("input[role='switch']")
    before = hidden.get_attribute("aria-checked")
    switch.click()
    page.wait_for_timeout(300)
    toggled = hidden.get_attribute("aria-checked")
    switch.click()
    page.wait_for_timeout(300)
    res.check(area, "Continuous switch toggles", toggled != before and hidden.get_attribute("aria-checked") == before,
              f"{before} -> {toggled} -> restored")

    swap = page.locator(SWAP_BTN)
    before = swap.get_attribute("aria-pressed")
    swap.click()
    page.wait_for_timeout(400)
    toggled = swap.get_attribute("aria-pressed")
    swap.click()
    page.wait_for_timeout(400)
    res.check(area, "Swap sections toggles", toggled != before and swap.get_attribute("aria-pressed") == before,
              f"{before} -> {toggled} -> restored")


# --------------------------------------------------------------
# 2 + 3. RECENTLY AUDITED LIST + EXCEL -> LIST CROSS-CHECK
# --------------------------------------------------------------
def check_list(page, res: Results, state: dict, entered: List[Entered], count_before: Optional[int]) -> None:
    area = "Recently audited"
    page.locator(ASV2_LIST_REFRESH).click()
    page.wait_for_timeout(1500)
    _list_all_auditors(page, False)

    count_now = read_list_count(page)
    if count_before is not None:
        res.check(area, "Entries increased by counts added", count_now == count_before + len(entered),
                  f"before={count_before} now={count_now} added={len(entered)}")

    _list_page_size(page, "100")
    idx, rows = _list_read_all(page)
    res.check(area, "Rows per page = 100 shows all entries", len(rows) == count_now,
              f"rows={len(rows)} pill={count_now}")

    code = entered[0][0] if entered else (rows[0][idx["ITEM CODE"]] if rows else "")
    if code:
        _list_search(page, code)
        _, found = _table(page, LIST)
        codes = {r[idx["ITEM CODE"]] for r in found}
        res.check(area, f"Search filters to {code}", bool(found) and codes == {code},
                  f"{len(found)} row(s), codes={sorted(codes)[:3]}")
        _list_search(page, "")

    own = read_list_count(page)
    _list_all_auditors(page, True)
    everyone = read_list_count(page)
    res.check(area, "All auditors shows >= own entries", (everyone or 0) >= (own or 0),
              f"own={own} all={everyone}")
    all_idx, all_rows = _list_read_all(page)
    state["list_totals"] = _list_totals(all_idx, all_rows)
    state["list_entries"] = len(all_rows)
    _list_all_auditors(page, False)

    # Excel -> list: newest rows for a code belong to the last counts of that code
    area = "Cross: Excel > list"
    by_code: Dict[str, List[List[str]]] = {}
    for r in rows:
        by_code.setdefault(r[idx["ITEM CODE"]], []).append(r)
    seen: Dict[str, int] = {}
    for code, audited, damaged, location in reversed(entered):
        n = seen.get(code, 0)
        seen[code] = n + 1
        matches = by_code.get(code, [])
        if n >= len(matches):
            res.check(area, f"{code} row in list", False, "not found")
            continue
        row = matches[n]
        act_aud = _num(row[idx["AUDITED QTY"]])
        act_dam = _num(row[idx["DAMAGED QTY"]]) if "DAMAGED QTY" in idx else 0.0
        act_loc = _clean(row[idx["AUDITED LOCATION"]]) if "AUDITED LOCATION" in idx else ""
        location = location or state["item_locations"].get(code)    # no location chosen: the item's own
        exp_loc = location.split("-")[-1] if location else "Unassigned"
        res.check(area, f"{code} audited qty", act_aud == float(audited), f"excel={audited} list={act_aud}")
        res.check(area, f"{code} damaged qty", act_dam == float(damaged or 0), f"excel={damaged} list={act_dam}")
        res.check(area, f"{code} audited location", exp_loc.lower() in act_loc.lower(),
                  f"excel={location or '-'} list={act_loc}")


# --------------------------------------------------------------
# 4. COUNT SUMMARY
# --------------------------------------------------------------
def _count_summary_tab(page, tab: str) -> Tuple[Dict[str, int], List[List[str]]]:
    dlg = page.locator(COUNT_DLG)
    dlg.locator(f".p-tabview-nav li:has-text('{tab}')").click()
    page.wait_for_timeout(1500)
    scope = f"{COUNT_DLG} .p-tabview-panel:not([aria-hidden='true'])"
    idx, rows = _table(page, scope)
    for _ in range(50):
        nxt = page.locator(f"{scope} button.p-paginator-next")
        if nxt.count() == 0 or nxt.is_disabled():
            break
        nxt.click()
        page.wait_for_timeout(1000)
        rows += _table(page, scope)[1]
    return idx, rows


def check_count_summary(page, res: Results, state: dict, entered: List[Entered], run_started: datetime) -> None:
    area = "Count summary"
    entries = state.get("list_entries")
    totals = state.get("list_totals", {})
    list_qty = sum(t["audited"] for t in totals.values())

    page.locator(f"{STOCK_PAGE} button:has-text('Count summary')").click()
    page.locator(COUNT_DLG).wait_for(state="visible", timeout=10000)
    page.wait_for_timeout(1500)
    try:
        idx, rows = _count_summary_tab(page, "Time Wise")
        items_col = next(h for h in idx if h.startswith("ITEMS AUDITED"))
        qty_col = next(h for h in idx if h.startswith("QTY COUNTED"))
        items = sum(_num(r[idx[items_col]]) for r in rows)
        qty = sum(_num(r[idx[qty_col]]) for r in rows)
        res.check(area, "Time Wise items = list entries", items == entries, f"time-wise={items:g} list={entries}")
        res.check(area, "Time Wise qty = list audited qty", qty == list_qty, f"time-wise={qty:g} list={list_qty:g}")

        if entered:
            # Time stamps are in the app's time zone, not this PC's: take the newest
            # one as "now" and look back over this run's duration.
            stamped = []
            for r in rows:
                try:
                    stamped.append((datetime.strptime(r[idx["TIME STAMP"]], "%b %d, %Y, %I:%M %p"), r))
                except ValueError:
                    continue
            newest = max((ts for ts, _ in stamped), default=None)
            minutes = int((datetime.now() - run_started).total_seconds() // 60) + 1
            recent = [r for ts, r in stamped if newest and (newest - ts).total_seconds() <= minutes * 60]
            run_qty = sum(float(e[1]) for e in entered)
            got = sum(_num(r[idx[qty_col]]) for r in recent)
            res.check(area, "Time Wise has this run's counts", got >= run_qty,
                      f"last {minutes} min up to {newest:%b %d %H:%M}: qty={got:g} expected>={run_qty:g}"
                      if newest else "no time stamps")

        for tab in ("Category Wise", "Location Wise"):
            idx, rows = _count_summary_tab(page, tab)
            qty_col = next(h for h in idx if "QTY COUNTED" in h)
            tab_qty = sum(_num(r[idx[qty_col]]) for r in rows)
            res.check(area, f"{tab} total qty = list audited qty", tab_qty == list_qty,
                      f"{tab_qty:g} vs {list_qty:g} ({len(rows)} row(s))")
            if tab == "Category Wise":
                tab_items = sum(_num(r[idx["ITEMS AUDITED"]]) for r in rows)
                res.check(area, "Category Wise items = distinct items counted", tab_items == len(totals),
                          f"{tab_items:g} vs {len(totals)}")
            else:
                labels = " | ".join(r[0] for r in rows).lower()
                for loc in sorted({(e[3] or state["item_locations"].get(e[0]) or "Unassigned") for e in entered}):
                    res.check(area, f"Location Wise lists {loc}", loc.split("-")[-1].lower() in labels, labels[:60])
    finally:
        from audit.finish_complete_flow import _close_guide
        _close_guide(page)                   # the guide panel can slide in over the dialog's close button
        page.locator(COUNT_DLG_CLOSE).first.click(timeout=10000)      # Escape does not close it
        page.locator(COUNT_DLG).wait_for(state="hidden", timeout=5000)


# --------------------------------------------------------------
# 5. PRINT LABELS (open + cancel only)
# --------------------------------------------------------------
def check_print_labels(page, res: Results) -> None:
    area = "Print labels"
    checkbox = page.locator(f"{LIST} tbody tr").first.locator("p-tablecheckbox .p-checkbox-box")
    btn = page.locator(f"{LIST} button[aria-label='Print labels']")
    checkbox.click()
    page.wait_for_timeout(500)
    res.check(area, "Enabled after selecting a row", btn.is_enabled())
    btn.click()
    dlg = page.locator(PRINT_DLG)
    dlg.wait_for(state="visible", timeout=8000)
    res.check(area, "Dialog opens", "Print Labels" in dlg.inner_text(), _clean(dlg.inner_text())[:50])
    dlg.locator("button.danger-button:has-text('Cancel')").click()
    dlg.wait_for(state="hidden", timeout=5000)
    res.check(area, "Cancel closes dialog", True)
    checkbox.click()
    page.wait_for_timeout(500)
    res.check(area, "Disabled after clearing selection", btn.is_disabled())


# --------------------------------------------------------------
# 6. FINISH AUDIT -> AUDIT DECLARATION (no notes, final Finish not pressed)
# --------------------------------------------------------------
def check_finish_declaration(page, res: Results, state: dict) -> None:
    area = "Finish > Declaration"
    page.locator(FINISH_BTN).click()
    decl = page.locator(DECLARATION)
    decl.wait_for(state="visible", timeout=15000)
    page.wait_for_timeout(1500)
    text = _clean(decl.inner_text())

    head = re.split(r"\bS\.?\s?NO\b", text, maxsplit=1, flags=re.I)[0]   # text above the table only
    progress = re.search(r"(\d+)\s+of\s+(\d+)\s+discrepancies declared", head, re.I)
    chips = {name.strip().upper(): int(n) for n, name in
             re.findall(r"(\d+)\s+(ITEMS|POSITIVE VARIANCE|EXCESS LINEITEM|NEGATIVE VARIANCE|NOT FOUND|UNVERIFIED)\b",
                        head, re.I)}
    idx, rows = _table(page, DECLARATION)
    state["declaration"] = {r[idx["ITEM CODE"]]: r for r in rows}
    state["declaration_idx"] = idx
    # uncounted items are listed as "Un Verified" and are not declared
    declarable = [r for r in rows if "un verified" not in r[idx["DISCREPANCY TYPE"]].lower()]

    res.check(area, "Opens declaration page", True, progress.group(0) if progress else text[:60])
    res.check(area, "Item rows = ITEMS chip", chips.get("ITEMS") == len(rows), f"rows={len(rows)} chips={chips}")
    res.check(area, "Progress total = declarable discrepancies",
              not progress or int(progress.group(2)) == len(declarable),
              f"progress={progress.group(0) if progress else '-'} declarable={len(declarable)}")
    res.check(area, "Discrepancy chips add up to ITEMS",
              sum(v for k, v in chips.items() if k != "ITEMS") == chips.get("ITEMS"), str(chips))

    for r in rows:
        code = r[idx["ITEM CODE"]]
        stock, audited = _num(r[idx["STOCK QTY"]]), _num(r[idx["AUDITED QTY"]])
        kind = r[idx["DISCREPANCY TYPE"]].lower()
        if stock == 0 and audited > 0:
            ok = "excess" in kind
        elif audited == 0 and stock > 0:
            ok = "not found" in kind or "negative" in kind or "un verified" in kind
        elif audited > stock:
            ok = "positive" in kind and f"({audited - stock:g})" in kind
        else:
            ok = "negative" in kind
        res.check(area, f"{code} discrepancy type", ok, f"stock={stock:g} audited={audited:g} -> {r[idx['DISCREPANCY TYPE']]}")
        totals = state.get("list_totals", {}).get(code)
        if totals:
            res.check(area, f"{code} audited = list total", audited == totals["audited"],
                      f"declaration={audited:g} list={totals['audited']:g}")

    # Leave without declaring or finishing
    page.locator("a.cad-crumb-link", has_text="Stock Audit").last.click()
    page.locator(STOCK_FORM).wait_for(state="visible", timeout=20000)
    page.wait_for_timeout(1000)
    after = _clean(page.locator(STATUS_VALUE).inner_text())
    res.check(area, "Back to Stock Audit, audit not finished", after == state.get("status"),
              f"status {state.get('status')} -> {after}")


# --------------------------------------------------------------
# 7. AUDIT SUMMARY PAGE
# --------------------------------------------------------------
def _summary_metrics(page) -> Dict[str, float]:
    out = {}
    for m in page.locator(f"{SUMMARY} div.summary-metric").all():
        out[_clean(m.locator(".metric-label").inner_text()).lower()] = _num(m.locator(".metric-value").inner_text())
    return out


def check_audit_summary(page, Config, res: Results, state: dict, entered: List[Entered]) -> None:
    area = "Audit Summary"
    navigate_to_audit(page, Config)     # waits until the summary data has loaded
    page.locator(f"{SUMMARY} span.badge-custom").first.wait_for(state="visible", timeout=20000)
    page.wait_for_timeout(1500)

    tiles = {}
    for t in page.locator(f"{SUMMARY} div.audit-info-tile .tile-row").all():
        label = _clean(t.locator(".tile-label").inner_text())
        tiles[label] = _clean(t.inner_text())[len(label):].strip()
    res.check(area, "Audit name tile", tiles.get("Audit Name") == Config.ap_audit_name, tiles.get("Audit Name"))
    status = _clean(page.locator(f"{SUMMARY} div.status-pill").inner_text())
    res.check(area, "Status matches Stock Audit page", status.lower() == (state.get("status") or "").lower(),
              f"summary={status} stock page={state.get('status')}")
    empty = [k for k, v in tiles.items() if not v]
    res.check(area, "All detail tiles have values", not empty, f"{len(tiles)} tiles, empty={empty}")
    for name in ("Stock Audit", "Auditor Insights", "Archive", "Complete Audit"):
        res.check(area, f"'{name}' button visible",
                  page.locator(f"{SUMMARY} button.text-app-primary", has_text=name).first.is_visible())

    # ---- totals vs table (All badge) vs Stock Audit list
    qty = _summary_metrics(page)
    cfg = SummaryCfg()
    all_count = click_badge(page, cfg, "All")
    rows = collect_all(page, cfg)
    res.check(area, "All badge count = rows", all_count == len(rows), f"badge={all_count} rows={len(rows)}")
    for metric, field in (("stock", "Stock Quantity"), ("audited", "Audited Qty"), ("damaged", "Damaged Qty")):
        col_sum = sum(_num(r.get(field)) for r in rows)
        res.check(area, f"{metric.title()} total = table sum", qty.get(metric) == col_sum,
                  f"metric={qty.get(metric)} table={col_sum:g}")
    totals = state.get("list_totals", {})
    if totals:
        res.check(area, "Audited total = Stock Audit list",
                  qty.get("audited") == sum(t["audited"] for t in totals.values()),
                  f"{qty.get('audited')} vs {sum(t['audited'] for t in totals.values()):g}")
        res.check(area, "Damaged total = Stock Audit list",
                  qty.get("damaged") == sum(t["damaged"] for t in totals.values()),
                  f"{qty.get('damaged')} vs {sum(t['damaged'] for t in totals.values()):g}")

    by_code = {r.get("Item Code", "").upper(): r for r in rows}
    for code in sorted({e[0] for e in entered}):
        row, t = by_code.get(code.upper()), totals.get(code)
        if not row or not t:
            res.check("Cross: list > summary", f"{code} in summary", False, "row missing")
            continue
        res.check("Cross: list > summary", f"{code} audited qty", _num(row.get("Audited Qty")) == t["audited"],
                  f"summary={row.get('Audited Qty')} list={t['audited']:g}")
        res.check("Cross: list > summary", f"{code} damaged qty", _num(row.get("Damaged Qty")) == t["damaged"],
                  f"summary={row.get('Damaged Qty')} list={t['damaged']:g}")

    # ---- business rules on every row
    bad = []
    for r in rows:
        var = r.get("Variance", "")
        if var.strip() == "-":
            continue
        diff = _num(r.get("Audited Qty")) - _num(r.get("Stock Quantity"))
        vtype = r.get("Variance Type", "").lower()
        type_ok = ("positive" in vtype) if diff > 0 else ("negative" in vtype) if diff < 0 else True
        if _num(var) != diff or not type_ok:
            bad.append(f"{r.get('Item Code')}: var={var} type={vtype}")
    res.check(area, "Variance = Audited - Stock, type matches sign", not bad, "; ".join(bad)[:60])

    # ---- declaration (Finish audit) vs summary
    decl, didx = state.get("declaration"), state.get("declaration_idx")
    if decl is not None:
        discrepant = {c for c, r in by_code.items() if _num(r.get("Variance")) != 0 and r.get("Variance", "").strip() != "-"}
        res.check("Cross: declaration", "Declaration items = summary rows with variance",
                  {c.upper() for c in decl} == discrepant,
                  f"declaration={sorted(decl)} summary={sorted(discrepant)}")
        for code, r in decl.items():
            srow = by_code.get(code.upper())
            if srow:
                res.check("Cross: declaration", f"{code} audited = summary",
                          _num(r[didx["AUDITED QTY"]]) == _num(srow.get("Audited Qty")),
                          f"declaration={r[didx['AUDITED QTY']]} summary={srow.get('Audited Qty')}")

    # ---- badges: count matches rows and the badge's business rule holds
    biz = BizRules()
    for badge in ("Matched Line Item", "Positive Variance", "Negative Variance", "Location Conflict", "Damaged Report"):
        n = click_badge(page, cfg, badge)
        got = collect_all(page, cfg) if n else []
        broken = [r.get("Item Code") for r in got if biz.check(badge, r)]
        res.check(area, f"Badge '{badge}'", n == len(got) and not broken,
                  f"badge={n} rows={len(got)} rule-fails={broken[:3]}")
    click_badge(page, cfg, "All")

    # ---- Qty / Value toggle
    toggle = page.locator(f"{SUMMARY} div.summary-toggle")
    toggle.locator("button.toggle-btn", has_text="Value").click()
    page.wait_for_timeout(1000)
    value = _summary_metrics(page)
    toggle.locator("button.toggle-btn", has_text="Qty").click()
    page.wait_for_timeout(800)
    res.check(area, "Value toggle switches totals", value != qty and all(v >= 0 for v in value.values()),
              f"qty={qty} value={value}")
    res.check(area, "Qty toggle restores totals", _summary_metrics(page) == qty)

    # ---- search
    code = entered[0][0] if entered else (rows[0].get("Item Code") if rows else "")
    if code:
        search = page.locator(f"{SUMMARY} input[placeholder='Search Item Code / Item Name']")
        search.fill(code)
        search.press("Enter")
        page.wait_for_timeout(1500)
        found = collect_all(page, cfg)
        codes = {r.get("Item Code", "").upper() for r in found}
        res.check(area, f"Search filters to {code}", codes == {code.upper()}, f"{len(found)} row(s)")
        search.fill("")
        search.press("Enter")
        page.wait_for_timeout(1000)

    # ---- back to Stock Audit
    page.locator(f"{SUMMARY} button.text-app-primary", has_text="Stock Audit").first.click()
    try:
        page.locator(STOCK_FORM).wait_for(state="visible", timeout=20000)
        res.check(area, "'Stock Audit' button opens Stock Audit page", True)
    except Exception:
        res.check(area, "'Stock Audit' button opens Stock Audit page", False, page.url)


# --------------------------------------------------------------
# ENTRY POINT
# --------------------------------------------------------------
def run_stock_audit_checks(page, Config, entered: List[Entered], list_count_before: Optional[int],
                           run_started: datetime) -> bool:
    print("\n" + "-" * 70)
    print("🔷 STOCK AUDIT v2 — FEATURE CHECKS + CROSS-CHECK")
    print("-" * 70)
    # An end-to-end run can collect these checks into its own Results
    res = getattr(Config, "asv2_results", None) or Results()
    # {item code: stock location} when known: a count saved with no location chosen goes there
    state = {"item_locations": dict(getattr(Config, "asv2_item_locations", None) or {})}
    for area, fn, *args in (
            ("Toolbar", check_toolbar, page, res, state),
            ("Recently audited list", check_list, page, res, state, entered, list_count_before),
            ("Count summary", check_count_summary, page, res, state, entered, run_started),
            ("Print labels", check_print_labels, page, res),
            ("Finish audit", check_finish_declaration, page, res, state),
            ("Audit Summary", check_audit_summary, page, Config, res, state, entered)):
        _clear_page(page)
        res.section(area, fn, *args)
    return res.report()


def _clear_page(page) -> None:
    """Close what can be left over the Stock Audit page: the "Audit progress" guide panel (it slides in
    and covers dialog buttons) and a dialog a failed section left open."""
    from audit.finish_complete_flow import _close_guide      # imported here: that module imports this one
    _close_guide(page)
    if page.locator(f"{COUNT_DLG}:visible").count():
        page.locator(COUNT_DLG_CLOSE).first.click()
        page.locator(COUNT_DLG).wait_for(state="hidden", timeout=5000)
    if page.locator(f"{PRINT_DLG}:visible").count():
        page.locator(f"{PRINT_DLG} button.danger-button:has-text('Cancel')").click()
        page.locator(PRINT_DLG).wait_for(state="hidden", timeout=5000)
