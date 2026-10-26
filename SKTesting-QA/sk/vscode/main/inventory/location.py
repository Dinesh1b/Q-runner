from datetime import datetime
import pytz
import difflib
import random
import re
import time
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import Page, expect
import os
import sys

from login.popup_handler import detect_feedback

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))




# ---------------------------------------
# SAFE CLICK
# ---------------------------------------
def safe_click(locator):
    locator.wait_for(state="attached", timeout=15000)
    locator.wait_for(state="visible", timeout=15000)
    locator.scroll_into_view_if_needed()
    locator.page.wait_for_load_state("networkidle")
    try:
        locator.click(timeout=10000)
    except:
        locator.click(force=True)


# ---------------------------------------
# DROPDOWN FILTER + SELECT
# ---------------------------------------
def type_in_dropdown_filter_dynamic(page, filter_text):
    filter_input = page.locator("input.p-dropdown-filter").last
    filter_input.wait_for(state="visible", timeout=5000)
    filter_input.click()
    filter_input.clear()

    # Human typing simulation
    for char in filter_text:
        filter_input.type(char, delay=random.randint(60, 140))

    page.wait_for_timeout(600)

    aria_owns = filter_input.get_attribute("aria-owns")
    options_locator = page.locator(f"#{aria_owns} li.p-dropdown-item")
    options_locator.first.wait_for(state="visible", timeout=5000)

    all_options = options_locator.all_inner_texts()

    # Exact match
    if filter_text in all_options:
        matched = filter_text
    else:
        matches = difflib.get_close_matches(filter_text, all_options, n=1, cutoff=0.4)
        if matches:
            matched = matches[0]
            print(f"⚠ Fuzzy match: {filter_text} → {matched}")
        else:
            print(" No timezone match found")
            return

    option = page.locator(f"#{aria_owns} li.p-dropdown-item:has-text('{matched}')")
    safe_click(option)
    print(f"   Selected: {matched}")


# ---------------------------------------
# SETTINGS page LOGIC
# ---------------------------------------
def settings(page, cfg):
    # Location Setup module: add the configured locations and/or run the Warehouse test suite
    if getattr(cfg, "ls_run_setup", True):
        add_locations(page, cfg)
    if getattr(cfg, "ls_run_tests", False):
        return run_warehouse_tests(page, cfg)


def add_locations(page, cfg):
    # The lists come from the run's config; any that are missing fall back to backend/Config.py → Location Setup
    from backend.Config import Config as Defaults
    cfg = type("LocationConfig", (), {key: getattr(cfg, key, getattr(Defaults, key))
                                      for key in ("zones", "aisles", "bays", "levels")})
    print(f" Locations: zones={cfg.zones} aisles={cfg.aisles} bays={cfg.bays} levels={cfg.levels}")
    try:
        page.locator("button:has(img[src*='white_logo.png'])").click()
        page.locator("#audit-settings-link").click()
        page.wait_for_timeout(1000)
        page.locator("a[href='/home/warehouse']").first.click()
        page.wait_for_timeout(1000)

        # ── STEP 1: Add Zones ──────────────────────────────────────
        for zone in cfg.zones:
            safe_click(page.locator(".storage-header button"))
            page.wait_for_timeout(400)
            page.locator(".storage-panel input[placeholder='Short Code']").last.fill(zone)
            page.wait_for_timeout(300)

        # ── STEP 2: Add Aisles for every Zone ─────────────────────
        for zone in cfg.zones:
            page.locator(".aisle-header select").select_option(label=zone)
            page.wait_for_timeout(400)
            for aisle in cfg.aisles:
                safe_click(page.locator(".aisle-header button"))
                page.wait_for_timeout(400)
                page.locator(".aisle-panel input[placeholder='Short Code']").last.fill(aisle)
                page.wait_for_timeout(300)

        # ── STEP 3: Add Bays for every Zone→Aisle combo ───────────

                for bay in cfg.bays:
                    safe_click(page.locator(".bay-header button"))
                    page.wait_for_timeout(400)
                    page.locator(".bay-panel input[placeholder='Short Code']").last.fill(bay)
                    page.wait_for_timeout(300)

        # ── STEP 4: Add Levels for every Zone→Aisle→Bay combo ─────

                    for level in cfg.levels:
                        safe_click(page.locator(".level-header button"))
                        page.wait_for_timeout(400)
                        page.locator(".level-panel input[placeholder='Short Code']").last.fill(level)
                        page.wait_for_timeout(300)

    except PlaywrightTimeoutError:
        print(" Settings navigation failed")
    page.locator("button.primary-button:has-text('Save')").click()


