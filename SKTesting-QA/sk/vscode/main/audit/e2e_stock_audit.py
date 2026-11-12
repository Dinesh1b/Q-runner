"""
End-to-end stock audit (Unit tracking) — stages 1-6 and the run report.

  1 Create Item Group   2 Import Items   3 Create Audit   4 Import Stock Sheet
  5 Stock Counting      6 Audit Summary  -> stages 7-9 in e2e_complete_resolution.py

Every run makes its own group, items, audit and workbook (run folder under
Config.e2e_output_dir) and writes Stock_Audit_E2E_<run>.xlsx with three sheets:
Tracker (stage PASS/FAIL/BLOCKED), Checks (every check) and Bugs (one card per failure).
"""
import os
import re
from collections import OrderedDict
from datetime import datetime

import pandas as pd

from audit.stock_audit_checks import Results, _clean, _num

STAGES = OrderedDict([
    (1, "Create Item Group"), (2, "Import Items"), (3, "Create Audit"), (4, "Import Stock Sheet"),
    (5, "Stock Counting"), (6, "Audit Summary"), (7, "Complete Audit"), (8, "Resolution"),
    (9, "Final Verification"),
])

# Areas used by the reused modules -> stage they belong to
AREA_STAGE = {
    "Toolbar": 5, "Recently audited": 5, "Cross: Excel > list": 5, "Count summary": 5, "Print labels": 5,
    "Audit Summary": 6, "Cross: list > summary": 6, "Cross: declaration": 6, "Summarize As": 6,
    "Finish > Declaration": 7, "Declaration": 7, "Summary before resolution": 7, "Complete popup": 7,
    "Start resolution": 7,
    "Resolution actions": 8, "Recount sub-audit": 8, "Recount review": 8, "Resolution summary": 8,
    "Adjustment report": 8,
    "Complete audit": 9, "Final report": 9, "Stock update": 9,
}

# "Summarize As" options the Complete Audit Report must offer, by inventory type
SUMMARIZE_AS = {
    "Unit":       ["Item", "Auditor", "Location", "UOM"],
    "Batch":      ["Batch", "Item", "Auditor", "Location", "UOM"],     # to confirm with the Batch run
    "Serial":     ["Serial", "Item", "Auditor", "Location", "UOM"],    # to confirm with the Serial run
    "Serialized": ["Serial", "Item", "Auditor", "Location", "UOM"],
}

SUMMARY = "app-audit-summary"


# ======================================================
# RUN DATA
# ======================================================
#            cost  stock location  stock counted damaged counted-at action        recount note
ITEM_PLAN = [
    (100, "SA-A1-B1-L1", 10, 10,   0,    None, "Accept",      None, "Misplaced"),     # matched
    (150, "SA-A1-B1-L2", 10, 13,   1,    None, "Accept",      None, "Inward Error"),  # positive
    (80,  "SA-A2-B3-L3", 10, 6,    None, None, "Recount",     9,    "Theft"),         # shortage
    (120, "SA-A1-B1-L3", 10, 10,   0,    "w1", "Accept",      None, "Misplaced"),     # location conflict
    (90,  "SA-A2-B3-L4", 10, None, None, None, "Accept",      None, "Misplaced"),     # not counted
    (200, "SA-A3-B5-L1", 10, None, None, None, "Accept",      None, "Misplaced"),     # not counted
    (60,  "SA-A3-B5-L2", 0,  5,    0,    None, "Investigate", None, "Misplaced"),     # excess (not on sheet)
]

# Run on an existing group (items + stock from Config.EXCEL_PATH sheet Data): counted, damaged, count location.
# None = no location chosen: the count goes to the item's own stock location (those SA-... locations are
# not in the audit location tree). Once a location is chosen it stays for the next counts, so the counts
# sheet lists the rows with a location last.
COUNT_PLAN_EXISTING = {
    "ITM0001": (10, None, None),     # matched
    "ITM0002": (13, 1, None),        # positive, damaged
    "ITM0003": (6, None, None),      # negative
    "ITM0004": (10, None, "w1"),     # matched qty, counted at another location
    "ITM0005": (None, None, None),   # not counted -> Un Verified
    "ITM0006": (None, None, None),   # not counted -> Un Verified
    "ITM0007": (12, None, None),     # positive
    "ITM0008": (8, None, None),      # negative
    "ITM0009": (10, None, None),     # matched
    "ITM0010": (4, 2, None),         # negative, damaged
}
EXCESS_COUNT, EXCESS_LOCATION = 5, "w1"     # Config.summary_excess_item: in the group, not on the sheet


