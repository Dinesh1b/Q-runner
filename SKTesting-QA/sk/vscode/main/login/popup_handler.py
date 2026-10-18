
#from popup_handler import detect_feedback


#detect_feedback(page)

#print("   Workflow completed")
#page.wait_for_timeout(5000)
# popup_handler.py
"""
Utility to detect and log feedback messages (SweetAlert2 / PrimeNG) after form submission.
"""

from playwright.sync_api import Page
import time
from datetime import datetime

# ==========================================================
# UNIVERSAL FEEDBACK DETECTOR
# Detects:
#   - SweetAlert2 popup
#   - PrimeNG Toast messages
#   - Multiple concurrent toasts
# Prints with timestamp
# ==========================================================

def detect_feedback(page: Page, wait_time: int = 5, check_generic_alerts: bool = True):
    """
    Detect and log feedback messages from the page.
    
    Args:
        page: Playwright Page object
        wait_time: Duration in seconds to listen for messages (default: 5)
        check_generic_alerts: Whether to check for role="alert" messages (default: True)
    
    Returns:
        List of collected feedback messages
    """
    start = time.time()
    collected = []

    print("\n Checking Feedback Messages...\n")

    while time.time() - start < wait_time:
        # --------------------------
        # SweetAlert2
        # --------------------------
        swal = page.locator(".swal2-popup")
        if swal.count() > 0:
            try:
                title = swal.locator(".swal2-title").inner_text(timeout=2000)
                content = swal.locator(".swal2-html-container").inner_text(timeout=2000)

                message = f"[SweetAlert2] {title} - {content}"
                if message not in collected:
                    collected.append(message)
                    print(f"{datetime.now().strftime('%H:%M:%S')} → {message}")

            except:
                pass

        # --------------------------
        # PrimeNG Toast (Multiple Support)
        # --------------------------
        toasts = page.locator(".p-toast-message")
        toast_count = toasts.count()

        for i in range(toast_count):
            try:
                toast = toasts.nth(i)
                severity = toast.get_attribute("class")
                summary = toast.locator(".p-toast-summary").inner_text(timeout=2000)
                detail = toast.locator(".p-toast-detail").inner_text(timeout=2000)

                message = f"[PrimeNG] {summary} - {detail}"
                if message not in collected:
                    collected.append(message)
                    print(f"{datetime.now().strftime('%H:%M:%S')} → {message}")

            except:
                pass

        # --------------------------
        # Generic Alert (role="alert" wrapper)     # ← NEW SECTION
        # --------------------------
        if check_generic_alerts:                   # ← NEW CONDITIONAL
            alerts = page.locator('[role="alert"].toast-message')  # ← NEW LOCATOR
            alert_count = alerts.count()           # ← NEW COUNT

            for i in range(alert_count):           # ← NEW LOOP
                try:
                    text = alerts.nth(i).inner_text(timeout=2000)  # ← NEW EXTRACTION
                    message = f"[Alert] {text}"    # ← NEW FORMAT
                    if message not in collected:
                        collected.append(message)
                        print(f"{datetime.now().strftime('%H:%M:%S')} → {message}")

                except (TimeoutError, AttributeError) as e:  # ← CONSISTENT EXCEPTION
                    pass

        time.sleep(0.5)

    if not collected:
        print(f"{datetime.now().strftime('%H:%M:%S')} → No feedback messages detected")

    print("---------------------------------------------------\n")

    return collected