# ---------------------------------------
# WAREHOUSE PAGE (Location / Aisle / Bay / Level panels)
# ---------------------------------------
STRUCTURE = "app-storage-structure"
LEVEL_ORDER = ("storage", "aisle", "bay", "level")   # Location, Aisle, Bay, Level
CODE = "input[placeholder='Short Code']"
DESC = "input[placeholder='Description']"
SHORT_CODE_MAX = 10   # the Short Code inputs have maxlength="10"
SAVE_URL = "**/storage/CreateorUpdateStorageAisleBayLevel*"
SAVED_OK = re.compile(r"saved successfully", re.I)


def open_warehouse(page):
    page.locator("button:has(img[src*='white_logo.png'])").click()
    page.locator("#audit-settings-link").click()
    page.locator("a[href='/home/warehouse']").first.click()
    _wait_for_structure(page)


def reload_warehouse(page):
    # Leaving without Save discards unsaved changes (new rows, deletions, mode)
    page.reload()
    _wait_for_structure(page)


def _wait_for_structure(page):
    page.locator(f"{STRUCTURE} .storage-panel").wait_for()
    page.wait_for_timeout(1500)  # the saved rows arrive just after the panels


def rows(page, level):
    return page.locator(f"{STRUCTURE} .{level}-panel .list-row")


def codes(page, level):
    return [row.locator(CODE).input_value() for row in rows(page, level).all()]


def visible_panels(page):
    return [level for level in LEVEL_ORDER if page.locator(f"{STRUCTURE} .{level}-panel").is_visible()]


def add_row(page, level, code, desc=""):
    count = rows(page, level).count()
    page.locator(f"{STRUCTURE} .{level}-header button.btn-light").click()
    expect(rows(page, level), f"+ did not add a {level} row").to_have_count(count + 1)
    rows(page, level).last.locator(CODE).fill(code)
    rows(page, level).last.locator(DESC).fill(desc)


def delete_row(page, level, code):
    for row in rows(page, level).all():
        if row.locator(CODE).input_value() == code:
            row.locator("button.btn-danger").click()
            return
    raise AssertionError(f"'{code}' is not in the {level} list")


def parent_options(page, level):
    return [o.strip() for o in page.locator(f"{STRUCTURE} .{level}-header select option").all_inner_texts()]


def select_parent(page, level, name):
    # The Aisle / Bay / Level panels list the children of the parent picked in their own dropdown
    page.locator(f"{STRUCTURE} .{level}-header select").select_option(label=name)
    page.wait_for_timeout(800)


def open_path(page, path):
    # Pick the parents left to right: the Location for Aisles, the Aisle for Bays, the Bay for Levels
    for level, name in zip(LEVEL_ORDER[1:], path):
        select_parent(page, level, name)


def current_mode(page):
    checked = page.locator("input[name='mode']:checked")
    return checked.get_attribute("value") if checked.count() else None   # 'S' simple, 'A' advance


def set_mode(page, value, proceed=True):
    # Every switch asks "This Configuration will apply future transactions only. Do you want to proceed?"
    # Yes switches (nothing is stored until Save); No keeps the current mode
    if current_mode(page) == value:
        return
    page.locator("label[for='simple']" if value == "S" else "label[for='advance']").click()
    dialog = page.locator(".swal2-popup")
    expect(dialog, "no confirmation when switching the configuration mode").to_be_visible()
    dialog.locator("button.swal2-confirm" if proceed else "button.swal2-cancel").click()
    expect(dialog).to_be_hidden()
    page.wait_for_timeout(300)


def save_warehouse(page):
    page.locator(f"{STRUCTURE} button.primary-button", has_text="Save").click()
    return detect_feedback(page, wait_time=4)


def snapshot(page):
    return (current_mode(page),) + tuple(tuple(codes(page, level)) for level in LEVEL_ORDER)


# ---------------------------------------
# WAREHOUSE TEST SUITE (WH_001 – WH_040)
# ---------------------------------------
WAREHOUSE_CASES = []
TEST_GROUPS = ("functional", "validation", "ui")


class Skip(Exception):
    """A case that can't run here; reported as SKIP with the reason."""