def _item(code, name, category, cost, location, stock, counted, damaged, count_loc, barcode=""):
    num = lambda v: None if v is None or pd.isna(v) else float(v)
    return {"code": code, "name": name, "category": category, "barcode": barcode, "cost": num(cost),
            "sell": (num(cost) or 0) * 1.5, "location": location, "stock": num(stock) or 0.0,
            "counted": num(counted), "damaged": num(damaged), "count_loc": count_loc,
            "action": "Accept", "recount": None, "note": "Misplaced", "on_sheet": (num(stock) or 0) > 0}


def _existing_items(Config):
    """Items of an existing group as its stock sheet lists them (Config.EXCEL_PATH sheet Data), counted
    as COUNT_PLAN_EXISTING says, plus Config.summary_excess_item counted although it is not on the sheet."""
    items = []
    for _, r in pd.read_excel(Config.EXCEL_PATH, sheet_name="Data").iterrows():
        code = str(r["Item Code"]).strip()
        counted, damaged, count_loc = COUNT_PLAN_EXISTING.get(code, (None, None, None))
        items.append(_item(code, r["Item Name"], r["Category"], r["Cost Price"], r["Location"], r["Adjustmentqty"],
                           counted, damaged, count_loc))
    excess = getattr(Config, "summary_excess_item", None)
    if excess:
        items.append(_item(excess, excess, None, getattr(Config, "summary_excess_cost", None), None, 0,
                           EXCESS_COUNT, None, EXCESS_LOCATION))
    return items


def build_run(Config, existing_group=None) -> dict:
    now = datetime.now()
    prefix = "QA_SUM" if existing_group else getattr(Config, "e2e_prefix", "QA_E2E")
    name = f"{prefix}_{now:%m%d_%H%M}"
    folder = os.path.join(Config.e2e_output_dir, name)
    os.makedirs(folder, exist_ok=True)
    if existing_group:
        items = _existing_items(Config)
    else:
        items = []
        for i, (cost, loc, stock, counted, damaged, count_loc, action, recount, note) in enumerate(ITEM_PLAN, 1):
            item = _item(f"E2E{now:%m%d%H%M}-{i:02d}", f"E2E Item {now:%m%d %H%M} {i:02d}",
                         getattr(Config, "e2e_category", "GMA"), cost, loc, stock, counted, damaged, count_loc,
                         barcode=f"88{now:%m%d%H%M}{i:02d}")
            item.update(action=action, recount=None if recount is None else float(recount), note=note)
            items.append(item)
    run = {"name": name, "group": existing_group or name, "audit": name, "folder": folder, "items": items,
           "workbook": os.path.join(folder, f"{name}_data.xlsx"), "started": now, "existing_group": existing_group,
           "inventory_type": getattr(Config, "e2e_inventory_type", "Unit"), "last_stage": 9}

    items_df = pd.DataFrame([{
        "Item Name": i["name"], "Item Code": i["code"], "Category": i["category"],
        "UOM": getattr(Config, "e2e_uom", "kg"), "Cost Price": i["cost"], "Sell Price": i["sell"],
        "Location": i["location"], "Barcode": i["barcode"],
    } for i in items])
    stock_df = pd.DataFrame([{
        "Item Code": i["code"], "Item Name": i["name"], "Location": i["location"], "Adjustmentqty": i["stock"],
    } for i in items if i["on_sheet"]])
    counts_df = pd.DataFrame([{
        "locations": i["count_loc"], "code": i["code"], "audited": i["counted"], "damaged": i["damaged"],
    } for i in sorted(items, key=lambda i: i["count_loc"] is not None)    # a chosen location stays: last
        if i["counted"] is not None])
    flow_df = pd.DataFrame([{
        "code": i["code"], "declaration_note": i["note"], "resolution": i["action"],
        "recount_qty": i["recount"], "remarks": f"e2e {i['action'].lower()}",
    } for i in items] + [{"code": "*", "declaration_note": "Misplaced", "resolution": "Accept",
                           "recount_qty": None, "remarks": "e2e default"}])
    with pd.ExcelWriter(run["workbook"]) as xl:
        items_df.to_excel(xl, sheet_name="Items", index=False)
        stock_df.to_excel(xl, sheet_name="Stock", index=False)
        counts_df.to_excel(xl, sheet_name="Counts", index=False)
        flow_df.to_excel(xl, sheet_name="finish_flow", index=False)
    return run


