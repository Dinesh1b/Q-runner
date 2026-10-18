
"""
Complete Playwright Automation Script with Enhanced Reporting
- Fixed all duplicate function definitions
- Completed header mapping logic
- Configured file paths properly
- Improved error handling
- Better variable scoping
- Fixed file upload redundancy
- Fixed audit flow issues
- Full reporting integration with HTML/PDF generation
"""

import sys
import os
import time
import random
import string
import difflib
import pandas as pd
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError,expect
import pandas as pd
import logging
import sys


from audit.audit_ui_validation import _navigate_to_audit_list
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    
# ======================================================
# CONFIG
# ======================================================
DRY_RUN = False
SEED = None
FAST_MODE = False  # Set True for fast mode (0.10s sleeps), False for default (1s)
ENABLE_REPORTING = True  # Set True to generate HTML/PDF reports

# File paths configuration
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

                   
if SEED is not None:
            random.seed(SEED)

# ======================================================
# PATH SETUP
# ======================================================
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# ======================================================
# CONSTANTS
# ======================================================
SLEEP_TIME = 0.10 if FAST_MODE else 1.0


logging.basicConfig(
    level=logging.INFO,
    format="  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),   # console output
          # file output
    ]
)
log = logging.getLogger(__name__)

    
def select_prime_dropdown(page, value_text=None, aria_controls=None, xpath=None):
    # âœ… Open dropdown â€” XPath > aria_controls > generic fallback
    if xpath:
        dropdown = page.locator(f"xpath={xpath}")
    elif aria_controls:
        dropdown = page.locator(f"[aria-controls='{aria_controls}']").locator("..")
    else:
        dropdown = page.locator(".p-dropdown")

    safe_click(dropdown)

    # âœ… No value_text = just open, don't select anything
    if not value_text:
        log.info("No value_text provided ” dropdown opened only.")
        return

    # âœ… Scope options list
    if aria_controls:
        options_locator = page.locator(f"#{aria_controls} li.p-dropdown-item")
    else:
        options_locator = page.locator("li.p-dropdown-item")

    options_locator.first.wait_for(state="visible", timeout=5000)
    all_options = options_locator.all_inner_texts()

    # âœ… Tier 1: Exact match
    if value_text in all_options:
        matched = value_text

    # âœ… Tier 2: Substring match
    elif any(value_text.lower() in o.lower() for o in all_options):
        matched = next(o for o in all_options if value_text.lower() in o.lower())
        log.info(f"âš ï¸  Partial match: '{value_text}' ’ '{matched}'")

    # âœ… Tier 3: Fuzzy match
    else:
        matches = difflib.get_close_matches(value_text, all_options, n=1, cutoff=0.4)
        if matches:
            matched = matches[0]
            log.info(f"âš ï¸  Fuzzy match: '{value_text}' ’ '{matched}'")
        else:
            log.info(f" No match found for '{value_text}'. Available: {all_options}")
            return

    option = page.locator(f"li.p-dropdown-item:has-text('{matched}')")
    safe_click(option)


def choose_frequency(page, frequency_type, Config):
    log.info(f"Choose Frequency: {frequency_type}")

    dropdown = page.locator("p-dropdown[formcontrolname='frequencyId']")
    dropdown.wait_for(state="visible", timeout=10000)



    safe_click(dropdown.locator(".p-dropdown-trigger"))
    wait2(page)

    panel = page.locator("div.p-dropdown-panel")
    panel.wait_for(state="visible")

    safe_click(panel.locator("li.p-dropdown-item", has_text=frequency_type))
    wait2(page)

    handle_frequency_logic(page, frequency_type, Config)


def handle_frequency_logic(page, frequency_type, Config):

    if frequency_type.lower() == "Manual":
        # No date required
        return

    if frequency_type.lower() in ["one-time"]:
        select_start_date(page )
    
    elif frequency_type.lower() == "daily":
        select_start_end_date(page, Config  )

    elif frequency_type.lower() == "weekly":
        select_weekly_options(page, Config)
        select_start_end_date(page, Config)

    elif frequency_type.lower() == "monthly":
        select_frequency_date(page, Config)
        select_start_end_date(page, Config)

def click_photo_validation_type(page, photo_type: str, sample_size=None):
    """
    photo_type: "None", "Random", "Damaged"
    sample_size: required only when photo_type == "Random" (fills 'Sample Size (%)')
    """
    log.info(f"➡️ Select Photo Validation Type: {photo_type}")

    value_map = {
        "None": "",
        "Random": "Random",
        "Damaged": "Damaged"
    }

    if photo_type not in value_map:
        raise Exception(f" Invalid Photo Validation Type: {photo_type}. Valid: {list(value_map.keys())}")

    radio_value = value_map[photo_type]

    if radio_value == "":
        radio_component = page.locator(
            "p-radiobutton[name='photoValidationType'] input[type='radio'][value='']"
        ).locator("xpath=ancestor::p-radiobutton")
    else:
        radio_component = page.locator(
            f"p-radiobutton[name='photoValidationType'][value='{radio_value}']"
        )

    radio_component.wait_for(state="attached")

    if radio_component.count() == 0:
        raise Exception(f" Photo Validation Type '{photo_type}' not found in UI")

    radio_box = radio_component.locator(".p-radiobutton-box")
    classes = radio_box.get_attribute("class") or ""
    if "p-highlight" not in classes:
        radio_box.scroll_into_view_if_needed()
        radio_box.click()

    wait2(page)

    # ── Sample Size (%) only appears for Random ──
    if photo_type == "Random":
        if sample_size in (None, ""):
            raise Exception(
                f"❌ Photo Validation Type 'Random' requires a Sample Size (%) value"
            )

        size_input = page.locator("input[formcontrolname='photoValidationSize']")
        size_input.wait_for(state="visible", timeout=8000)
        size_input.click()
        size_input.fill("")
        size_input.fill(str(sample_size))
        wait2(page)
        log.info(f"✔ Sample Size (%) set to {sample_size}")
    else:
        log.info(f"ℹ️ No Sample Size (%) needed for '{photo_type}'")


        

def select_weekly_options(page, Config):

    log.info(" Choose Weekly Day")

    safe_click(page.get_by_role("combobox", name="Choose day"))
    wait2(page)

    safe_click(
    page.locator(f"li.p-dropdown-item:has-text('{Config.Target__Day}')")
)
    wait2(page)