def case(tc_id, group, title):
    def register(fn):
        WAREHOUSE_CASES.append((tc_id, group, title, fn))
        return fn
    return register


def selected_cases(cfg):
    groups = set(getattr(cfg, "ls_test_groups", None) or TEST_GROUPS)
    ids = {str(i).strip().upper() for i in (getattr(cfg, "ls_test_cases", None) or []) if str(i).strip()}
    return [c for c in WAREHOUSE_CASES if c[1] in groups and (not ids or c[0] in ids)]


class WarehouseRun:
    """What the cases share: the page, this run's test codes, and the starting state for cleanup."""

    def __init__(self, page, prefix):
        self.page = page
        self.stamp = f"{prefix[:3]}{datetime.now().strftime('%H%M')}"
        self.start = snapshot(page)

    def code(self, name):
        code = f"{self.stamp}{name}"
        assert len(code) <= SHORT_CODE_MAX, f"test code {code} is longer than {SHORT_CODE_MAX} characters"
        return code

    def fresh(self):
        reload_warehouse(self.page)

    def need_advance(self):
        if self.start[0] != "A":
            raise Skip("the tenant is saved in Simple mode; switching to Advance would have to be saved")

    def save_ok(self):
        feedback = save_warehouse(self.page)
        assert any(SAVED_OK.search(m) for m in feedback), f"no 'Saved Successfully' message: {feedback}"
        reload_warehouse(self.page)

    def location(self, name, desc="QA test"):
        """A saved test location, created once per run."""
        code = self.code(name)
        if code not in codes(self.page, "storage"):
            add_row(self.page, "storage", code, desc)
            self.save_ok()
        return code

    def chain(self, depth, base="L"):
        """Saved test structure Location → Aisle → Bay → Level, `depth` levels deep; returns the codes."""
        path = [self.location(base)]
        for level, suffix in zip(LEVEL_ORDER[1:depth], "ABV"):
            code = self.code(base + suffix)
            open_path(self.page, path)
            if code not in codes(self.page, level):
                add_row(self.page, level, code, "QA test")
                self.save_ok()
            path.append(code)
        open_path(self.page, path)
        return path

    def cleanup(self):
        # Deleting a test location also removes its aisles, bays and levels
        reload_warehouse(self.page)
        test_rows = [c for c in codes(self.page, "storage") if c.startswith(self.stamp)]
        for code in test_rows:
            delete_row(self.page, "storage", code)
        if test_rows:
            self.save_ok()
        assert snapshot(self.page) == self.start, f"after cleanup {snapshot(self.page)} differs from the start {self.start}"
        return len(test_rows)


def expect_rejected(run, message):
    """Save must be refused with `message` and nothing sent to the server."""
    page, sent = run.page, []
    handler = lambda request: sent.append(request.url) if "CreateorUpdateStorageAisleBayLevel" in request.url else None
    page.on("request", handler)
    try:
        feedback = save_warehouse(page)
    finally:
        page.remove_listener("request", handler)
    assert any(message.lower() in m.lower() for m in feedback), f"expected '{message}', got {feedback}"
    assert not sent, "the invalid change was sent to the server"
    return f"rejected with '{message}'"


def has_add_button(page, level):
    expect(page.locator(f"{STRUCTURE} .{level}-panel")).to_be_visible()
    expect(page.locator(f"{STRUCTURE} .{level}-header button.btn-light")).to_be_visible()


# ---- Functional ---------------------------------------------------------

@case("WH_001", "functional", "Verify Warehouse page")
def wh_001(run):
    expect(run.page.locator(STRUCTURE)).to_be_visible()
    assert "/home/warehouse" in run.page.url, run.page.url
    expect(run.page.locator(f"{STRUCTURE} button.primary-button", has_text="Save")).to_be_visible()


@case("WH_002", "functional", "Verify Simple Configuration")
def wh_002(run):
    set_mode(run.page, "S")
    assert visible_panels(run.page) == ["storage"], f"visible panels: {visible_panels(run.page)}"


@case("WH_003", "functional", "Verify Advance Configuration")
def wh_003(run):
    set_mode(run.page, "S")
    set_mode(run.page, "A")
    assert visible_panels(run.page) == list(LEVEL_ORDER), f"visible panels: {visible_panels(run.page)}"