# ======================================================
# STAGE RUNNER
# ======================================================
def dismiss_version_banner(page):
    """Close the "New version available" banner whenever it appears over the page
    (its X, not Refresh: a reload would lose the wizard page the run is on)."""
    banner = page.get_by_text("New version available").locator("xpath=ancestor::*[.//button][1]")

    def close(_):
        page.keyboard.press("Escape")
        btn = banner.locator("button:not(:has-text('Refresh'))").first
        if btn.count() and btn.is_visible():
            btn.click()
        print("   ⚠️ 'New version available' banner closed")

    page.add_locator_handler(page.get_by_text("New version available"), close)


class StageRunner:
    def __init__(self, page, folder):
        self.page, self.folder = page, folder
        dismiss_version_banner(page)
        self.res = Results()
        self.meta = []          # per Results row: (stage, screenshot)
        self.blocked = {}       # stage -> reason
        self.skipped = {}       # stage -> reason (not needed in this run, e.g. an existing group)
        self.errored = set()    # stages that stopped on an exception

    def skip(self, n, reason):
        print("\n" + "=" * 70 + f"\n  STAGE {n}: {STAGES[n]}  — SKIPPED ({reason})\n" + "=" * 70)
        self.skipped[n] = reason

    def note(self, n):
        return self.blocked.get(n) or self.skipped.get(n, "")

    def _stage_of(self, area, default):
        m = re.match(r"^(\d)\. ", area)
        return int(m.group(1)) if m else AREA_STAGE.get(area, default)

    def run(self, n, fn, *args, needs=()):
        print("\n" + "=" * 70 + f"\n  STAGE {n}: {STAGES[n]}\n" + "=" * 70)
        stop = [d for d in needs if d in self.errored or d in self.blocked]
        if stop:
            self.blocked[n] = f"blocked by stage {', '.join(map(str, stop))}"
            print(f"   BLOCKED ({self.blocked[n]})")
            return
        start = len(self.res.rows)
        try:
            fn(*args)
        except (Exception, SystemExit) as e:
            if isinstance(e, SystemExit):     # import_app / Excel loaders exit on validation failures
                text = f"stopped with exit code {e.code} (see the console log for the failed checks)"
            else:
                text = str(e).splitlines()[0][:200] if str(e) else type(e).__name__
            self.res.check(f"{n}. {STAGES[n]}", "Stage completed", False, text)
            self.errored.add(n)
        shot = None
        if any(not r[2] for r in self.res.rows[start:]):
            shot = os.path.join(self.folder, f"stage{n}_{STAGES[n].replace(' ', '_')}.png")
            try:
                self.page.screenshot(path=shot, full_page=True)
            except Exception:
                shot = None
        for row in self.res.rows[start:]:
            self.meta.append((self._stage_of(row[0], n), shot))

    def stage_rows(self, n):
        return [r for r, (s, _) in zip(self.res.rows, self.meta) if s == n]

    def status(self, n):
        if n in self.skipped:
            return "SKIPPED"
        if n in self.blocked:
            return "BLOCKED"
        rows = self.stage_rows(n)
        if not rows:
            return "NOT RUN"
        return "PASS" if all(r[2] for r in rows) else "FAIL"


# ======================================================
# STAGES 1-6
# ======================================================
def stage_create_group(page, Config, run, res):
    from inventory.create_group import create_group
    create_group(page, Config)          # opens, applies settings, saves, verify_group raises on a wrong value
    res.check("1. Create Item Group", "Group created, saved values verified", True,
              f"{run['group']} ({Config.inventory_type})")


def stage_import_items(page, Config, run, res):
    from inventory.Item_import_add import import_app
    import_app(page, Config)            # import + list and edit-form validation; exits / raises on failures
    res.check("2. Import Items", "Items imported, list + edit form match the workbook", True,
              f"{len(run['items'])} items into {run['group']}")