def select_frequency_date(page, Config):

    log.info(" Select Frequency Date")

    frequency_date = datetime.strptime(
    Config.Target_Date,   # dd/mm/yyyy
    "%d/%m/%Y"
).strftime("%m/%d/%Y")   
    #frequency_date = (datetime + timedelta(days=9)).strftime("%d/%m/%Y")

    freq_input = page.locator(
        "p-calendar[formcontrolname='frequencyDate'] input"
    )

    freq_input.wait_for(state="visible")
    freq_input.click()
    freq_input.press("Control+A")
    freq_input.press("Backspace")
    freq_input.type(frequency_date, delay=50)
    freq_input.press("Enter")

    wait2(page)
def select_start_date(page):


        log.info(" Choose Start Date")

        today = datetime.today()
        #end_day = today + timedelta(days=10)

        start_day = today.day
       

        # Start Date
        safe_click(page.locator("button[aria-label='Choose Date']").nth(0))
        popup = page.locator("div.p-datepicker[role='dialog']")
        popup.wait_for(state="visible")

        safe_click(popup.locator(f"td[aria-label='{start_day}']:not(.p-disabled) span").first)

        wait2(page)


       

#          IMPROVED DATE SELECTION FUNCTIONS


def select_prime_date(
    page: Page,
    formcontrolname: str,
    target_date: datetime,
    use_direct_input: bool = True
) -> None:
    """
    Select date in PrimeNG p-calendar.
    Tries direct input first (most stable), falls back to popup navigation.
    """


    log.info(f"  Setting date for {formcontrolname}: {target_date.strftime('%d/%m/%Y')}")

    calendar = page.locator(f"p-calendar[formcontrolname='{formcontrolname}']")
    calendar.wait_for(state="visible", timeout=10000)

    input_field = calendar.locator("input")

    if use_direct_input:
        try:
            input_field.click(force=True)
            input_field.fill("")  # clear existing value
            formatted_date = target_date.strftime("%d/%m/%Y")  # adjust format if app uses %m/%d/%Y
            input_field.type(formatted_date, delay=40)
            input_field.press("Enter")
            time.sleep(0.6)

            # Verify
            expect(input_field).to_have_value(formatted_date, timeout=5000)
            log.info(f" Direct input successful: {formatted_date}")
            

            return

        except Exception as e:
            log.info(f"Direct input failed ({e}), falling back to calendar popup")

    # â”””€ Popup fallback â””””””””””””””””””””””””””””””””””””””””€
    
        date_button = calendar.locator("button[aria-label='Choose Date']")
        safe_click(date_button)

        popup = page.locator("div.p-datepicker[role='dialog']:visible").last
        expect(popup).to_be_visible(timeout=8000)

        # Navigate to correct month/year
        header = popup.locator(".p-datepicker-title")
        expected_header = target_date.strftime("%B %Y")  # "March 2026"

        attempts = 0
        max_attempts = 12  # roughly one year
        while header.inner_text().strip() != expected_header and attempts < max_attempts:
            next_btn = popup.locator(".p-datepicker-next")
            prev_btn = popup.locator(".p-datepicker-prev")

            if next_btn.is_visible():
                safe_click(next_btn)
            elif prev_btn.is_visible():
                safe_click(prev_btn)
            else:
                raise RuntimeError("Cannot navigate calendar - no prev/next buttons found")

            time.sleep(0.5)
            attempts += 1

        if attempts >= max_attempts:
            raise RuntimeError(f"Failed to reach {expected_header} after {max_attempts} attempts")

        # Select the day
        day_locator = popup.locator(
            f"td[aria-label='{target_date.day}'] span:not(.p-disabled)"
        ).first

        day_locator.wait_for(state="visible", timeout=6000)
        safe_click(day_locator)

        # Wait for popup to close & value to appear
        expect(popup).to_be_hidden(timeout=5000)
        expect(input_field).to_have_value(target_date.strftime("%d/%m/%Y"), timeout=6000)

        log.info(f" Popup selection successful: {target_date.day} {target_date.strftime('%B %Y')}")


def select_start_end_date(page, Config):

      

        log.info("  Select Start & End Date")

        today = datetime.today()
        start_date = today  # or today + timedelta(days=1) if must be future
        end_date = today + timedelta(days=Config.Day_s)

        start_str = start_date.strftime("%m/%d/%Y")   # 02/03/2026
        end_str   = end_date.strftime("%m/%d/%Y")     # e.g. 01/04/2026

        log.info(f"Planned ’ Start: {start_str}   End: {end_str}")

        def set_date(formcontrolname: str, date_str: str, target_date: datetime):
            calendar = page.locator(f"p-calendar[formcontrolname='{formcontrolname}']")
            calendar.wait_for(state="visible", timeout=10000)
            input_el = calendar.locator("input")

            # Try direct typing first (most apps accept DD/MM/YYYY)
            try:
                input_el.click(force=True)
                input_el.fill("")           # clear
                input_el.type(date_str, delay=40)
                input_el.press("Enter")
                time.sleep(0.8)

                # Quick verify
                current_val = input_el.input_value()
                if date_str in current_val or date_str.replace('/', '') in current_val:
                    log.info(f" Typing worked for {formcontrolname}: {date_str}")
                    return
                else:
                    log.info(f"Typing partial/ignored ’ fallback to popup")
            except Exception as e:
                log.info(f"Typing failed ({e}) ’ fallback to popup")

            # Popup fallback (robust navigation)
            try:
                safe_click(calendar.locator("button[aria-label='Choose Date']"))
                popup = page.locator("div.p-datepicker[role='dialog']:visible").last
                expect(popup).to_be_visible(timeout=8000)

                header = popup.locator(".p-datepicker-title")
                expected = target_date.strftime("%B %Y")   # "March 2026"

                attempts = 0
                while header.inner_text().strip() != expected and attempts < 24:
                    if popup.locator(".p-datepicker-next").is_visible():
                        safe_click(popup.locator(".p-datepicker-next"))
                    elif popup.locator(".p-datepicker-prev").is_visible():
                        safe_click(popup.locator(".p-datepicker-prev"))
                    else:
                        raise RuntimeError("No navigation buttons")
                    time.sleep(0.4)
                    attempts += 1

                if attempts >= 24:
                    raise RuntimeError(f"Couldn't reach {expected}")

                day_sel = popup.locator(
                    f"td[aria-label='{target_date.day}'] span:not(.p-disabled)"
                ).first
                day_sel.wait_for(state="visible")
                safe_click(day_sel)

                expect(popup).to_be_hidden(timeout=6000)
                expect(input_el).to_have_value(lambda v: date_str in v or str(target_date.day) in v, timeout=5000)

                log.info(f" Popup success for {formcontrolname}: {date_str}")

            except Exception as e:
                page.screenshot(path=f"date-fail-{formcontrolname}-{int(time.time())}.png")
                raise RuntimeError(f"Date set failed for {formcontrolname}: {e}")

        # Apply to both
        set_date("startDateTime", start_str, start_date)
        set_date("endDateTime", end_str, end_date)

        # Final debug read
        try:
            s_val = page.locator("[formcontrolname='startDateTime'] input").input_value()
            e_val = page.locator("[formcontrolname='endDateTime'] input").input_value()
            log.info(f"FINAL VALUES ’ Start: {s_val} | End: {e_val}")
        except:
            pass