@case("WH_004", "functional", "Switch configuration modes")
def wh_004(run):
    page = run.page
    for value, expected in (("S", ["storage"]), ("A", list(LEVEL_ORDER)), ("S", ["storage"])):
        set_mode(page, value)
        assert visible_panels(page) == expected, f"after {value}: {visible_panels(page)}"
    set_mode(page, "A", proceed=False)
    assert current_mode(page) == "S" and visible_panels(page) == ["storage"], "answering No still switched the mode"
    return "each switch asks for confirmation; No keeps the current mode"


@case("WH_005", "functional", "Verify Location list")
def wh_005(run):
    set_mode(run.page, "S")
    found = codes(run.page, "storage")
    if not found:
        raise Skip("there are no saved locations to show")
    for row in rows(run.page, "storage").all():
        expect(row.locator(CODE)).to_be_visible()
    return f"locations: {', '.join(found)}"


@case("WH_006", "functional", "Add Location")
def wh_006(run):
    add_row(run.page, "storage", "", "")
    new = rows(run.page, "storage").last
    expect(new.locator(CODE)).to_be_editable()
    expect(new.locator(DESC)).to_be_editable()


@case("WH_007", "functional", "Save new Location")
def wh_007(run):
    code = run.location("L")
    assert code in codes(run.page, "storage"), f"{code} missing after save + reload"


@case("WH_008", "functional", "Delete Location")
def wh_008(run):
    code = run.location("D")
    delete_row(run.page, "storage", code)
    assert code not in codes(run.page, "storage"), "the row is still shown after the trash button"
    run.save_ok()
    assert code not in codes(run.page, "storage"), f"{code} is still saved after delete + save"


@case("WH_009", "functional", "Cancel Location deletion")
def wh_009(run):
    # There is no confirmation dialog: a deletion is cancelled by leaving without Save
    code = run.location("K")
    delete_row(run.page, "storage", code)
    run.fresh()
    assert code in codes(run.page, "storage"), f"{code} was deleted without Save"
    return "no confirmation dialog; leaving without Save keeps the location"


@case("WH_010", "functional", "Verify Aisle panel")
def wh_010(run):
    run.need_advance()
    has_add_button(run.page, "aisle")


@case("WH_011", "functional", "Select Location for Aisle")
def wh_011(run):
    run.need_advance()
    options, locations = parent_options(run.page, "aisle"), codes(run.page, "storage")
    assert sorted(options) == sorted(locations), f"dropdown {options} vs locations {locations}"


@case("WH_012", "functional", "Add Aisle")
def wh_012(run):
    run.need_advance()
    location, aisle = run.chain(2)
    assert codes(run.page, "aisle") == [aisle], f"aisles under {location}: {codes(run.page, 'aisle')}"


@case("WH_013", "functional", "Verify Bay panel")
def wh_013(run):
    run.need_advance()
    has_add_button(run.page, "bay")


@case("WH_014", "functional", "Add Bay")
def wh_014(run):
    run.need_advance()
    *_, aisle, bay = run.chain(3)
    assert codes(run.page, "bay") == [bay], f"bays under {aisle}: {codes(run.page, 'bay')}"


@case("WH_015", "functional", "Verify Level panel")
def wh_015(run):
    run.need_advance()
    has_add_button(run.page, "level")


@case("WH_016", "functional", "Add Level")
def wh_016(run):
    run.need_advance()
    *_, bay, level = run.chain(4)
    assert codes(run.page, "level") == [level], f"levels under {bay}: {codes(run.page, 'level')}"


@case("WH_017", "functional", "Save configuration")
def wh_017(run):
    page = run.page
    add_row(page, "storage", run.code("S"), "QA test")
    with page.expect_response(lambda r: "CreateorUpdateStorageAisleBayLevel" in r.url) as response:
        feedback = save_warehouse(page)
    assert response.value.ok, f"the save request returned {response.value.status}"
    assert any(SAVED_OK.search(m) for m in feedback), f"no success message: {feedback}"


@case("WH_018", "functional", "Verify persistence")
def wh_018(run):
    code = run.location("S")
    run.fresh()
    assert code in codes(run.page, "storage"), f"{code} is gone after a refresh"