def stage_create_audit(page, Config, run, res):
    from audit.Ad_hoc_Audit import Ad_hoc_Audit
    from audit.finish_complete_flow import _audit_list, _list_row
    Ad_hoc_Audit(page, Config)
    page.wait_for_timeout(3000)
    nav = page.locator("button[aria-label='Close navigation popup']")    # opens after create
    if nav.count() and nav.is_visible():
        nav.click()
        page.wait_for_timeout(800)
    _audit_list(page, Config)
    row = _list_row(page, run["audit"], "Complete Count")
    cells = [_clean(t) for t in row.locator("td").all_inner_texts()] if row.count() else []
    res.check("3. Create Audit", "Audit in Ongoing list", bool(cells), " | ".join(cells[1:])[:80])
    if cells:
        res.check("3. Create Audit", "Status Not Started", cells[-1] == "Not Started", cells[-1])


def stage_import_stock_sheet(page, Config, run, res):
    from audit.Ongo_Audit import Ongo_Audit
    from audit.finish_complete_flow import _audit_list, _close_guide, _list_row, _open_audit
    Ongo_Audit(page, Config)
    _close_guide(page)
    on_sheet = [i for i in run["items"] if i["on_sheet"]]
    _open_audit(page, Config, "Settings")
    page.wait_for_timeout(3000)
    text = _clean(page.locator("app-layout").first.inner_text())
    m = re.search(r"Line items (\d+) Stock qty (\d+)", text)
    lines, qty = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    res.check("4. Import Stock Sheet", "Line items = sheet rows", lines == len(on_sheet), f"page={lines} sheet={len(on_sheet)}")
    res.check("4. Import Stock Sheet", "Stock qty = sheet total", qty == sum(i["stock"] for i in on_sheet),
              f"page={qty} sheet={sum(i['stock'] for i in on_sheet):g}")
    _audit_list(page, Config)
    row = _list_row(page, run["audit"], "Complete Count")
    status = _clean(row.locator("td").last.inner_text()) if row.count() else ""
    res.check("4. Import Stock Sheet", "Status Stock Sheet Updated", status == "Stock Sheet Updated", status)


def stage_count(page, Config, run, res):
    from audit.Auditor_1 import stock_audit
    stock_audit(page, Config)           # A_SA + run_stock_audit_checks into res (Config.asv2_results)


def _summary_table(page):
    summ = page.locator(SUMMARY)
    headers = [_clean(h) for h in summ.locator("table thead th").all_inner_texts()]
    rows = []
    for _ in range(50):
        for r in summ.locator("tbody.p-datatable-tbody > tr").all():
            cells = [_clean(t) for t in r.locator("td").all_inner_texts()]
            if len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))
        nxt = summ.locator("button.p-paginator-next")
        if nxt.count() == 0 or nxt.first.is_disabled():
            break
        nxt.first.click()
        page.wait_for_timeout(1200)
    return rows


def _metrics(page):
    out = {}
    for m in page.locator(f"{SUMMARY} div.summary-metric").all():
        out[_clean(m.locator(".metric-label").inner_text()).lower()] = _num(m.locator(".metric-value").inner_text())
    return out


