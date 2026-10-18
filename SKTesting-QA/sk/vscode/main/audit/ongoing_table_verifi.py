import sys
import os
import time
from datetime import datetime
from typing import Dict
from playwright.sync_api import sync_playwright, Page

# ======================================================
# CONFIG
# ======================================================
DRY_RUN = False

CI_MODE = os.getenv("CI") is not None

# ======================================================
# PATH SETUP
# ======================================================
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login
from login.popup_handler import detect_feedback



# ======================================================
# EXPECTED DATA
# ======================================================
EXPECTED_ROW = {
    "Audit Name": "Audit_PWDNZ5_1",
    "Type": "Complete Count",
    "Audited / Total Line Item": "0 / 10",
    "Audited / Total Qty": "0 / 100",
    "Matched LineItem": "0",
    "Shortfall LineItem": "0",
    "Excess LineItem": "0",
    "Status": "Not Started"
}


# ======================================================
# NAVIGATION
# ======================================================
def navigate_to_ongoing_audits(page: Page):
    page.click("a[href='#/home/audit']")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("tbody tr", timeout=10000)


# ======================================================
# HEADER MAPPING
# ======================================================
def get_column_index_map(page: Page) -> Dict[str, int]:
    headers = page.locator("thead th")
    header_map = {}
    for i in range(headers.count()):
        header_text = headers.nth(i).inner_text().strip()
        header_map[header_text] = i
    return header_map


# ======================================================
# FETCH ROW DATA
# ======================================================
def get_audit_row_data(page: Page, audit_name: str) -> Dict[str, str]:

    page.wait_for_selector("tbody tr", timeout=10000)
    header_map = get_column_index_map(page)

    row = page.locator(
        f"tbody tr:has(td:has-text('{audit_name}'))"
    )

    if row.count() == 0:
        raise Exception(f"Audit row '{audit_name}' not found")

    row = row.first
    cells = row.locator("td")

    actual_data = {}

    for column_name in EXPECTED_ROW.keys():
        if column_name in header_map:
            index = header_map[column_name]
            actual_data[column_name] = cells.nth(index).inner_text().strip()
        else:
            actual_data[column_name] = "COLUMN NOT FOUND"

    return actual_data


# ======================================================
# VALIDATION
# ======================================================
def normalize(value: str) -> str:
    if not value:
        return ""
    return value.strip().lower()


def validate_audit_row(page: Page,
                       actual: Dict[str, str],
                       expected: Dict[str, str],
                       reporter=None) -> bool:

    errors = []
    matched = []

    for column, expected_value in expected.items():

        actual_value = actual.get(column, "")

        if normalize(actual_value) == normalize(expected_value):
            matched.append(f"{column} ✔")
        else:
            error_msg = (
                f"{column}  | Expected: {expected_value} | Actual: {actual_value}"
            )
            errors.append(error_msg)

    report_message = (
        "Matched Columns:\n" + "\n".join(matched) +
        "\n\nFailed Columns:\n" + ("\n".join(errors) if errors else "None")
    )

    if errors:

        screenshot_path = f"screenshot_{int(time.time())}.png"
        page.screenshot(path=screenshot_path)

        if reporter:
            reporter.add_log("Validation failed.")
            reporter.add_log(report_message)
            reporter.add_test_step(
                "Audit Row Validation",
                "failed",
                duration=0,
                error=report_message,
                screenshot=screenshot_path
            )

        return False

    else:
        if reporter:
            reporter.add_log("All columns matched successfully.")
            reporter.add_log(report_message)
            reporter.add_test_step(
                "Audit Row Validation",
                "passed",
                duration=0,
                error=report_message
            )

        return True


# ======================================================
# MAIN
# ======================================================
def main():

   

    start_time = time.time()
    validation_status = False

    print("\n🚀 STARTING AUDIT AUTOMATION\n")



    with sync_playwright() as p:

            step = time.time()
            browser, page = login(
                p,
                browser_name="chrome",
                environment="QA"
            )


            detect_feedback(page)

            step = time.time()
            navigate_to_ongoing_audits(page)


            step = time.time()
            actual_row = get_audit_row_data(
                page,
                EXPECTED_ROW["Audit Name"]
            )



    validate_audit_row(
                page,
                actual_row,
                EXPECTED_ROW
            )



    if not CI_MODE and not DRY_RUN:
        page.wait_for_timeout(2000)

        browser.close()



print("\n   Automation execution completed\n")


if __name__ == "__main__":
    main()