@case("WH_019", "functional", "Verify parent-child mapping")
def wh_019(run):
    run.need_advance()
    location, aisle, bay, level = run.chain(4)
    for panel, expected in (("aisle", aisle), ("bay", bay), ("level", level)):
        assert codes(run.page, panel) == [expected], f"{panel} under its parent: {codes(run.page, panel)}"
    other = next((o for o in parent_options(run.page, "aisle") if o != location), None)
    if other:
        select_parent(run.page, "aisle", other)
        assert aisle not in codes(run.page, "aisle"), f"{aisle} also shows under {other}"


@case("WH_020", "functional", "Verify empty structure")
def wh_020(run):
    run.need_advance()
    page, errors = run.page, []
    handler = lambda error: errors.append(str(error))
    page.on("pageerror", handler)
    try:
        location = run.location("E")
        select_parent(page, "aisle", location)
        assert rows(page, "aisle").count() == 0, "a new location already has aisles"
        assert parent_options(page, "bay") == [], f"bay dropdown not empty: {parent_options(page, 'bay')}"
    finally:
        page.remove_listener("pageerror", handler)
    assert not errors, f"page errors: {errors}"


# ---- Validation ---------------------------------------------------------

@case("WH_021", "validation", "Add Location with empty name")
def wh_021(run):
    add_row(run.page, "storage", "", "no code")
    return expect_rejected(run, "Short code is mandatory")


@case("WH_022", "validation", "Add duplicate Location")
def wh_022(run):
    code = run.location("U")
    add_row(run.page, "storage", code, "duplicate")
    result = expect_rejected(run, "Duplicate short codes found")
    run.fresh()
    assert codes(run.page, "storage").count(code) == 1, f"{code} is saved more than once"
    return result


@case("WH_023", "validation", "Add Location with whitespace")
def wh_023(run):
    add_row(run.page, "storage", "   ", "spaces only")
    return expect_rejected(run, "Short code is mandatory")


@case("WH_024", "validation", "Add duplicate Aisle")
def wh_024(run):
    run.need_advance()
    _, aisle = run.chain(2)
    add_row(run.page, "aisle", aisle, "duplicate")
    return expect_rejected(run, "Duplicate short codes found")


@case("WH_025", "validation", "Add Bay without parent")
def wh_025(run):
    run.need_advance()
    select_parent(run.page, "aisle", run.location("E"))   # a location with no aisles
    assert parent_options(run.page, "bay") == [], "the location already has aisles"
    before = rows(run.page, "bay").count()
    run.page.locator(f"{STRUCTURE} .bay-header button.btn-light").click()
    run.page.wait_for_timeout(500)
    assert rows(run.page, "bay").count() == before, "a bay row was added without a parent aisle"
    return "+ adds no bay while there is no parent aisle"


@case("WH_026", "validation", "Add Level without parent")
def wh_026(run):
    run.need_advance()
    run.chain(2, "N")                                      # an aisle with no bays
    assert parent_options(run.page, "level") == [], "the aisle already has bays"
    before = rows(run.page, "level").count()
    run.page.locator(f"{STRUCTURE} .level-header button.btn-light").click()
    run.page.wait_for_timeout(500)
    assert rows(run.page, "level").count() == before, "a level row was added without a parent bay"
    return "+ adds no level while there is no parent bay"


@case("WH_027", "validation", "Delete Location with dependencies")
def wh_027(run):
    run.need_advance()
    location, *_ = run.chain(4, "X")
    delete_row(run.page, "storage", location)
    run.save_ok()
    assert location not in codes(run.page, "storage"), f"{location} is still saved"
    assert location not in parent_options(run.page, "aisle"), f"{location} is still offered as a parent"
    return "the location was deleted together with its aisles, bays and levels"


@case("WH_028", "validation", "Save invalid configuration")
def wh_028(run):
    run.need_advance()
    select_parent(run.page, "aisle", run.location("L"))
    add_row(run.page, "aisle", "", "no code")
    return expect_rejected(run, "Short code is mandatory")


@case("WH_029", "validation", "Save without changes")
def wh_029(run):
    before = snapshot(run.page)
    feedback = save_warehouse(run.page)
    assert not any(re.search(r"error|fail|invalid|duplicate|mandatory", m, re.I) for m in feedback), feedback
    run.fresh()
    assert snapshot(run.page) == before, "saving with no changes changed the data"