def stage_summary_views(page, Config, run, res):
    """Summarize As options per inventory type, per-view rows, cost-price variance value, totals."""
    from audit.A_audit_Summary import Config as SummaryCfg, click_badge
    from audit.e2e_complete_resolution import _sign_ok
    from audit.finish_complete_flow import _open_audit
    area = "Summarize As"
    items = {i["code"]: i for i in run["items"]}
    _open_audit(page, Config, "Audit Summary")
    click_badge(page, SummaryCfg(), "All")
    summ = page.locator(SUMMARY)

    dd = summ.locator("h6:has-text('Summarize As') ~ p-dropdown").first
    dd.click()
    page.wait_for_timeout(600)
    options = [_clean(t) for t in page.locator(".p-dropdown-panel:visible li.p-dropdown-item").all_inner_texts()]
    page.keyboard.press("Escape")
    expected = SUMMARIZE_AS.get(Config.inventory_type, SUMMARIZE_AS["Unit"])
    res.check(area, f"Options for {Config.inventory_type} = {', '.join(expected)}", sorted(options) == sorted(expected),
              f"shown={options}")

    qty = _metrics(page)
    views = {}
    for option in [o for o in options if o in ("Item", "Location", *expected)]:
        dd.click()
        page.wait_for_timeout(500)
        page.locator(".p-dropdown-panel:visible li.p-dropdown-item", has_text=option).first.click()
        page.wait_for_timeout(2500)
        rows = [r for r in _summary_table(page) if r.get("Item Code") in items]
        views[option] = rows
        bad_var, bad_val, bad_type = [], [], []
        for r in rows:
            code = r["Item Code"]
            if r.get("Variance", "").strip() == "-":
                continue
            stock, aud, var = _num(r.get("Stock Quantity")), _num(r.get("Audited Quantity")), _num(r.get("Variance"))
            if var != aud - stock:
                bad_var.append(f"{code}: {var:g} vs {aud:g}-{stock:g}")
            if items[code]["cost"] is not None and _num(r.get("Variance Value")) != var * items[code]["cost"]:
                bad_val.append(f"{code}: {r.get('Variance Value')} vs {var:g} x {items[code]['cost']:g}")
            if not _sign_ok(var, r.get("Variance Type", "")):
                bad_type.append(f"{code}: {var:g} -> {r.get('Variance Type')}")
        res.check(area, f"{option} view: variance = audited - stock", not bad_var, "; ".join(bad_var)[:150])
        res.check(area, f"{option} view: variance value = variance x cost price", not bad_val, "; ".join(bad_val)[:150])
        res.check(area, f"{option} view: variance type matches sign", not bad_type, "; ".join(bad_type)[:150])
        for metric, col in (("stock", "Stock Quantity"), ("audited", "Audited Quantity"), ("damaged", "Damaged Qty")):
            total = sum(_num(r.get(col)) for r in rows)
            res.check(area, f"{option} view: {metric} total = summary card", total == qty.get(metric),
                      f"table={total:g} card={qty.get(metric)}")

    item_rows = {r["Item Code"]: r for r in views.get("Item", [])}
    for code, item in items.items():
        r = item_rows.get(code)
        if r is None:
            res.check(area, f"Item view: {code} listed", False, "row missing")
            continue
        res.check(area, f"Item view: {code} stock / audited / damaged = run data",
                  (_num(r.get("Stock Quantity")), _num(r.get("Audited Quantity")), _num(r.get("Damaged Qty")))
                  == (item["stock"], item["counted"] or 0, item["damaged"] or 0),
                  f"page={r.get('Stock Quantity')}/{r.get('Audited Quantity')}/{r.get('Damaged Qty')} "
                  f"run={item['stock']:g}/{item['counted'] or 0:g}/{item['damaged'] or 0:g}")
    if "Location" in views:
        for code in items:
            loc_rows = [r for r in views["Location"] if r["Item Code"] == code]
            r = item_rows.get(code, {})
            sums = tuple(sum(_num(x.get(c)) for x in loc_rows) for c in ("Stock Quantity", "Audited Quantity"))
            res.check(area, f"Location view: {code} rows add up to Item view",
                      sums == (_num(r.get("Stock Quantity")), _num(r.get("Audited Quantity"))),
                      f"{len(loc_rows)} row(s) sum={sums} item view={r.get('Stock Quantity')}/{r.get('Audited Quantity')}")
        moved = [i for i in items.values() if i["count_loc"]]
        for item in moved:
            locs = {r.get("Audited Location") for r in views["Location"] if r["Item Code"] == item["code"]}
            res.check(area, f"Location view: {item['code']} shows counted location {item['count_loc']}",
                      any(item["count_loc"] in (l or "") for l in locs), str(sorted(l for l in locs if l)))

    # Value toggle: totals = sum(qty x cost price)
    toggle = summ.locator("div.summary-toggle")
    toggle.locator("button.toggle-btn", has_text="Value").click()
    page.wait_for_timeout(1200)
    value = _metrics(page)
    toggle.locator("button.toggle-btn", has_text="Qty").click()
    page.wait_for_timeout(800)
    for metric, key in (("stock", "stock"), ("audited", "counted"), ("damaged", "damaged")):
        if any(i[key] and i["cost"] is None for i in items.values()):
            continue                      # an item without a known cost price (excess item, no cost given)
        want = sum((i[key] or 0) * i["cost"] for i in items.values())
        res.check(area, f"Value card: {metric} = sum(qty x cost price)", value.get(metric) == want,
                  f"card={value.get(metric)} expected={want:g}")


