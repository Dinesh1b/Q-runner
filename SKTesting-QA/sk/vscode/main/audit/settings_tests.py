"""
Audit Settings page — test cases (TC-SET-xx).

Runs on one existing test audit (Config.settings_audit_name) and restores its settings
and stock sheet at the end. Groups:
  A  Configuration fields save and reload
  B  Field validation (invalid values must not be saved)
  C  Stock sheet import (reset, mapping, not-found prompt, validation filters, save)
  D  Settings take effect on the Stock Audit screen

Writes Settings_Tests_<run>.xlsx (Test Cases + Bugs) under Config.e2e_output_dir.
"""
import os
import re
from collections import OrderedDict
from datetime import datetime

import pandas as pd

from audit.Auditor_1 import ASV2_ADD_COUNT_BTN, ASV2_AUDITED_QTY, ASV2_DAMAGED_QTY, ASV2_ITEM_LOADED, ASV2_ITEM_SEARCH
from audit.finish_complete_flow import _close_guide, _open_audit
from audit.stock_audit_checks import _clean, _num

DAYS     = "app-layout input[formcontrolname='autoCompletionDays']"
AUDITORS = "app-layout p-multiselect[formcontrolname='auditor']"
MAPPING  = "app-layout p-dropdown[formcontrolname='auditMappingType']"
PHOTO    = "app-layout p-dropdown[formcontrolname='selectedValidationType']"
SAMPLE   = "app-layout input[formcontrolname='validationSize']"
UPDATE   = "app-layout button:has-text('Update')"
TOGGLES  = OrderedDict([
    ("restrictSameItemCount", "Restrict auditors counting same item"),
    ("IsDamageQty", "Allow damaged quantity"),
    ("enableBlindCount", "Blind count"),
    ("isGeoLocation", "Geo-tagging"),
])
MESSAGES = ".p-toast-message, .swal2-popup:visible, [role=alert]"


# ======================================================
# PAGE HELPERS
# ======================================================
def _settings_view(page):
    """Settings and Audit Import share one route; make sure the settings form is shown."""
    try:
        page.locator(DAYS).wait_for(state="visible", timeout=15000)
    except Exception:
        page.locator("a", has_text="Audit Settings").first.click()
        page.locator(DAYS).wait_for(state="visible", timeout=30000)


def open_settings(page, Config):
    _open_audit(page, Config, "Settings")
    _settings_view(page)
    page.wait_for_timeout(1500)
    _close_guide(page)


def reload_settings(page):
    page.reload()
    _settings_view(page)
    page.wait_for_timeout(2000)
    _close_guide(page)


def _pick(page, dropdown, text):
    option = page.locator(".p-dropdown-panel:visible li", has_text=re.compile(rf"^\s*{re.escape(text)}\s*$")).first
    for attempt in range(2):                      # the settings panel scrolls inside itself
        page.locator(dropdown).scroll_into_view_if_needed()
        page.locator(dropdown).click()
        try:
            option.wait_for(state="visible", timeout=5000)
            option.click()
            break
        except Exception:
            page.keyboard.press("Escape")
            if attempt:
                raise
    page.wait_for_timeout(500)


def read_auditors(page):
    page.locator(AUDITORS).click()
    panel = page.locator(".p-multiselect-panel:visible").last
    panel.wait_for(state="visible", timeout=5000)
    chosen = [_clean(li.inner_text()) for li in panel.locator("li.p-multiselect-item").all()
              if "p-highlight" in (li.get_attribute("class") or "") or li.get_attribute("aria-selected") == "true"]
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    return sorted(chosen)


def set_auditors(page, names):
    page.locator(AUDITORS).click()
    panel = page.locator(".p-multiselect-panel:visible").last
    panel.wait_for(state="visible", timeout=5000)
    for li in panel.locator("li.p-multiselect-item").all():
        selected = "p-highlight" in (li.get_attribute("class") or "") or li.get_attribute("aria-selected") == "true"
        if selected != (_clean(li.inner_text()) in names):
            li.click()
            page.wait_for_timeout(250)
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)


def read_state(page):
    state = {
        "days": page.locator(DAYS).input_value(),
        "auditors": read_auditors(page),
        "mapping": _clean(page.locator(MAPPING).inner_text()),
        "photo": _clean(page.locator(PHOTO).inner_text()),
        "sample": page.locator(SAMPLE).input_value() if page.locator(SAMPLE).count() else None,
    }
    for fc in TOGGLES:
        state[fc] = page.locator(f"app-layout input[formcontrolname='{fc}']").is_checked()
    return state


def set_toggle(page, fc, on) -> bool:
    """Returns False when the toggle can't be changed (some depend on other settings)."""
    box = page.locator(f"app-layout input[formcontrolname='{fc}']")
    if box.is_checked() == on:
        return True
    if box.is_disabled():
        return False
    try:
        box.check(force=True, timeout=3000) if on else box.uncheck(force=True, timeout=3000)
    except Exception:
        box.locator("xpath=ancestor::label[1]").click()       # the switch's label
    page.wait_for_timeout(300)
    return box.is_checked() == on