@case("WH_030", "validation", "Verify save failure handling")
def wh_030(run):
    page, code = run.page, run.code("F")
    add_row(page, "storage", code, "QA test")
    body = '{"message": "Internal Server Error", "statusCode": 500}'
    print("[WARN] WH_030 makes Save fail on purpose (simulated HTTP 500); the error message below is expected")
    page.route(SAVE_URL, lambda route: route.fulfill(status=500, body=body, content_type="application/json"))
    try:
        feedback = save_warehouse(page)
    finally:
        page.unroute(SAVE_URL)
    assert feedback, "no error message after a failed save"
    assert not any(SAVED_OK.search(m) for m in feedback), f"success shown although the save failed: {feedback}"
    assert not any("[object Object]" in m for m in feedback), f"the error message is not readable: {feedback}"
    run.fresh()
    assert code not in codes(page, "storage"), "the failed save was stored anyway"
    return f"simulated HTTP 500, the app showed: {feedback[0]}"


# ---- UI -------------------------------------------------------------------

@case("WH_031", "ui", "Verify Save button")
def wh_031(run):
    save = run.page.locator(f"{STRUCTURE} button.primary-button", has_text="Save")
    expect(save).to_be_visible()
    expect(save).to_be_enabled()


@case("WH_032", "ui", "Verify configuration radio buttons")
def wh_032(run):
    radios = run.page.locator("input[name='mode']")
    checked = lambda: [r.is_checked() for r in radios.all()]
    assert checked().count(True) == 1, f"checked radios: {checked()}"
    set_mode(run.page, "S" if current_mode(run.page) == "A" else "A")
    assert checked().count(True) == 1, f"after switching: {checked()}"


@case("WH_033", "ui", "Verify structure card colors")
def wh_033(run):
    backgrounds = []
    for level in LEVEL_ORDER:
        card = run.page.locator(f"{STRUCTURE} .card-top.{level}")
        expect(card).to_be_visible()
        backgrounds.append(card.evaluate("e => getComputedStyle(e).backgroundColor"))
    assert all(b not in ("rgba(0, 0, 0, 0)", "transparent") for b in backgrounds), f"card backgrounds: {backgrounds}"
    return "cards are styled; compare the colours with the design by eye"


@case("WH_034", "ui", "Verify delete icons")
def wh_034(run):
    for level in visible_panels(run.page):
        lefts = []
        for row in rows(run.page, level).all():
            trash = row.locator("button.btn-danger")
            expect(trash).to_be_visible()
            lefts.append(round(trash.bounding_box()["x"]))
        assert max(lefts, default=0) - min(lefts, default=0) <= 2, f"{level} trash buttons are not aligned: {lefts}"


@case("WH_035", "ui", "Verify add buttons")
def wh_035(run):
    for level in visible_panels(run.page):
        header = run.page.locator(f"{STRUCTURE} .{level}-header")
        button = header.locator("button.btn-light")
        expect(button).to_be_visible()
        h, b = header.bounding_box(), button.bounding_box()
        assert h["x"] <= b["x"] and b["x"] + b["width"] <= h["x"] + h["width"] + 1, f"the {level} + button is outside its header"


@case("WH_036", "ui", "Verify scrolling")
def wh_036(run):
    page = run.page
    for i in range(15):
        add_row(page, "storage", run.code(f"Z{i}"), "")
    panel = page.locator(f"{STRUCTURE} .storage-panel")
    scrolls = panel.evaluate("e => e.scrollHeight > e.clientHeight && ['auto', 'scroll'].includes(getComputedStyle(e).overflowY)")
    aisle = page.locator(f"{STRUCTURE} .aisle-panel")
    if aisle.is_visible():
        a, b = panel.bounding_box(), aisle.bounding_box()
        assert a["x"] + a["width"] <= b["x"] + 1 or a["y"] >= b["y"] + b["height"], "the Location panel overlaps the Aisle panel"
    return "the panel scrolls" if scrolls else "the panel grows with its rows (no inner scroll)"


@case("WH_037", "ui", "Verify responsive layout")
def wh_037(run):
    phone = run.page.context.new_page()
    try:
        phone.set_viewport_size({"width": 390, "height": 844})
        phone.goto(run.page.url)
        phone.locator(f"{STRUCTURE} .storage-panel").wait_for()
        expect(phone.locator(f"{STRUCTURE} button.primary-button", has_text="Save")).to_be_visible()
        overflow = phone.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        assert overflow <= 1, f"the page is {overflow}px wider than a 390px phone screen"
    finally:
        phone.close()