# ======================================================
# UTILITY FUNCTIONS
# ======================================================




def wait_for_overlay_to_disappear(page: Page) -> None:
    """Wait for common overlay elements to disappear."""
    overlays = [
        ".p-dialog-mask",
        ".p-component-overlay",
        ".cdk-overlay-backdrop"
    ]
    for selector in overlays:
        try:
            page.wait_for_selector(selector, state="detached", timeout=2000)
        except PlaywrightTimeoutError:
            pass


def js_click(page: Page, locator) -> bool:
    """
    Attempt to click an element, first normally then via JavaScript if needed.
    Returns True if successful, False otherwise.
    """
    try:
        locator.click(force=True)
        return True
    except Exception:
        try:
            handle = locator.element_handle(timeout=2000)
            if handle:
                page.evaluate("(el) => el.click()", handle)
                return True
        except Exception:
            return False
    return False

    # --------------------------------------------------------------
    # SELECT BRANCH (PrimeNG p-dropdown via XPath)
    # --------------------------------------------------------------
def select_branch(page, branch_text: str):
        dropdown = page.locator(
            'xpath=/html/body/app-root/app-layout/div/app-header/div[1]/div[2]/div[2]//p-dropdown'
        )
        dropdown.wait_for(state="visible", timeout=30000)
        dropdown.locator(".p-dropdown-label").click()

        panel = page.locator(".p-dropdown-panel").last
        panel.wait_for(state="visible", timeout=30000)

        search = panel.locator("input.p-dropdown-filter")
        if search.count() > 0:
            search.fill("")
            search.fill(branch_text)
            page.wait_for_timeout(300)
        panel.locator("li.p-dropdown-item").get_by_text(branch_text, exact=True)
        option = panel.locator("li.p-dropdown-item", has_text=branch_text)
        if option.count() == 0:
            raise Exception(f" Branch not found: {branch_text}")

        option.first.click()
        panel.wait_for(state="hidden", timeout=30000)

        dropdown.locator(
            ".p-dropdown-label", has_text=branch_text
        ).wait_for(state="visible", timeout=30000)
def safe_click(locator) -> None:
    """Safe Playwright click that refuses disabled elements."""

    locator.wait_for(state="attached", timeout=15000)
    locator.wait_for(state="visible", timeout=15000)
    locator.scroll_into_view_if_needed()

    # Never force-click a disabled control
    try:
        if locator.is_disabled():
            raise AssertionError(
                f"Cannot click disabled element: {locator}"
            )
    except Exception:
        # Some PrimeNG containers don't support is_disabled()
        classes = locator.get_attribute("class") or ""
        aria_disabled = locator.get_attribute("aria-disabled")

        if "p-disabled" in classes or aria_disabled == "true":
            raise AssertionError(
                "Cannot click disabled PrimeNG element"
            )

    locator.click(timeout=10000)


def wait2(page: Page) -> None:
    """Wait for 2 seconds."""
    page.wait_for_timeout(2000)


def click_and_wait(page: Page, click_selector: str, wait_selector: Optional[str] = None, 
                   timeout: int = 15000) -> None:
    """Click an element and optionally wait for another element to appear."""
    page.wait_for_selector(click_selector, timeout=timeout).click()
    if wait_selector:
        page.wait_for_selector(wait_selector, timeout=timeout)
    time.sleep(SLEEP_TIME)


def random_name() -> str:
    """Generate a random audit name."""
    return "Audit_" + "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )


def _normalize(s: str) -> str:
    """Normalize string for comparison."""
    return (s or "").strip().lower()
# =====================================
# Configure Cross Audit Section
# =====================================

def configure_cross_audit(page, cross_type: str, cross_auditor: str = None, cross_size: str = None):

    log.info(f"  Configure Cross Audit: {cross_type}")

    # Step 1: Select Cross Audit Type
    click_cross_audit_type(page, cross_type)
    wait2(page)

    # Step 2: If Random Recheck → fill percentage
    if cross_type == "Random Recheck":
        if not cross_size:
            raise Exception("❌ Random Recheck requires cross_size value")

        size_input = page.locator("[formcontrolname='crossCheckSize']")
        size_input.wait_for(state="visible")
        size_input.fill(str(cross_size))

    # Step 3: Select Cross Auditor (if required)
    if cross_type in ["Random Recheck", "Discrepancy Recheck"]:

        if not cross_auditor:
            raise Exception(f"❌ {cross_type} requires Cross Auditor")

        dropdown = page.locator("p-dropdown[formcontrolname='crossCheckAuditor']")
        dropdown.wait_for(state="visible", timeout=10000)

        current_label = dropdown.locator("span.p-dropdown-label").inner_text().strip()

        if current_label == cross_auditor:
            log.info(f"✔ Cross Auditor already set to '{cross_auditor}' — skipping")
        else:
            log.info(f"  Choose Cross Auditor: {cross_auditor}")

            safe_click(dropdown.locator(".p-dropdown-trigger"))
            panel = page.locator("div.p-dropdown-panel")
            panel.wait_for(state="visible")

            option = panel.locator("li.p-dropdown-item", has_text=cross_auditor)

            if option.count() == 0:
                raise Exception(f"❌ Cross Auditor '{cross_auditor}' not found")

            option.first.scroll_into_view_if_needed()
            option.first.click()

    wait2(page)





# =====================================
# Select Multiple Auditors (PrimeNG Safe)
# =====================================