def apply_state(page, state):
    page.locator(DAYS).fill(str(state["days"]))
    set_auditors(page, state["auditors"])        # first: some toggles depend on the auditors
    for fc in ("IsDamageQty", *[f for f in TOGGLES if f != "IsDamageQty"]):   # Damaged photo option needs damaged qty
        if not set_toggle(page, fc, state[fc]):
            print(f"   ⚠️ could not set {fc} to {state[fc]}")
    if _clean(page.locator(PHOTO).inner_text()) != state["photo"]:
        _pick(page, PHOTO, state["photo"])
    if state["photo"] == "Random" and state.get("sample") is not None and page.locator(SAMPLE).count():
        page.locator(SAMPLE).fill(str(state["sample"]))
    if _clean(page.locator(MAPPING).inner_text()) != state["mapping"]:
        _pick(page, MAPPING, state["mapping"])


def save(page):
    """Click Update; return the messages shown (toasts, popups, alerts)."""
    button = page.locator(UPDATE)
    if not button.is_enabled():
        return ["(Update disabled)"]
    button.click()
    seen = []
    for _ in range(8):
        page.wait_for_timeout(500)
        for t in page.locator(MESSAGES).all_inner_texts():
            t = _clean(t)
            if t and t not in seen:
                seen.append(t)
    ok = page.locator(".swal2-popup:visible button.swal2-confirm:visible")
    if ok.count():
        ok.first.click()
    return seen


def _saved_ok(messages):
    return any(re.search(r"updat|success|saved", m, re.I) for m in messages) and not any(
        re.search(r"error|invalid|required|must|cannot|not allowed|please", m, re.I) for m in messages)


# ---- stock sheet import
def open_import(page):
    if page.locator("app-layout button", has_text="Reset Report").count():   # already on Audit Import
        return
    page.locator("app-layout button", has_text="Import stock sheet").click()
    page.locator("app-layout button", has_text="Reset Report").wait_for(state="visible", timeout=20000)
    page.wait_for_timeout(1500)


def reset_report(page, confirm=True):
    page.locator("app-layout button", has_text="Reset Report").click()
    dialog = page.locator(".p-dialog:visible", has=page.locator("button", has_text="Cancel")).last
    dialog.wait_for(state="visible", timeout=8000)
    text = _clean(dialog.inner_text())
    dialog.locator("button", has_text="Reset" if confirm else "Cancel").last.click()
    page.wait_for_timeout(3000)
    return text


def upload(page, path, sheet):
    page.set_input_files("input#formFileSm", path)
    page.wait_for_timeout(3000)
    messages = [_clean(t) for t in page.locator(MESSAGES).all_inner_texts() if _clean(t)]
    chooser = page.locator("p-dropdown[placeholder='Choose Sheet'], p-dropdown[ng-reflect-placeholder='Choose Sheet']")
    if chooser.count() and chooser.first.is_visible():
        chooser.first.click()
        page.locator(".p-dropdown-panel:visible li", has_text=sheet).first.click()
        page.wait_for_timeout(2500)
    mapping = page.locator(".p-dialog:visible", has_text="Header Mapping").last
    return (mapping if mapping.count() else None), messages


def map_and_process(page, mapping, not_found_answer="Yes"):
    """Map (headers auto-match by name); answer the not-found prompt; wait for processing."""
    mapping.locator("button", has_text="Map").click()
    prompts = []
    for k in range(40):
        page.wait_for_timeout(1500)
        popup = page.locator(".swal2-popup:visible")
        if popup.count() == 0:
            if k > 3:
                break
            continue
        text = _clean(popup.last.inner_text())
        if "not found" in text.lower() and text not in prompts:
            prompts.append(text)
            if not_found_answer == "Yes":
                popup.last.locator("button.swal2-confirm").click()
            else:
                popup.last.locator("button.swal2-deny:visible, button.swal2-cancel:visible").first.click()
            continue
        ok = popup.last.locator("button.swal2-confirm:visible")
        if ok.count() and ok.first.is_enabled() and ("Completed" in text or "Processing" not in text):
            ok.first.click()
    page.wait_for_timeout(1500)
    return prompts


def import_filters(page):
    out = {}
    for t in page.locator("app-layout button:visible").filter(has_text=re.compile(r"\(\d+\)")).all_inner_texts():
        m = re.match(r"\s*(.+?)\s*\((\d+)\)", t)
        if m:
            out[m.group(1).strip()] = int(m.group(2))
    return out


def import_rows(page):
    return [[_clean(c) for c in r.locator("td").all_inner_texts()] for r in page.locator("app-layout table tbody tr").all()]


def stock_panel(page):
    text = _clean(page.locator("app-layout").first.inner_text())
    m = re.search(r"Line items (\d+) Stock qty (\d+)", text)
    src = re.search(r"Stock Source (.+?) Status", text)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None), (src.group(1) if src else "")