# ======================================================
# EXCEL REPORT
# ======================================================
STEPS = {
    1: ["Navigate to Inventory > Item Groups.", "Click Add Item Group.",
        "Enter the group name and select inventory type {inventory_type}.", "Click Save and reopen the group."],
    2: ["Open the item group {group}.", "Click Import, upload the run workbook (sheet Items) and map the headers.",
        "Finish the import and open the item list / edit forms."],
    3: ["Navigate to Audits > Create Audit > Manual > Complete Audit (Dynamic).",
        "Select item group {group}, enter audit name {audit}, click Create Audit."],
    4: ["Open audit {audit} > Settings.", "Import the stock sheet (sheet Stock) and map Item Code / Stock Quantity.",
        "Save and check the Stock Sheet panel."],
    5: ["Open audit {audit} > Stock Audit.", "Count the items in sheet Counts (location, qty, damaged).",
        "Check the Recently audited list and Count summary."],
    6: ["Open audit {audit} > Audit Summary.", "Check the badges, cards and table.",
        "Change Summarize As and the Qty/Value toggle."],
    7: ["Open audit {audit} > Stock Audit > Finish audit.", "Choose a declaration note per discrepancy and Finish.",
        "Audit Summary > Complete Audit > answer the 3-step popup > Proceed to Resolution."],
    8: ["On Resolution, set Accept / Recount / Investigate per item and press Next.",
        "Do the Recount Audit, approve it, open the Resolution summary and the Adjustment report."],
    9: ["Resolution summary > Complete Audit.", "Check Audit History.",
        "Reports > Audit > Complete Count, item group {group}, Search."],
}
IMPACT = {
    1: "The stock audit cannot start without the item group.",
    2: "Items are missing or wrong, so the stock sheet and counts are wrong.",
    3: "No audit to count.",
    4: "Expected stock is wrong, so every variance is wrong.",
    5: "Counts are lost or recorded wrongly.",
    6: "The owner reviews wrong variances / values.",
    7: "The audit cannot move to resolution.",
    8: "Variances cannot be resolved correctly.",
    9: "The audit cannot be closed, or reports show wrong figures.",
}
FIX = {
    1: "Check group save validation, API response and saved values.",
    2: "Check import mapping, validation and saved item fields.",
    3: "Check audit creation for the selected group.",
    4: "Check stock sheet import, header mapping and save.",
    5: "Check count save and the counted / location values.",
    6: "Check the summary calculations (variance x cost price) and the Summarize As options.",
    7: "Check declaration save and the complete-audit flow.",
    8: "Check resolution actions, recount and adjustment calculations.",
    9: "Check completion rules and the Complete Count report query.",
}
CODE_RE = re.compile(r"\b(E2E\d{8}-\d{2}|[A-Z]{2,}\d[\w/-]*)\b")


def _severity(check, detail):
    text = f"{check} {detail}".lower()
    if check in ("Stage completed", "section ran") or "pending" in text or "accepted" in text and "complete" in text:
        return "Critical", "High"
    if any(k in text for k in ("value", "variance", "qty", "total", "count", "stock", "cost", "=")):
        return "Major", "Medium"
    return "Minor", "Low"


def bug_cards(runner, run, Config):
    groups = OrderedDict()
    for (area, check, ok, detail), (stage, shot) in zip(runner.res.rows, runner.meta):
        if ok:
            continue
        m = CODE_RE.search(check)
        key_check = CODE_RE.sub("{item}", check) if m else check
        g = groups.setdefault((stage, area, key_check), {"items": [], "details": [], "shot": shot})
        if m:
            g["items"].append(m.group(1))
        g["details"].append(detail)
    fmt = {"group": run["group"], "audit": run["audit"], "inventory_type": run["inventory_type"]}
    cards = []
    for n, ((stage, area, check), g) in enumerate(groups.items(), 1):
        severity, priority = _severity(check, " ".join(g["details"]))
        items = sorted(set(g["items"]))
        actual = "; ".join(d for d in g["details"] if d)[:900]
        cards.append(OrderedDict([
            ("Bug ID", f"SA-BUG-{n:03d}"), ("Module", "Stock Audit"), ("Sub Module", STAGES.get(stage, area)),
            ("Bug Title", f"{area}: {check.replace('{item}', 'item')}"[:150]),
            ("Environment", getattr(Config, "environments", "QA")), ("Severity", severity), ("Priority", priority),
            ("Preconditions", "1. User is logged in.\n2. User has audit owner / auditor permissions.\n"
                              f"3. Run data: {os.path.basename(run['workbook'])}"),
            ("Steps to Reproduce", "\n".join(f"{i}. {s.format(**fmt)}" for i, s in enumerate(STEPS.get(stage, []), 1))),
            ("Expected Result", f"{check.replace('{item}', 'each item')} — holds."),
            ("Actual Result", (f"Items: {', '.join(items)}. " if items else "") + actual),
            ("Reproducibility", "Always"), ("Status", "New"), ("Attachments", g["shot"] or ""),
            ("Impact", IMPACT.get(stage, "")), ("Suggested Fix", FIX.get(stage, "")),
        ]))
    return cards