def select_auditors(page, auditor_input):

    # Convert to list
    if isinstance(auditor_input, str):
        auditor_names = [name.strip() for name in auditor_input.split(",") if name.strip()]
    else:
        auditor_names = auditor_input

    log.info(f"  Select Auditors: {', '.join(auditor_names)}")

    # Open dropdown
    safe_click(page.locator("div.p-multiselect-trigger").first)

    # Wait for overlay panel to appear
    panel = page.locator("div.p-multiselect-panel")
    panel.wait_for(state="visible")

    for auditor_name in auditor_names:

        # Use text-based locator inside panel (VERY IMPORTANT)
        option = panel.locator("li.p-multiselect-item", has_text=auditor_name)

        if option.count() == 0:
            raise Exception(f"❌ Auditor '{auditor_name}' not found in dropdown")

        target = option.first
        classes = target.get_attribute("class") or ""

        if "p-highlight" in classes:
            log.info(f"✔ Auditor already selected: '{auditor_name}' — skipping")
            continue

        target.scroll_into_view_if_needed()
        target.click()
        page.wait_for_timeout(200)  # let PrimeNG update highlight state before next check

    # Close dropdown safely
    page.keyboard.press("Escape")

# ======================================================
# DROPDOWN FUNCTIONS
# ======================================================

def read_dropdown_options_for_locator(page: Page, dropdown_locator, 
                                     timeout: int = 3000) -> List[str]:
    """
    Open a p-dropdown, read all options, close it, and return the option list.
    """
    try:
        combobox = dropdown_locator.locator('span[role="combobox"]').first
        combobox.scroll_into_view_if_needed()
        js_click(page, combobox)
        time.sleep(0.12)

        try:
            page.wait_for_selector("div.p-dropdown-panel:visible", timeout=timeout)
        except PlaywrightTimeoutError:
            page.mouse.click(0, 0)
            return []

        panels = page.locator("div.p-dropdown-panel:visible")
        option_texts = []
        panel_count = panels.count()
        
        for i in range(panel_count):
            panel = panels.nth(i)
            try:
                item_count = panel.locator("li.p-dropdown-item").count()
            except Exception:
                item_count = 0
                
            if item_count > 0:
                try:
                    option_texts = panel.evaluate(
                        """panel => Array.from(panel.querySelectorAll('li.p-dropdown-item'))
                                           .map(li => li.innerText ? li.innerText.trim() : 
                                                     (li.textContent || '').trim())"""
                    )
                except Exception:
                    option_texts = []
                    for j in range(item_count):
                        try:
                            text = panel.locator("li.p-dropdown-item").nth(j).inner_text().strip()
                            option_texts.append(text)
                        except Exception:
                            option_texts.append("")
                break

        page.mouse.click(0, 0)
        time.sleep(0.12)
        return option_texts

    except Exception as e:
        log.info(f"âœ– Failed to read dropdown options: {e}")
        try:
            page.mouse.click(0, 0)
        except Exception:
            pass
        return []

def click_audit_type(page, Audit_Type: str):
    VALID_AUDIT_TYPES = {"Cycle Count", "Complete Count"}  # update once you confirm DOM values
    if Audit_Type not in VALID_AUDIT_TYPES:
        raise ValueError(
            f"Audit Type '{Audit_Type}' is invalid. "
            f"Must be one of: {sorted(VALID_AUDIT_TYPES)}"
        )

    locator = page.locator(f"p-radiobutton[value='{Audit_Type}'] .p-radiobutton-box")
    locator.wait_for(state="visible")

    if is_field_disabled(locator):
        log.info(f"ℹ Audit Type is locked in edit mode — skipping (currently set, not changing to '{Audit_Type}').")
        return

    locator.scroll_into_view_if_needed()
    locator.click()

# =====================================
# Select Cross Audit Type (PrimeNG - Final Stable Version)
# =====================================

def click_cross_audit_type(page, cross_audit_type: str):


    log.info(f"➡️ Select Cross Audit Type: {cross_audit_type}")

    value_map = {
        "None": "",
        "Random Recheck": "Random",
        "Discrepancy Recheck": "Discrepancy"
    }

    if cross_audit_type not in value_map:
        raise Exception(
            f" Invalid Cross Audit Type: {cross_audit_type}. "
            f"Valid options: {list(value_map.keys())}"
        )

    radio_value = value_map[cross_audit_type]

    # Scope by name="crossCheckType" to avoid collision with photoValidationType
    if radio_value == "":
        radio_component = page.locator(
            "p-radiobutton[name='crossCheckType'] input[type='radio'][value='']"
        ).locator("xpath=ancestor::p-radiobutton")
    else:
        radio_component = page.locator(
            f"p-radiobutton[name='crossCheckType'][value='{radio_value}']"
        )

    radio_component.wait_for(state="attached")

    if radio_component.count() == 0:
        raise Exception(f" Cross Audit Type '{cross_audit_type}' not found in UI")

    radio_box = radio_component.locator(".p-radiobutton-box")

    classes = radio_box.get_attribute("class") or ""
    if "p-highlight" not in classes:
        radio_box.scroll_into_view_if_needed()
        radio_box.click()

    wait2(page)


# ======================================================
# DROPDOWN OPTION SELECTION WITH FUZZY MATCHING 
def select_option_for_dropdown_locator(page: Page, dropdown_locator, option_text: str, 
                                       timeout: int = 7000) -> Tuple[bool, str, Optional[any]]:
    """
    Select an option from a dropdown with fuzzy matching fallback.
    Returns (success: bool, method: str, element: Locator or None)
    """
    option_text_norm = _normalize(option_text)
    log.info(f"[select_option] selecting '{option_text}'")

    try:
        trigger = dropdown_locator
        try:
            inner = dropdown_locator.locator('span[role="combobox"]').first
            if inner.count() and inner.is_visible():
                trigger = inner
        except Exception:
            pass

        try:
            trigger.scroll_into_view_if_needed()
        except Exception:
            pass

        clicked = js_click(page, trigger)
        if not clicked:
            try:
                trigger.click(timeout=2000, force=True)
            except Exception:
                pass

        time.sleep(SLEEP_TIME)

        panel_selectors = [
            "div.p-dropdown-panel", "div.p-multiselect-panel", "ul.p-dropdown-items",
            "div.ui-dropdown-panel", "div[role='listbox']", "div[role='dialog']"
        ]

        panels = []
        for sel in panel_selectors:
            try:
                loc = page.locator(sel)
                cnt = loc.count()
                for i in range(cnt):
                    p = loc.nth(i)
                    if p.is_visible():
                        panels.append(p)
            except Exception:
                continue

        if not panels:
            panels = [page]

        # 1) Exact match
        for panel in panels:
            try:
                opt = panel.locator(f"li:has-text('{option_text}')")
                if opt.count():
                    for j in range(opt.count()):
                        candidate = opt.nth(j)
                        if candidate.is_visible():
                            js_click(page, candidate)
                            return True, "exact_li", candidate
            except Exception:
                continue

        # 2) Case-insensitive + fuzzy match
        for panel in panels:
            try:
                items = panel.locator("li, div, span")
                cnt = items.count()
            except:
                cnt = 0

            seen = []
            for i in range(cnt):
                try:
                    it = items.nth(i)
                    if not it.is_visible():
                        continue
                    txt = it.inner_text().strip()
                    if not txt:
                        continue
                    seen.append((i, txt, it))
                    if _normalize(txt) == option_text_norm:
                        js_click(page, it)
                        return True, "case_insensitive_direct", it
                except:
                    continue

            if seen:
                texts = [t for (_, t, _) in seen]
                lower_texts = [t.lower() for t in texts]
                matches = difflib.get_close_matches(option_text_norm, lower_texts, n=1, cutoff=0.6)
                if matches:
                    best = matches[0]
                    idx = lower_texts.index(best)
                    chosen = seen[idx][2]
                    js_click(page, chosen)
                    return True, "fuzzy", chosen

        # 3) Page-wide exact match
        page_items = page.locator(f"text={option_text}")
        if page_items.count():
            for i in range(page_items.count()):
                candidate = page_items.nth(i)
                if candidate.is_visible():
                    js_click(page, candidate)
                    return True, "page_wide", candidate

        return False, "not_found", None

    except Exception as e:
        return False, f"exception:{e}", None