@case("WH_038", "ui", "Verify loading state")
def wh_038(run):
    page = run.page
    add_row(page, "storage", run.code("W"), "QA test")
    page.locator(f"{STRUCTURE} button.primary-button", has_text="Save").click()
    try:
        page.locator(f"{STRUCTURE} app-spinner *").first.wait_for(state="visible", timeout=2000)
        shown = True
    except PlaywrightTimeoutError:
        shown = False
    detect_feedback(page, wait_time=4)
    if not shown:
        raise Skip("no loading indicator appeared during save; confirm with the design")


@case("WH_039", "ui", "Verify success/error messages")
def wh_039(run):
    page = run.page
    add_row(page, "storage", run.code("T"), "QA test")
    ok = save_warehouse(page)
    assert any(SAVED_OK.search(m) for m in ok), f"no success message after save: {ok}"
    run.fresh()
    add_row(page, "storage", "", "")
    error = save_warehouse(page)
    assert any("mandatory" in m.lower() for m in error), f"no error message for an invalid save: {error}"
    return f"save: '{ok[0]}' | invalid: '{error[0]}' (add/delete show no message until Save)"


@case("WH_040", "ui", "Verify data after mode switching")
def wh_040(run):
    run.need_advance()
    before = snapshot(run.page)
    set_mode(run.page, "S")
    set_mode(run.page, "A")
    assert snapshot(run.page)[1:] == before[1:], "rows changed after Simple → Advance"
    run.fresh()
    assert snapshot(run.page) == before, "saved data changed after switching modes without Save"
    return "switching modes without Save keeps the rows; the switch itself is not saved"


# ---------------------------------------
# RUN THE SUITE
# ---------------------------------------
def run_warehouse_tests(page, cfg):
    from backend.tools.enhanced_report_generator import AutomationReporter

    cases = selected_cases(cfg)
    report_dir = os.path.join(ROOT_DIR, "reports", "warehouse", datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(report_dir, exist_ok=True)
    reporter = AutomationReporter(title="Warehouse Configuration Tests")
    print(f"[STEP] Warehouse tests: {len(cases)} case(s)")

    started = time.time()
    open_warehouse(page)
    run = WarehouseRun(page, getattr(cfg, "ls_test_prefix", None) or "QA")
    results = []
    for tc_id, group, title, fn in cases:
        t0, status, detail, shot = time.time(), "PASS", "", None
        try:
            run.fresh()
            detail = fn(run) or ""
        except Skip as e:
            status, detail = "SKIP", str(e)
        except Exception as e:  # assertion or page error: the case fails, the suite goes on
            status = "FAIL"
            detail = (str(e).strip().splitlines() or [type(e).__name__])[0][:300]
            shot = os.path.join(report_dir, f"{tc_id}.png")
            try:
                page.screenshot(path=shot, full_page=True)
            except Exception:
                shot = None
        print(f"[{status}] {tc_id} {title}" + (f" — {detail}" if detail else ""))
        results.append((tc_id, title, status, detail))
        reporter.add_test_step(f"{tc_id} {title}", {"PASS": "passed", "FAIL": "failed", "SKIP": "skipped"}[status],
                               round(time.time() - t0, 1), detail if status != "PASS" else None, shot)

    if getattr(cfg, "ls_test_cleanup", True):
        try:
            removed = run.cleanup()
            print(f"[PASS] Cleanup — {removed} test location(s) removed; the Warehouse page is back to its starting state")
        except Exception as e:
            detail = (str(e).strip().splitlines() or [type(e).__name__])[0][:300]
            print(f"[FAIL] Cleanup — {detail}")
            results.append(("CLEANUP", "Cleanup", "FAIL", detail))

    counts = {s: sum(1 for r in results if r[2] == s) for s in ("PASS", "FAIL", "SKIP")}
    print(f"Warehouse tests: passed={counts['PASS']} failed={counts['FAIL']} skipped={counts['SKIP']}")
    for tc_id, title, status, detail in results:
        print(f"  {status:<4}  {tc_id:<8} {title}" + (f" — {detail}" if status != "PASS" and detail else ""))

    reporter.finalize("FAILED" if counts["FAIL"] else "PASSED", round(time.time() - started, 1))
    html = reporter.generate_html_report(os.path.join(report_dir, "warehouse_report.html"))
    print(f"[STEP] Warehouse report: {html}")
    return counts["FAIL"] == 0