def write_report(runner, run, Config):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    fills = {"PASS": "C6EFCE", "FAIL": "FFC7CE", "BLOCKED": "D9D9D9", "NOT RUN": "D9D9D9", "SKIPPED": "D9D9D9"}
    wb = Workbook()

    ws = wb.active
    ws.title = "Tracker"
    ws.append(["Stage", "Module", "Status", "Checks passed", "Checks failed", "Notes"])
    statuses = []
    for n, name in STAGES.items():
        rows = runner.stage_rows(n)
        status = runner.status(n)
        statuses.append(status)
        ws.append([n, name, status, sum(1 for r in rows if r[2]), sum(1 for r in rows if not r[2]), runner.note(n)])
        ws.cell(ws.max_row, 3).fill = PatternFill("solid", fgColor=fills[status])
    # stages after run["last_stage"] were not part of this run; skipped ones were not needed
    ran = [s for n, s in zip(STAGES, statuses) if n <= run["last_stage"] and s != "SKIPPED"]
    flow = "PASS" if ran and all(s == "PASS" for s in ran) else "FAIL"
    label = ("Audit flow (final stock + reports verified)" if run["last_stage"] >= 9
             else f"Audit flow up to stage {run['last_stage']}")
    ws.append(["", label, flow, "", "", f"group / audit: {run['group']} / {run['audit']}"])
    ws.cell(ws.max_row, 3).fill = PatternFill("solid", fgColor=fills[flow])
    if run.get("summary"):
        ok, path = run["summary"]
        ws.append(["", "Audit Summary page tests", "PASS" if ok else "FAIL", "", "", path])
        ws.cell(ws.max_row, 3).fill = PatternFill("solid", fgColor=fills["PASS" if ok else "FAIL"])

    wc = wb.create_sheet("Checks")
    wc.append(["Stage", "Area", "Check", "Result", "Detail"])
    for (area, check, ok, detail), (stage, _) in zip(runner.res.rows, runner.meta):
        wc.append([stage, area, check, "PASS" if ok else "FAIL", detail])
        wc.cell(wc.max_row, 4).fill = PatternFill("solid", fgColor=fills["PASS" if ok else "FAIL"])

    cards = bug_cards(runner, run, Config)
    wbug = wb.create_sheet("Bugs")
    wbug.append(list(cards[0].keys()) if cards else ["Bug ID", "Bug Title"])
    for card in cards:
        wbug.append(list(card.values()))

    for sheet in (ws, wc, wbug):
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for col in sheet.columns:
            width = max(len(str(c.value or "")) for c in col)
            sheet.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
            for c in col:
                c.alignment = Alignment(wrap_text=True, vertical="top")

    path = os.path.join(run["folder"], f"Stock_Audit_E2E_{run['name']}.xlsx")
    wb.save(path)

    print("\n" + "=" * 70 + f"\n  STOCK AUDIT E2E — {run['name']}\n" + "=" * 70)
    for (n, name), status in zip(STAGES.items(), statuses):
        print(f"  {n}. {name:<22} {status:<8} {runner.note(n)}")
    print(f"  {label}: {flow}   bugs: {len(cards)}   report: {path}")
    if run.get("summary"):
        print(f"  Audit Summary page tests: {'PASS' if run['summary'][0] else 'FAIL'}   report: {run['summary'][1]}")
    return flow == "PASS", path