def is_already_mapped(dropdown_locator) -> bool:
    """Check if dropdown already has a selected value."""
    try:
        label = dropdown_locator.locator("span.p-dropdown-label:not(.p-placeholder)")
        return label.count() > 0 and label.first.inner_text().strip() != ""
    except Exception:
        return False


def select_item_group(page: Page, group_name: str) -> None:
    """Select value from 'Select Item Group' PrimeNG dropdown."""
    dropdown = page.locator("p-dropdown[placeholder='Select Item Group']")
    dropdown.locator("div.p-dropdown-trigger").click()
    time.sleep(SLEEP_TIME)

    panel = page.locator("div.p-dropdown-panel")
    time.sleep(SLEEP_TIME)

    panel.locator("input.p-dropdown-filter").fill(group_name)
    time.sleep(SLEEP_TIME)

    panel.locator("li.p-dropdown-item", has_text=group_name).first.click()


def _read_auditor_mapping_df(Config):
        sheet_name = getattr(Config, "EXCEL_SHEET_AUDITOR_MAPPING", None)
        if isinstance(sheet_name, str):
            sheet_name = sheet_name.strip()

        if sheet_name in (None, "", "None"):
            workbook = pd.ExcelFile(Config.EXCEL_PATH)
            if "AUDITOR_MAPPING" in workbook.sheet_names:
                sheet_name = "AUDITOR_MAPPING"
            elif len(workbook.sheet_names) == 1:
                sheet_name = workbook.sheet_names[0]
            else:
                raise ValueError(
                    "EXCEL_SHEET_AUDITOR_MAPPING is required for Audit Plan mapping. "
                    f"Available sheets: {', '.join(workbook.sheet_names)}"
                )

        df = pd.read_excel(
            Config.EXCEL_PATH,
            sheet_name=sheet_name
        )

        if isinstance(df, dict):
            if sheet_name in df:
                df = df[sheet_name]
            elif len(df) == 1:
                df = next(iter(df.values()))
            else:
                raise ValueError(
                    "Unable to resolve a single auditor-mapping sheet from the workbook."
                )

        return df
    # --------------------------------------------------------------
    # LOAD AUDITOR MAPPING FROM SINGLE SHEET
    # Returns: { auditor_name: { "categories": [...], "storages": [...] } }
    # Reads EXCEL_SHEET_AUDITOR_MAPPING with columns: Auditor | Category | Storage
    # --------------------------------------------------------------
def load_auditor_mapping(Config):
        df = _read_auditor_mapping_df(Config)

        result = {}   # { auditor: { "categories": [], "storages": [] } }
        seen   = {}   # { auditor: { "categories": set, "storages": set } }

        for _, row in df.iterrows():
            auditor = str(row[Config.EXCEL_auditor_col]).strip()
            if not auditor or auditor.lower() == "nan":
                continue

            if auditor not in result:
                result[auditor] = {"categories": [], "storages": []}
                seen[auditor]   = {"categories": set(), "storages": set()}

            # --- Category column ---
            cat_val = str(row.get(Config.EXCEL_category_col, "")).strip()
            if cat_val and cat_val.lower() != "nan":
                for cat in cat_val.split(","):
                    cat = cat.strip()
                    if cat and cat.lower() not in seen[auditor]["categories"]:
                        result[auditor]["categories"].append(cat)
                        seen[auditor]["categories"].add(cat.lower())

            # --- Storage column ---
            stor_val = str(row.get(Config.EXCEL_storage_col, "")).strip()
            if stor_val and stor_val.lower() != "nan":
                for stor in stor_val.split(","):
                    stor = stor.strip()
                    if stor and stor.lower() not in seen[auditor]["storages"]:
                        result[auditor]["storages"].append(stor)
                        seen[auditor]["storages"].add(stor.lower())

        return result

        # --------------------------------------------------------------
        # FIND EXACT AUDITOR ROW  (exact <td> match, not substring)
        # --------------------------------------------------------------
def find_auditor_row(page, auditor_name):
            rows = page.locator("tr")
            for i in range(rows.count()):
                row = rows.nth(i)
                tds = row.locator("td")
                for j in range(tds.count()):
                    if tds.nth(j).inner_text().strip() == auditor_name:
                        return row
            return None
    # --------------------------------------------------------------
    # OPEN MULTISELECT PANEL FOR A ROW
    # --------------------------------------------------------------
def open_multiselect_panel(page, row):
        row.locator("div.p-multiselect").click()
        panel = page.locator("div.p-multiselect-panel").filter(
            has=page.locator(":visible")
        )
        panel.wait_for(state="visible")
        return panel


    # --------------------------------------------------------------
    # APPLY AUDITOR ASSIGNMENTS
    #   "Random"      ’ nothing to assign
    #   "By Category" ’ assign Category column values per auditor
    #   "By Storage"  ’ assign Storage  column values per auditor
    # --------------------------------------------------------------