def import_good_sheet(page, Config):
    """Reset if needed, import Config.EXCEL_PATH / Data and Save (the audit's normal stock sheet)."""
    open_import(page)
    if import_rows(page):
        reset_report(page, True)
    mapping, _ = upload(page, Config.EXCEL_PATH, "Data")
    map_and_process(page, mapping, "Yes")
    page.locator("app-layout button:visible", has_text="Save").first.click()
    for _ in range(20):
        page.wait_for_timeout(1500)
        ok = page.locator(".swal2-popup:visible button.swal2-confirm:visible")
        if ok.count() and ok.first.is_enabled():
            ok.first.click()
            break


# ======================================================
# TEST CASE RUNNER
# ======================================================
class SettingsRun:
    def __init__(self, page, folder):
        self.page, self.folder = page, folder
        self.cases = []

    after = None    # run after every case (puts the original settings back)

    def case(self, tc_id, group, title, steps, expected, fn, *args):
        self._case(tc_id, group, title, steps, expected, fn, *args)
        if self.after:
            try:
                self.after()
            except Exception as e:
                print(f"   ⚠️ could not put the settings back after {tc_id}: {str(e).splitlines()[0]}")

    def _case(self, tc_id, group, title, steps, expected, fn, *args):
        print(f"\n▶ {tc_id} {title}")
        status, actual, shot = "FAIL", "", None
        try:
            outcome = fn(*args)
            if isinstance(outcome, tuple):
                ok, actual = outcome
                status = "PASS" if ok else "FAIL"
            else:
                status, actual = outcome["status"], outcome.get("actual", "")
        except Exception as e:
            actual = f"error: {str(e).splitlines()[0][:200]}"
        if status == "FAIL":
            shot = os.path.join(self.folder, f"{tc_id}.png")
            try:
                self.page.screenshot(path=shot, full_page=True)
            except Exception:
                shot = None
        print(f"   {status}  {actual}")
        self.cases.append(OrderedDict([
            ("Test Case ID", tc_id), ("Group", group), ("Title", title),
            ("Steps", "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))), ("Expected Result", expected),
            ("Actual Result", actual), ("Status", status), ("Attachment", shot or ""),
        ]))


# ======================================================
# A — CONFIGURATION FIELDS
# ======================================================
def tc_page_loads(page, Config):
    open_settings(page, Config)
    title = _clean(page.locator("app-layout h1").first.inner_text())
    present = {name: page.locator(sel).count() > 0 for name, sel in (
        ("auto-completion", DAYS), ("auditors", AUDITORS), ("item mapping", MAPPING), ("photo validation", PHOTO),
        ("update", UPDATE), ("import", "app-layout button:has-text('Import stock sheet')"))}
    present.update({label: page.locator(f"app-layout input[formcontrolname='{fc}']").count() > 0 for fc, label in TOGGLES.items()})
    missing = [k for k, v in present.items() if not v]
    return title == Config.ap_audit_name and not missing, f"title={title!r} missing={missing}"


def tc_update_disabled(page, Config):
    reload_settings(page)
    return not page.locator(UPDATE).is_enabled(), f"Update enabled={page.locator(UPDATE).is_enabled()} on a fresh load"


def tc_field_saves(page, field, change, expect):
    """Change one field, Update, reload, read it back."""
    reload_settings(page)
    change()
    messages = save(page)
    reload_settings(page)
    value = read_state(page)[field] if field != "photo+sample" else (read_state(page)["photo"], read_state(page)["sample"])
    errors = [m for m in messages if re.search(r"error|could not|invalid|required|please", m, re.I)]
    return value == expect and not errors, f"saved={value!r} expected={expect!r} messages={messages}"


def tc_mapping(page, option, panel_text):
    reload_settings(page)
    _pick(page, MAPPING, option)
    panel = panel_text in _clean(page.locator("app-layout").first.inner_text())
    messages = save(page)
    reload_settings(page)
    saved = _clean(page.locator(MAPPING).inner_text())
    return saved == option and panel, f"saved={saved!r} '{panel_text}' shown={panel} messages={messages}"


def tc_cross_auditor(page):
    text = _clean(page.locator("app-layout").first.inner_text())
    m = re.search(r"Cross-auditor\s+info\s+(\S+(?: \S+)?)", text)
    shown = m.group(1) if m else ""
    return bool(shown), f"Cross-auditor shows {shown!r} (set from the audit plan's cross-check settings)"


# ======================================================
# B — VALIDATION (invalid values must not be saved)
# ======================================================
def tc_rejected(page, field, change, describe):
    reload_settings(page)
    pick = (lambda s: (s["photo"], s["sample"])) if field == "photo+sample" else (lambda s: s[field])
    before = pick(read_state(page))
    change()
    messages = save(page)
    reload_settings(page)
    after = pick(read_state(page))
    raw = [m for m in messages if re.search(r"JSON|System\.|Path: \$", m)]
    return after == before and not raw, (f"{describe}: messages={messages} saved value {before!r} -> {after!r}"
                                         + (" (raw server error shown to the user)" if raw else ""))


def tc_refused_with(page, change, text):
    """The change must be refused with a message containing text."""
    reload_settings(page)
    before = read_state(page)["mapping"]
    change()
    messages = save(page)
    reload_settings(page)
    after = read_state(page)["mapping"]
    return after == before and any(text.lower() in m.lower() for m in messages), \
        f"messages={messages} mapping {before!r} -> {after!r}"


def tc_damaged_option(page):
    """'Damaged' photo validation is offered only when damaged quantity is allowed."""
    reload_settings(page)
    seen = {}
    for on in (False, True):
        set_toggle(page, "IsDamageQty", on)
        page.locator(PHOTO).click()
        seen[on] = [_clean(t) for t in page.locator(".p-dropdown-panel:visible li").all_inner_texts()]
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    return "Damaged" not in seen[False] and "Damaged" in seen[True], \
        f"damaged off: {seen[False]} | damaged on: {seen[True]}"


# ======================================================
# C — STOCK SHEET IMPORT
# ======================================================
def tc_sample(page):
    reload_settings(page)
    open_import(page)
    with page.expect_download(timeout=15000) as info:
        page.locator("app-layout button, app-layout a", has_text="Sample").first.click()
    name = info.value.suggested_filename
    return name.lower().endswith((".xlsx", ".xls", ".csv")), f"downloaded {name!r}"


def tc_upload_needs_reset(page, Config, bad_file):
    reload_settings(page)
    open_import(page)
    if not import_rows(page):
        return {"status": "NOT RUN", "actual": "no stock sheet loaded, nothing to protect"}
    mapping, messages = upload(page, bad_file, "Data")
    blocked = mapping is None and any("reset" in m.lower() for m in messages)
    if mapping is not None:
        mapping.locator("button", has_text="Back").click()
    return blocked, f"messages={messages} mapping opened={mapping is not None}"


def tc_reset_cancel(page):
    reload_settings(page)
    open_import(page)
    before = len(import_rows(page))
    text = reset_report(page, confirm=False)
    after = len(import_rows(page))
    return after == before and "reset" in text.lower(), f"dialog={text!r} rows {before} -> {after}"


def tc_reset_confirm(page):
    reload_settings(page)
    open_import(page)
    before = len(import_rows(page))
    text = reset_report(page, confirm=True)
    after = len(import_rows(page))
    return after == 0, f"dialog={text!r} rows {before} -> {after}"


def tc_not_found_no(page, bad_file):
    mapping, _ = upload(page, bad_file, "Data")
    if mapping is None:
        return False, "mapping dialog did not open"
    prompts = map_and_process(page, mapping, "No")
    counts = import_filters(page)
    return bool(prompts) and counts.get("All", 0) == 0, f"prompt={prompts[:1]} filters={counts}"


def tc_not_found_yes(page, bad_file, st):
    reload_settings(page)
    open_import(page)
    if import_rows(page):          # the previous upload is still loaded (No does not clear it)
        reset_report(page, True)
    mapping, _ = upload(page, bad_file, "Data")
    if mapping is None:
        mapping = page.locator(".p-dialog:visible", has_text="Header Mapping").last
    prompts = map_and_process(page, mapping, "Yes")
    st["filters"], st["rows"] = import_filters(page), import_rows(page)
    # Yes then opens "Import Transaction" to create the missing items in inventory;
    # close it without mapping so no inventory item is created
    transaction = page.locator(".p-dialog:visible", has_text="Import Transaction").last
    opened = False
    for _ in range(10):
        if transaction.count() and transaction.is_visible():
            opened = True
            break
        page.wait_for_timeout(500)
    if opened:
        inner = page.locator(".p-dialog:visible", has_text="Header Mapping")
        if inner.count() > 1:
            inner.last.locator("button", has_text="Back").click()
            page.wait_for_timeout(800)
        transaction.locator(".p-dialog-header-close, .p-dialog-header-icon, button:has-text('×')").first.click()
        page.wait_for_timeout(1500)
    return bool(prompts) and st["filters"].get("All", 0) > 0 and opened, \
        f"prompt={prompts[:1]} filters={st['filters']} import-transaction dialog opened={opened} (closed, no item created)"


def tc_filter_counts(st, expect):
    got = {k: st.get("filters", {}).get(k) for k in expect}
    return got == expect, f"filters={st.get('filters')} expected={expect}"


def tc_row_statuses(st):
    rows = {r[1]: r for r in st.get("rows", []) if len(r) >= 5}
    checks = {
        "ITM0002 merged 20": rows.get("ITM0002", [""] * 5)[3] == "20" and "merged" in rows.get("ITM0002", [""] * 5)[4].lower(),
        "ITM0003 empty qty": "empty" in rows.get("ITM0003", [""] * 5)[4].lower(),
        "NOPE9999 not found": "not found" in rows.get("NOPE9999", [""] * 5)[4].lower(),
        "ITM0001 verified": rows.get("ITM0001", [""] * 5)[4] == "Verified",
    }
    return all(checks.values()), f"{checks} rows={[r[1:] for r in rows.values()]}"


def tc_filter_buttons(page, st):
    bad = []
    for name, count in st.get("filters", {}).items():
        page.locator("app-layout button:visible").filter(has_text=re.compile(rf"^\s*{re.escape(name)}\s*\(")).first.click()
        page.wait_for_timeout(1200)
        n = len([r for r in import_rows(page) if len(r) >= 5])
        if n != count:
            bad.append(f"{name}: {n} rows vs {count}")
    page.locator("app-layout button:visible").filter(has_text=re.compile(r"^\s*All\s*\(")).first.click()
    return not bad, "; ".join(bad) or "each filter shows its count of rows"


def tc_download_error(page):
    button = page.locator("app-layout button:visible", has_text="Download Error")
    if not button.count():
        return False, "no Download Error button"
    with page.expect_download(timeout=15000) as info:
        button.first.click()
    return True, f"downloaded {info.value.suggested_filename!r}"


def tc_import_save(page, Config):
    open_settings(page, Config)
    import_good_sheet(page, Config)
    open_settings(page, Config)
    (lines, qty), source = stock_panel(page)
    want = pd.read_excel(Config.EXCEL_PATH, sheet_name="Data")
    return (lines, qty) == (len(want), int(want["Adjustmentqty"].sum())), \
        f"panel lines={lines} qty={qty} source={source!r} sheet={len(want)}/{int(want['Adjustmentqty'].sum())}"


# ======================================================
# D — SETTINGS TAKE EFFECT ON THE STOCK AUDIT SCREEN
# ======================================================
def _stock_screen(page, Config):
    _open_audit(page, Config, "Stock Audit")
    page.wait_for_selector("app-audit-stock-v2 form.asv2-form", timeout=30000)
    page.wait_for_timeout(2000)
    _close_guide(page)


def tc_blind_count(page, Config):
    open_settings(page, Config)
    set_toggle(page, "enableBlindCount", True)
    save(page)
    _stock_screen(page, Config)
    headers = [_clean(h).upper() for h in page.locator("app-audit-stock-list-v2 thead th").all_inner_texts()]
    return "STOCK QTY" not in headers, f"list headers={headers}"


def tc_damaged_off(page, Config):
    open_settings(page, Config)
    set_toggle(page, "IsDamageQty", False)
    save(page)
    _stock_screen(page, Config)
    shown = page.locator(ASV2_DAMAGED_QTY).count() > 0 and page.locator(ASV2_DAMAGED_QTY).first.is_visible()
    return not shown, f"damaged qty field shown={shown}"


def tc_photo_required(page, Config):
    open_settings(page, Config)
    _pick(page, PHOTO, "Random")
    if page.locator(SAMPLE).count():
        page.locator(SAMPLE).fill("10")
    save(page)
    _stock_screen(page, Config)
    before = _clean(page.locator("app-audit-stock-list-v2 span.aslv2-count-pill").inner_text())
    search = page.locator(ASV2_ITEM_SEARCH).first
    search.click()
    search.type("ITM0001", delay=50)
    page.locator("li.p-autocomplete-item:visible").first.click()
    page.wait_for_selector(ASV2_ITEM_LOADED, timeout=8000)
    page.fill(ASV2_AUDITED_QTY, "1")
    page.locator(ASV2_ADD_COUNT_BTN).click()
    messages = []
    for _ in range(8):
        page.wait_for_timeout(500)
        messages += [_clean(t) for t in page.locator(MESSAGES).all_inner_texts() if _clean(t) not in messages]
    for b in page.locator(".swal2-popup:visible button.swal2-confirm, .swal2-popup:visible button.swal2-cancel").all()[:1]:
        b.click()
    page.locator("app-audit-stock-list-v2 button[aria-label='Refresh']").click()
    page.wait_for_timeout(2000)
    after = _clean(page.locator("app-audit-stock-list-v2 span.aslv2-count-pill").inner_text())
    saved = after != before
    if saved:   # undo the count this test created
        row = page.locator("app-audit-stock-list-v2 tbody tr", has_text="ITM0001").first
        row.locator("button[aria-label='Delete']").click()
        confirm = page.locator(".p-confirm-dialog:visible button.p-confirm-dialog-accept, .swal2-popup:visible button.swal2-confirm")
        confirm.first.wait_for(state="visible", timeout=5000)
        confirm.first.click()
        page.wait_for_timeout(2000)
    return not saved and any("photo" in m.lower() for m in messages), \
        f"messages={messages} entries {before} -> {after}" + (" (count saved without a photo, then deleted)" if saved else "")


# ======================================================
# REPORT
# ======================================================
def write_report(run, folder, audit_name, Config):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    fills = {"PASS": "C6EFCE", "FAIL": "FFC7CE", "NOT RUN": "D9D9D9", "BLOCKED": "D9D9D9", "MANUAL": "FFEB9C"}
    wb = Workbook()
    ws = wb.active
    ws.title = "Test Cases"
    ws.append(list(run.cases[0].keys()))
    for c in run.cases:
        ws.append(list(c.values()))
        ws.cell(ws.max_row, 7).fill = PatternFill("solid", fgColor=fills.get(c["Status"], "FFFFFF"))
    wb_bugs = wb.create_sheet("Bugs")
    fails = [c for c in run.cases if c["Status"] == "FAIL"]
    cols = ["Bug ID", "Module", "Sub Module", "Bug Title", "Environment", "Severity", "Priority", "Preconditions",
            "Steps to Reproduce", "Expected Result", "Actual Result", "Reproducibility", "Status", "Attachments",
            "Impact", "Suggested Fix"]
    wb_bugs.append(cols)
    for n, c in enumerate(fails, 1):
        severity = ("Major", "Medium") if c["Group"].startswith(("B", "C", "D")) else ("Minor", "Low")
        if c["Actual Result"].startswith("error:"):
            severity = ("Critical", "High")
        wb_bugs.append([
            f"SA-BUG-{n:03d}", "Stock Audit", f"Audit Settings — {c['Group']}", f"{c['Test Case ID']}: {c['Title']}",
            getattr(Config, "environments", "QA"), severity[0], severity[1],
            f"1. User is logged in as the audit owner.\n2. Audit {audit_name} exists with a stock sheet.",
            c["Steps"], c["Expected Result"], c["Actual Result"], "Always", "New", c["Attachment"],
            "Audit settings can be saved wrong or not applied to counting.",
            "Check the settings validation, save API and how the setting is applied.",
        ])
    for sheet in (ws, wb_bugs):
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width = min(max(10, max(len(str(c.value or "")) for c in col) + 2), 60)
            for c in col:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    path = os.path.join(folder, f"Settings_Tests_{os.path.basename(folder)}.xlsx")
    wb.save(path)
    counts = {s: sum(1 for c in run.cases if c["Status"] == s) for s in ("PASS", "FAIL", "NOT RUN", "BLOCKED", "MANUAL")}
    print("\n" + "=" * 70 + f"\n  AUDIT SETTINGS TESTS — {audit_name}\n" + "=" * 70)
    for c in run.cases:
        print(f"  {c['Test Case ID']:<11} {c['Status']:<8} {c['Title']}")
    print(f"  {counts}   bugs: {len(fails)}   report: {path}")
    return counts["FAIL"] == 0, path


# ======================================================
# ENTRY POINT
# ======================================================
def run_settings_tests(page, Config) -> bool:
    audit = Config.settings_audit_name
    folder = os.path.join(Config.e2e_output_dir, f"Settings_{datetime.now():%m%d_%H%M}")
    os.makedirs(folder, exist_ok=True)
    bad_file = os.path.join(folder, "stock_bad.xlsx")
    pd.DataFrame({"Item Code": ["ITM0001", "ITM0002", "ITM0002", "ITM0003", "NOPE9999"],
                  "Location": ["SA-A1-B1-L1", "SA-A1-B1-L2", "SA-A1-B1-L2", "SA-A2-B3-L3", "SA-A1-B1-L1"],
                  "Adjustmentqty": [10, 10, 10, "abc", 5]}).to_excel(bad_file, sheet_name="Data", index=False)

    saved_name = Config.ap_audit_name
    Config.ap_audit_name = audit
    run = SettingsRun(page, folder)
    original = None
    st = {}
    other = getattr(Config, "settings_second_auditor", "Dinesh")
    try:
        # ---------------- A
        run.case("TC-SET-01", "A Configuration", "Settings page loads with all controls",
                 [f"Open audit {audit} > Settings."], "Title is the audit name; every control is shown.",
                 tc_page_loads, page, Config)
        original = read_state(page)
        print(f"   original settings: {original}")
        run.after = lambda: (reload_settings(page), apply_state(page, original), save(page))
        run.case("TC-SET-02", "A Configuration", "Update disabled until something changes",
                 ["Open Settings.", "Change nothing."], "Update button is disabled.", tc_update_disabled, page, Config)
        days = "7" if original["days"] != "7" else "8"
        run.case("TC-SET-03", "A Configuration", f"Auto-completion window saves ({days} days)",
                 [f"Set Auto-completion window to {days}.", "Click Update.", "Reload Settings."],
                 f"Value {days} is saved and shown after reload.",
                 tc_field_saves, page, "days", lambda: page.locator(DAYS).fill(days), days)
        both = sorted(set(original["auditors"]) | {other})
        run.case("TC-SET-04", "A Configuration", f"Add auditor {other}",
                 [f"Select auditor {other} in Auditors.", "Click Update.", "Reload Settings."],
                 f"Auditors {both} are saved.", tc_field_saves, page, "auditors", lambda: set_auditors(page, both), both)
        run.case("TC-SET-05", "A Configuration", f"Remove auditor {other}",
                 [f"Deselect auditor {other}.", "Click Update.", "Reload Settings."],
                 f"Auditors {original['auditors']} are saved.",
                 tc_field_saves, page, "auditors", lambda: set_auditors(page, original["auditors"]), original["auditors"])
        for i, (fc, label) in enumerate(TOGGLES.items(), 6):
            want = not original[fc]
            run.case(f"TC-SET-{i:02d}", "A Configuration", f"{label} toggle saves ({'on' if want else 'off'})",
                     [f"Turn {label} {'on' if want else 'off'}.", "Click Update.", "Reload Settings."],
                     f"{label} is {'on' if want else 'off'} after reload.",
                     tc_field_saves, page, fc, lambda fc=fc, want=want: set_toggle(page, fc, want), want)
        run.case("TC-SET-10", "A Configuration", "Photo validation Random with sample size 5 saves",
                 ["Choose Photo validation Random.", "Enter sample size 5.", "Click Update.", "Reload Settings."],
                 "Random with sample size 5 is saved.",
                 tc_field_saves, page, "photo+sample",
                 lambda: (_pick(page, PHOTO, "Random"), page.locator(SAMPLE).fill("5")), ("Random", "5"))
        run.case("TC-SET-11", "A Configuration", "Photo validation Damaged saves",
                 ["Choose Photo validation Damaged.", "Click Update.", "Reload Settings."], "Damaged is saved.",
                 tc_field_saves, page, "photo", lambda: _pick(page, PHOTO, "Damaged"), "Damaged")
        run.case("TC-SET-12", "A Configuration", "Photo validation None saves",
                 ["Choose Photo validation None.", "Click Update.", "Reload Settings."], "None is saved.",
                 tc_field_saves, page, "photo", lambda: _pick(page, PHOTO, "None"), "None")
        run.case("TC-SET-13", "A Configuration", "Item mapping By Category needs a category per auditor",
                 ["Choose Item mapping By Category.", "Assign no categories.", "Click Update."],
                 "'Please assign categories to every auditor.' and the mapping is not changed.",
                 tc_refused_with, page, lambda: _pick(page, MAPPING, "By Category"), "assign categories")
        run.case("TC-SET-14", "A Configuration", "Item mapping By Location needs a location per auditor",
                 ["Choose Item mapping By Location.", "Assign no locations.", "Click Update."],
                 "'Please assign locations to every auditor.' and the mapping is not changed.",
                 tc_refused_with, page, lambda: _pick(page, MAPPING, "By Location"), "assign locations")
        run.case("TC-SET-15", "A Configuration", "Item mapping back to Random saves",
                 ["Choose Item mapping Random.", "Click Update.", "Reload."], "Random is saved.",
                 tc_mapping, page, "Random", "Item mapping")
        run.case("TC-SET-16", "A Configuration", "Cross-auditor value shown",
                 ["Open Settings.", "Read the Cross-auditor field."], "The cross-auditor (or 'Not Assigned') is shown.",
                 tc_cross_auditor, page)
        run.case("TC-SET-17", "A Configuration", "'Damaged' photo validation only when damaged qty is allowed",
                 ["Turn Allow damaged quantity off and open Photo validation.", "Turn it on and open Photo validation."],
                 "Off: None, Random. On: None, Random, Damaged.", tc_damaged_option, page)

        # ---------------- B
        for i, (value, why) in enumerate((("400", "above 365"), ("-1", "negative"), ("", "empty")), 21):
            run.case(f"TC-SET-{i}", "B Validation", f"Auto-completion window {why} is rejected ({value!r})",
                     [f"Enter {value!r} in Auto-completion window.", "Click Update.", "Reload Settings."],
                     "An error is shown and the previous value is kept.",
                     tc_rejected, page, "days", lambda value=value: page.locator(DAYS).fill(value), f"days={value!r}")
        run.case("TC-SET-24", "B Validation", "No auditor selected is rejected",
                 ["Deselect every auditor.", "Click Update.", "Reload Settings."],
                 "An error is shown (Auditors is required) and the auditors are kept.",
                 tc_rejected, page, "auditors", lambda: set_auditors(page, []), "no auditors")
        for i, (value, why) in enumerate((("", "empty"), ("0", "zero"), ("150", "more than the items")), 25):
            run.case(f"TC-SET-{i}", "B Validation", f"Random photo validation, sample size {why} is rejected",
                     ["Choose Photo validation Random.", f"Enter sample size {value!r}.", "Click Update.", "Reload Settings."],
                     "An error is shown and the previous photo validation is kept.",
                     tc_rejected, page, "photo+sample",
                     lambda value=value: (_pick(page, PHOTO, "Random"), page.locator(SAMPLE).fill(value)),
                     f"Random sample={value!r}")

        # ---------------- D (before C, which resets the stock sheet)
        run.after = None
        apply_and_save = lambda: (reload_settings(page), apply_state(page, original), save(page))
        apply_and_save()
        run.case("TC-SET-41", "D Effect on counting", "Blind count hides the stock quantity",
                 ["Turn Blind count on and Update.", "Open Stock Audit.", "Check the Recently audited columns."],
                 "No Stock Qty column is shown to the auditor.", tc_blind_count, page, Config)
        apply_and_save_from_stock = lambda: (open_settings(page, Config), apply_state(page, original), save(page))
        apply_and_save_from_stock()
        run.case("TC-SET-42", "D Effect on counting", "Damaged quantity off removes the damaged field",
                 ["Turn Allow damaged quantity off and Update.", "Open Stock Audit."],
                 "The Damaged qty field is not shown.", tc_damaged_off, page, Config)
        apply_and_save_from_stock()
        run.case("TC-SET-43", "D Effect on counting", "Photo validation requires a photo when counting",
                 ["Set Photo validation Random, sample size 10 (every item) and Update.", "Open Stock Audit.",
                  "Select ITM0001, enter 1, click Add count without a photo."],
                 "The count is refused until a photo is taken.", tc_photo_required, page, Config)
        apply_and_save_from_stock()
        run.cases.append(OrderedDict([
            ("Test Case ID", "TC-SET-44"), ("Group", "D Effect on counting"), ("Title", "Geo-tagging records the location"),
            ("Steps", "1. Turn Geo-tagging on.\n2. Count an item on a device with location allowed.\n3. Check Coordinates in Audit Summary."),
            ("Expected Result", "Coordinates are stored with the count."),
            ("Actual Result", "Needs a device with location permission"), ("Status", "MANUAL"), ("Attachment", "")]))
        run.cases.append(OrderedDict([
            ("Test Case ID", "TC-SET-45"), ("Group", "D Effect on counting"), ("Title", "Restrict auditors counting same item"),
            ("Steps", "1. Turn the restriction on.\n2. Auditor 1 counts ITM0001.\n3. Auditor 2 tries to count ITM0001."),
            ("Expected Result", "Auditor 2 is stopped from counting the same item."),
            ("Actual Result", "Auditor 2 login is rejected (Config.password2)"), ("Status", "BLOCKED"), ("Attachment", "")]))

        # ---------------- C
        run.case("TC-SET-31", "C Stock sheet import", "Sample template downloads",
                 ["Settings > Import stock sheet.", "Click Sample."], "An Excel template is downloaded.", tc_sample, page)
        run.case("TC-SET-32", "C Stock sheet import", "Upload is refused while a stock sheet is loaded",
                 ["Settings > Import stock sheet (a sheet is loaded).", "Choose a file without Reset Report."],
                 "'Please reset report and upload a file.' and no header mapping.",
                 tc_upload_needs_reset, page, Config, bad_file)
        run.case("TC-SET-33", "C Stock sheet import", "Reset Report — Cancel keeps the stock sheet",
                 ["Import stock sheet > Reset Report.", "Click Cancel."], "Confirmation shown; all rows kept.",
                 tc_reset_cancel, page)
        run.case("TC-SET-34", "C Stock sheet import", "Reset Report — Reset clears the stock sheet",
                 ["Import stock sheet > Reset Report.", "Click Reset."], "Every row is removed.", tc_reset_confirm, page)
        run.case("TC-SET-35", "C Stock sheet import", "Items not found — No cancels the import",
                 ["Upload a file with an unknown item code.", "Map.", "Answer No to 'items not found'."],
                 "The prompt is shown and nothing is imported.", tc_not_found_no, page, bad_file)
        run.case("TC-SET-36", "C Stock sheet import", "Items not found — Yes continues the import",
                 ["Upload the same file.", "Map.", "Answer Yes."], "The file is processed.",
                 tc_not_found_yes, page, bad_file, st)
        expect = {"All": 4, "Verified": 2, "Duplicates": 1, "Invalid Items": 1, "Items not found": 1}
        run.case("TC-SET-37", "C Stock sheet import", "Validation filter counts",
                 ["After the import, read All / Verified / Duplicates / Invalid Items / Items not found."],
                 f"Counts {expect} (5 rows: 1 duplicate merged, 1 bad qty, 1 unknown code).", tc_filter_counts, st, expect)
        run.case("TC-SET-38", "C Stock sheet import", "Row statuses (merged duplicate, empty qty, not found)",
                 ["Read the Status column."],
                 "ITM0002 merged to 20; ITM0003 'Stock quantity is empty'; NOPE9999 'Item not found'; ITM0001 Verified.",
                 tc_row_statuses, st)
        run.case("TC-SET-39", "C Stock sheet import", "Filter buttons narrow the table",
                 ["Click each filter."], "The table shows that filter's count of rows.", tc_filter_buttons, page, st)
        run.case("TC-SET-46", "C Stock sheet import", "Reset, import a valid sheet and Save",
                 ["Reset Report.", "Upload the valid sheet (Data), Map, Save.", "Open Settings."],
                 "Stock Sheet panel shows the sheet's line items and stock qty.", tc_import_save, page, Config)
    finally:
        try:      # always leave the audit as it was
            open_settings(page, Config)
            (lines, _), _ = stock_panel(page)
            if not lines or "stock sheet" not in stock_panel(page)[1].lower():
                import_good_sheet(page, Config)
                open_settings(page, Config)
            if original:
                apply_state(page, original)
                save(page)
                reload_settings(page)
                print(f"   restored settings: {read_state(page)}")
        except Exception as e:
            print(f"   ⚠️ restore failed: {e}")
        Config.ap_audit_name = saved_name
    ok, _ = write_report(run, folder, audit, Config)
    return ok
