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



# ======================================================
# CONFIG
# ======================================================
DRY_RUN = False
SEED = None
FAST_MODE = False  # Set True for fast mode (0.10s sleeps), False for default (1s)


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


def finish_audit(page, Config):
    if not Config.A_Checkboxes_BlindCount:
        print(" Finish Audit skipped - Blind Count checkbox is False")
        return

    finish_btn = page.locator('button[data-tour-id="finish-audit-btn"]')
    finish_btn.wait_for(state="visible")
    finish_btn.click()

    print(" Finish Audit clicked")

    finish_audit(page, Config)