def apply_auditor_assignments(page, mapping_type, Config):
    """Fixed: accepts Config; mapping key 'By Storage' → 'By Location' per UI."""
    if mapping_type == "Random":
        log.info("ℹ Mapping type is Random — no assignments needed")
        return

    auditor_map = load_auditor_mapping(Config)
    log.info(f"📋 Loaded auditor mapping: {auditor_map}")

    for auditor, data in auditor_map.items():

        if mapping_type == "By Category":
            items = data["categories"]
            item_type = "Category"
        elif mapping_type == "By Location":
            # UI label is "By Location"; excel col mapped via Config.EXCEL_storage_col
            items = data["storages"]
            item_type = "Location"
        else:
            raise ValueError(
                f"Unknown AUDIT_MAPPING_TYPE: '{mapping_type}'. "
                "Must be 'Random', 'By Category', or 'By Location'."
            )

        if not items:
            log.info(f"⚠ No {item_type} found for '{auditor}' in sheet")
            continue

        log.info(f"→ Assigning {item_type} {items} to '{auditor}'")
        row = find_auditor_row(page, auditor)
        if row is None:
            log.info(f" Row not found for auditor: '{auditor}'")
            continue

        panel = open_multiselect_panel(page, row)
        select_items_in_panel(page, panel, items, auditor, item_type)
    # --------------------------------------------------------------
    # TEST MAPPING AND SAVING
    # --------------------------------------------------------------
def test_mapping_and_saving(page, Config):

        log.info("Uploading primary file")
        page.set_input_files("input#formFileSm", Config.EXCEL_PATH)
        page.wait_for_selector("div.row-container")

        
# ======================================================
# HEADER MAPPING
# ======================================================

def map_headers(page: Page, mapping: dict) -> None:
    """
    Map Excel headers to application fields with safety checks.
    """
    row_container = page.locator("div.row-container")
    left_col = row_container.locator("div.col-md-6").nth(0)
    right_col = row_container.locator("div.col-md-6").nth(1)

    labels = left_col.locator("div.label > label")
    dropdowns = right_col.locator("p-dropdown")

    # Read all label texts
    try:
        label_texts = left_col.evaluate(
            """col => Array.from(col.querySelectorAll('div.label > label'))
                           .map(el => el.innerText ? el.innerText.trim() :
                                     (el.textContent || '').trim())"""
        )
    except Exception as e:
        log.info(f"Warning: evaluate failed: {e}. Falling back to incremental read.")
        label_texts = []
        for i in range(labels.count()):
            try:
                label_texts.append(labels.nth(i).inner_text().strip())
            except Exception:
                label_texts.append("")

    log.info(f"Found headers: {label_texts}")

    for required_label, excel_header in mapping.items():
        wait_for_overlay_to_disappear(page)

        if required_label not in label_texts:
            log.info(f"⚠ Missing label: '{required_label}' not found on page")
            continue

        idx = label_texts.index(required_label)
        dropdown = dropdowns.nth(idx)

        if is_already_mapped(dropdown):
            log.info(f"⭐ Skipped '{required_label}' (already mapped)")
            continue

        step_start = time.time()
        ok, method, _ = select_option_for_dropdown_locator(page, dropdown, excel_header)
        duration = round(time.time() - step_start, 2)

        if ok:
            log.info(f"✔ Mapped '{required_label}' → '{excel_header}' via {method} ({duration}s)")
        else:
            log.info(f"✖ Failed to map '{required_label}' → '{excel_header}' ({duration}s)")

    log.info("   Header mapping completed.")
    





    # --------------------------------------------------------------
    # OPEN MULTISELECT PANEL FOR A ROW
    # --------------------------------------------------------------
def open_multiselect_panel(page, row):
        row.locator("div.p-multiselect").click()
        panel = page.locator("div.p-multiselect-panel").filter(
            has=page.locator(":visible")
        )
        panel.wait_for(state="visible")
        return panel

        # --------------------------------------------------------------
        # FIND EXACT AUDITOR ROW  (exact <td> match, not substring)
        # --------------------------------------------------------------
def find_auditor_row(page, auditor_name):
            rows = page.locator("tr")
            for i in range(rows.count()):
                row = rows.nth(i)
                tds = row.locator("td")
                for j in range(tds.count()):
                    if tds.nth(j).inner_text().strip() == auditor_name:
                        return row
            return None

    # --------------------------------------------------------------
    # SELECT ITEMS IN AN OPEN MULTISELECT PANEL  (idempotent)
    # --------------------------------------------------------------
def select_items_in_panel(page, panel, items, auditor_name, item_type):
        for item_text in items:
            option = panel.locator("li.p-multiselect-item", has_text=item_text)

            if option.count() == 0:
                log.info(
                    f"âš  {item_type} '{item_text}' not found for '{auditor_name}'"
                )
                continue

            cls = option.first.get_attribute("class") or ""
            if "p-highlight" not in cls:
                option.first.click()
                page.wait_for_timeout(300)
            else:
                log.info(
                    f" Already selected: '{item_text}' for '{auditor_name}'"
                )

        page.keyboard.press("Escape")
        page.wait_for_timeout(300)


# =====================================
# Enable / Disable Audit Options (Dynamic)
# =====================================

def enable_audit_options(page, audit_options: dict):


    log.info("  Configure Audit Options")

    for field_name, value in audit_options.items():

        checkbox = page.locator(f"[formcontrolname='{field_name}']")

        # Wait for checkbox to be attached
        checkbox.wait_for(state="attached")

        should_check = str(value).strip().lower() in ["true", "yes", "1"]

        if should_check:
            if not checkbox.is_checked():
                checkbox.check()
        else:
            if checkbox.is_checked():
                checkbox.uncheck()

    wait2(page)

    # --------------------------------------------------------------
    # SELECT BRANCH using XPATH (PrimeNG p-dropdown)
    # --------------------------------------------------------------