# ======================================================
# ENTRY POINT
# ======================================================
def run_e2e_stock_audit(page, Config, existing_group=None, last_stage=9, summary_tests=False) -> bool:
    """existing_group: audit that group (no group / item creation, stages 1-2 skipped);
    last_stage: stop after it (6 = counted and summary checked, nothing finished);
    summary_tests: then run the Audit Summary page tests on the new audit."""
    from audit.e2e_complete_resolution import run_complete_resolution
    run = build_run(Config, existing_group)
    run["last_stage"] = last_stage
    print(f"\n🔷 STOCK AUDIT E2E: {run['name']}   group: {run['group']}   data: {run['workbook']}")
    runner = StageRunner(page, run["folder"])
    auditor = getattr(Config, "fc_auditor", None) or Config.Auditor2
    overrides = {
        # 1-2 item group + items
        "group_name": run["group"], "inventory_type": run["inventory_type"],
        "fields": [], "ids": [], "EXCEL_FILE": run["workbook"], "sheet_name": "Items",
        "run_add_item": False, "run_quick_add_items": False, "run_import_items": True,
        "run_details_validation": True,
        # 3-4 audit + stock sheet
        "ap_audit_name": run["audit"], "Group_Name": run["group"], "Audit_Type": "Complete Audit",
        "SD_audit_type": "Dynamic", "EXCEL_PATH": run["workbook"], "oa_sheet": "Stock",
        "oa_mapping": {"Item Code": "Item Code", "Stock Quantity": "Adjustmentqty"},
        "A_Checkboxes_BlindCount": False, "A_Checkboxes_geo": False, "A_Checkboxes_Audit_Damaged": True,
        "oa_photo_type": "None", "oa_sample_size": 0, "AUDIT_MAPPING_TYPE": "Random",
        "oa_Auditor1": auditor, "oa_Auditor2": auditor,
        # 5-8 counting + resolution
        "EXCEL_SHEET_auditor_1": "Counts", "EXCEL_LOCATION_COL1": "locations", "EXCEL_CODE_COL1": "code",
        "EXCEL_AUDITED_COL1": "audited", "EXCEL_DAMAGED_COL1": "damaged", "run_new_add_item": False,
        "run_asv2_checks": True, "asv2_results": runner.res, "EXCEL_SHEET_finish_flow": "finish_flow",
        # an existing group's items: a count saved with no location chosen goes to the item's own location
        "asv2_item_locations": {i["code"]: i["location"] for i in run["items"] if i["location"]}
                               if existing_group else None,
    }
    saved = {k: getattr(Config, k, None) for k in overrides}
    try:
        for k, v in overrides.items():
            setattr(Config, k, v)
        res = runner.res
        if existing_group:
            runner.skip(1, f"existing group {existing_group}")
            runner.skip(2, f"items of {existing_group} (sheet Data)")
        else:
            runner.run(1, stage_create_group, page, Config, run, res)
            runner.run(2, stage_import_items, page, Config, run, res, needs=(1,))
        runner.run(3, stage_create_audit, page, Config, run, res, needs=() if existing_group else (1,))
        runner.run(4, stage_import_stock_sheet, page, Config, run, res, needs=(3,) if existing_group else (2, 3))
        runner.run(5, stage_count, page, Config, run, res, needs=(4,))
        runner.run(6, stage_summary_views, page, Config, run, res, needs=(5,))
        if last_stage >= 7:
            run_complete_resolution(page, Config, run, runner)
        if summary_tests and 3 not in runner.errored and 3 not in runner.blocked:
            from audit.summary_page_tests import run_summary_page_tests
            known = {i["code"]: i["cost"] for i in run["items"] if i["cost"] is not None}
            ok = run_summary_page_tests(page, Config, folder=run["folder"], known_costs=known)
            run["summary"] = (ok, os.path.join(run["folder"], f"Summary_Page_Tests_{run['name']}.xlsx"))
    finally:
        for k, v in saved.items():
            setattr(Config, k, v)
    ok, _ = write_report(runner, run, Config)
    return ok and (run.get("summary") or (True,))[0]


def run_new_audit_summary(page, Config) -> bool:
    """Create an audit on Config.summary_group, import its stock sheet, count it, then run the Audit
    Summary page tests on it. Nothing is finished or completed."""
    return run_e2e_stock_audit(page, Config, existing_group=Config.summary_group, last_stage=6, summary_tests=True)