def select_branch(page, branch_text: str):

        # 1ï¸âƒ£ Branch dropdown container (XPath)
        dropdown = page.locator(
            'xpath=/html/body/app-root/app-layout/div/app-header/div[1]/div[2]/div[2]//p-dropdown'
        )
        dropdown.wait_for(state="visible", timeout=30000)

        # 2ï¸âƒ£ Click dropdown label to open
        dropdown.locator(".p-dropdown-label").click()

        # 3ï¸âƒ£ Wait for dropdown panel (overlay)
        panel = page.locator(".p-dropdown-panel").last
        panel.wait_for(state="visible", timeout=30000)

        # 4ï¸âƒ£ Filter search (if exists)
        search = panel.locator("input.p-dropdown-filter")
        if search.count() > 0:
            search.fill("")
            search.fill(branch_text)
            page.wait_for_timeout(300)

        # 5ï¸âƒ£ Select branch option
        option = panel.locator(
            "li.p-dropdown-item",
            has_text=branch_text
        )

        if option.count() == 0:
            raise Exception(f" Branch not found: {branch_text}")

        option.first.click()

        # 6ï¸âƒ£ Ensure panel closed
        panel.wait_for(state="hidden", timeout=30000)

        # 7ï¸âƒ£ Final verification
        dropdown.locator(
            ".p-dropdown-label",
            has_text=branch_text
        ).wait_for(state="visible", timeout=30000)

def set_checkbox(page, selector, should_be_checked):
        checkbox = page.wait_for_selector(selector)
        if should_be_checked and not checkbox.is_checked():
            checkbox.check(force=True)
        elif not should_be_checked and checkbox.is_checked():
            checkbox.uncheck(force=True)  


    # --------------------------------------------------------------
    # CLICK AUDIT ROW
    # --------------------------------------------------------------
def click_audit(page: Page, ap_audit_name: str) -> None:
    page.wait_for_load_state("networkidle")

    audit = page.locator(
        f"table tbody tr td[data-label='Name'] span[title='{ap_audit_name}']"
    ).first

    audit.click()

    print(f"Opened audit: {ap_audit_name}")
# ======================================================
# EDIT-MODE FIELD STATE VALIDATION
# ======================================================

def is_field_disabled(locator) -> bool:
    """
    Check disabled state for:
    - Native HTML elements: disabled
    - PrimeNG components: p-disabled
    - ARIA components: aria-disabled="true"
    - Disabled child or parent elements
    """

    # 1. Native Playwright disabled check
    try:
        if locator.is_disabled():
            return True
    except Exception:
        pass

    # 2. Direct disabled attribute
    try:
        if locator.get_attribute("disabled") is not None:
            return True
    except Exception:
        pass

    # 3. Direct aria-disabled attribute
    try:
        aria_disabled = locator.get_attribute("aria-disabled")
        if aria_disabled == "true":
            return True
    except Exception:
        pass

    # 4. PrimeNG disabled class on current element
    try:
        classes = locator.get_attribute("class") or ""
        if "p-disabled" in classes:
            return True
    except Exception:
        pass

    # 5. Disabled ancestor
    try:
        disabled_parent = locator.locator(
            "xpath=ancestor-or-self::*["
            "contains(concat(' ', normalize-space(@class), ' '), ' p-disabled ') "
            "or @aria-disabled='true' "
            "or @disabled"
            "]"
        )

        if disabled_parent.count() > 0:
            return True
    except Exception:
        pass

    # 6. Disabled descendant
    try:
        disabled_child = locator.locator(
            "[disabled], "
            "[aria-disabled='true'], "
            ".p-disabled"
        )

        if disabled_child.count() > 0:
            return True
    except Exception:
        pass

    return False


def verify_edit_field_state(
    page: Page,
    expected_state: dict,
    timeout: int = 5000
) -> bool:

    field_selector_map = {

        "Audit Owner":
            "p-dropdown[formcontrolname='auditOwner'] .p-dropdown-label",

        "Item Group":
            "#role",

        "Audit Plan Name":
            "input[formcontrolname='name']",

        "Audit Type":
            "p-radiobutton[name='auditType'] input[type='radio']",
    }

    all_ok = True

    log.info("======================================================")
    log.info("EDIT-MODE FIELD STATE VALIDATION")
    log.info("======================================================")

    for field_name, expected in expected_state.items():

        selector = field_selector_map.get(field_name)

        if not selector:
            all_ok = False
            log.info(f"✖ No selector configured for '{field_name}'")
            continue

        try:
            locator = page.locator(selector)

            # Audit Type native inputs are intentionally hidden
            if field_name == "Audit Type":
                locator.first.wait_for(
                    state="attached",
                    timeout=timeout
                )
            else:
                locator.first.wait_for(
                    state="visible",
                    timeout=timeout
                )

            locator_count = locator.count()

            if locator_count == 0:
                all_ok = False
                log.info(f"✖ '{field_name}' not found")
                continue

            disabled_results = []

            for index in range(locator_count):

                field = locator.nth(index)

                # No visibility check here
                is_disabled = is_field_disabled(field)

                disabled_results.append(is_disabled)

            is_disabled = all(disabled_results)

            actual = (
                "DISABLED"
                if is_disabled
                else "ENABLED"
            )

            if actual == expected:
                log.info(
                    f"✔ {field_name}: "
                    f"expected={expected} actual={actual}"
                )
            else:
                all_ok = False
                log.info(
                    f"✖ {field_name}: "
                    f"expected={expected} actual={actual}"
                )

        except PlaywrightTimeoutError as error:
            all_ok = False
            log.info(
                f"✖ {field_name}: "
                f"not found/attached within {timeout}ms"
            )

        except Exception as error:
            all_ok = False
            log.info(f"✖ {field_name}: {error}")

    log.info("------------------------------------------------------")

    if all_ok:
        log.info("✔ ALL EDIT-MODE FIELD STATES CONFIRMED")
    else:
        log.info("✖ EDIT-MODE FIELD STATE VALIDATION FAILED")

    log.info("======================================================")

    return all_ok

def get_audit_type_state(page, selector):
    radios = page.locator(selector)

    count = radios.count()

    if count == 0:
        raise AssertionError("Audit Type radio buttons not found")

    disabled_states = [
        radios.nth(i).is_disabled()
        for i in range(count)
    ]

    return "DISABLED" if all(disabled_states) else "ENABLED"
def validate_field_state(page, field_name, selector, expected_state):

    try:
        if field_name == "Audit Type":
            actual_state = get_audit_type_state(page, selector)

        else:
            locator = page.locator(selector)
            locator.first.wait_for(
                state="visible",
                timeout=5000
            )

            actual_state = (
                "DISABLED"
                if locator.first.is_disabled()
                else "ENABLED"
            )

        if actual_state == expected_state:
            print(
                f"✔ {field_name}: "
                f"expected={expected_state} "
                f"actual={actual_state}"
            )
            return True

        print(
            f"✘ {field_name}: "
            f"expected={expected_state} "
            f"actual={actual_state}"
        )
        return False

    except Exception as error:
        print(f"✘ {field_name}: {error}")
        return False
# ======================================================
# EXPECTED EDIT-MODE FIELD STATE
# ======================================================

EDIT_FIELD_STATE = {
    "Audit Owner": "ENABLED",
    "Item Group": "DISABLED",
    "Audit Plan Name": "DISABLED",
    "Audit Type": "DISABLED",
}
FIELD_TYPES = {
    "Audit Owner": "control",
    "Item Group": "control",
    "Audit Plan Name": "control",
    "Audit Type": "radio_group",
}

# ======================================================
# AUDIT CREATION
# ======================================================

def update_audit(page, Config) -> str:
    """Create a new audit and return its name."""

     #branch selection
    select_branch(page, Config.Branch)
    print(f"   Branch selected: {Config.Branch}")
    log.info("Open Audit page")
    page.wait_for_timeout(1000)
    # Wait until element visible
    page.wait_for_selector("a[href='/home/audit']", state="visible")

    # Click
    page.click("a[href='/home/audit']")
    page.wait_for_load_state("networkidle")
    wait2(page)




    log.info("Select Audit Plan")
    safe_click(page.locator("button:has-text('Audit Plan')"))
    wait2(page)


# click Audit Plan Name
        
    # Click Audit Plan Name
    click_audit(page, Config.ap_audit_name)

    # Wait for edit form
    page.locator(
        "input[formcontrolname='name']"
    ).wait_for(
        state="visible",
        timeout=10000
    )

    # ======================================================
    # VALIDATE EDIT-MODE FIELD STATES
    # ======================================================

    field_state_ok = verify_edit_field_state(
        page,
        EDIT_FIELD_STATE
    )

    if not field_state_ok:
        raise AssertionError(
            "Edit-mode UI validation failed. "
            "Expected field states do not match actual UI state."
        )

    log.info(
        "✔ Edit-mode UI validation passed. "
        "Continuing with allowed update fields."
    )    
#==========================================================================================        
#------------------------------------------------------------------------------------------

    # Open Audit Owner dropdown
    log.info("Choose Audit Owner")
    select_prime_dropdown(
        page,
        xpath="/html/body/app-root/app-layout/div/app-audit-plan/app-add-audit-plan/div/div[2]/form/div[1]/div/div[1]/div[2]/p-dropdown/div"
    )
    wait2(page)

    # Select audit owner from open dropdown
    page.locator(f"li.p-dropdown-item:has-text('{Config.Audit_Owner}')").first.click()
    wait2(page)
            
       
#------------------------------------------------------------------------------------------
    # Select Group
     
# Select Group — only if this field is actually editable in this mode
    if not is_field_disabled(page.locator("#role")):
        safe_click(page.locator("#role .p-dropdown-trigger"))
        panel = page.locator("div.p-dropdown-panel")
        panel.wait_for(state="visible")
        panel.locator("input.p-dropdown-filter").fill(Config.Group_Name)
        panel.locator("li.p-dropdown-item").filter(has_text=Config.Group_Name).first.click()
        wait2(page)
    else:
        log.info("ℹ Item Group is locked in edit mode — skipping Group change.")
#------------------------------------------------------------------------------------------


#------------------------------------------------------------------------------------------
 
 # Select Audit Type as Cycle Count or Complete Count       

    log.info("Select Audit Type")
    click_audit_type(page, Config.Audit_Type)   #Cycle Count or Complete Count     
    wait2(page)
#------------------------------------------------------------------------------------------
    #Choose Frequency - Manual, one-time, Daily , Weekly, Monthly
    choose_frequency(page, Config.frequency, Config)
#dynamic selection based on requirement           
        
 #------------------------------------------------------------------------------------------     
# Click Next
    
    safe_click(page.get_by_role("button", name="Next"))
    wait2(page)

#---------------------------------------------------------------------------------------------------------
        # Select Auditors
    select_auditors(page, [Config.Auditor1, Config.Auditor2])
#---------------------------------------------------------------------------------------------------------
 # Enable Audit Options  isDamageQty, isStockItems, isGeoTagging(true/false)
 # Enable Audit Options  isDamageQty, isStockItems, isGeoTagging(true/false)
# Audit Damaged Inventory
    set_checkbox(page, "input[formcontrolname='isDamageQty']", Config.A_Checkboxes_Audit_Damaged)

        # Show Stock Count to Auditor
    set_checkbox(
    page,
    "xpath=//label[normalize-space(text())='Enable Blind Count']/ancestor::div[contains(@class,'row')][1]//input[@type='checkbox']",
    Config.A_Checkboxes_BlindCount
)

        # Geo Tagging
    set_checkbox(page, "input[formcontrolname='isGeoTagging']", Config.A_Checkboxes_geo)

        # Photo Validation
  
    click_photo_validation_type(page, Config.photo_type, Config.sample_size)
    time.sleep(SLEEP_TIME)
                
        
#---------------------------------------------------------------------------------------------------------
        #Sample Size, Cross Auditor
        #CROSS_AUDIT_TYPE = "Random Recheck", "Discrepancy Recheck", "None"

    if Config.CROSS_AUDIT_TYPE == "Random Recheck":
            configure_cross_audit(page, cross_type="Random Recheck", cross_size="50", cross_auditor=Config.CROSS_Auditor_name)
    elif Config.CROSS_AUDIT_TYPE  == "Discrepancy Recheck":
            configure_cross_audit(page, cross_type="Discrepancy Recheck", cross_auditor=Config.CROSS_Auditor_name)
    else:
            configure_cross_audit(page, cross_type="None")
#---------------------------------------------------------------------------------------------------------
 # Click Next
        
    log.info("  Click Next")
    safe_click(page.get_by_role("button", name="Next"))
    wait2(page)
#------------------------------------------------
    
#    mapping_type = Config.AUDIT_MAPPING_TYPE
    mapping_type = Config.AUDIT_MAPPING_TYPE
    page.locator("p-dropdown[formcontrolname='periodicalType']").click()
    page.locator("li.p-dropdown-item", has_text= mapping_type).click()
    time.sleep(SLEEP_TIME)
            # "Random" ’ nothing extra; "By Category"/"By Storage" ’ assign from sheet
    apply_auditor_assignments(page, mapping_type, Config) 
#---------------------------------------------------------------------------------------------------------
 # Save Audit

    log.info("Update Audit")
    safe_click(page.locator("button.primary-button:has-text('Update')"))
    page.wait_for_load_state("networkidle")
    
    page.wait_for_load_state("networkidle")
    wait2(page)
   
    _navigate_to_audit_list(page, Config)

 
