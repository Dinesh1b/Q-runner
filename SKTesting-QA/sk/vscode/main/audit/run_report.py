"""
One report per Audit.py run, one sheet per step.

Audit.py creates a RunReport at the start of the run. It makes the run folder
    <Config.e2e_output_dir>/Audit_Run_<audit>_<MMDD_HHMM>/
and writes Audit_Run_<audit>_<MMDD_HHMM>.xlsx into it:
    Overview  - one row per step: result, PASS / FAIL / ... counts, duration, note
    <step>    - one sheet per step (Login, Create Audit, Stock Audit A1, Audit Summary, ...)
    Bugs      - every FAIL / ERROR row of all the steps
    Screenshots      - every screenshot of the run (FAIL_..., ERROR_..., Settings TC-...), each under its
                       file name; the Screenshot / Attachments cells of the other sheets link to it
    <file> - <sheet> - every sheet of each Excel file a test registered with attach_file (the settings
                       import test file "Settings stock bad")
No other report workbook is written in a run: Audit Summary / History / Settings put their checks in their
sheet of this workbook (save_to_run_report). Their files go into the run folder, no subfolders, each name
prefixed with its step (run_files): Summary_UI_..., Summary_History_..., Settings_..., ERROR_... When the
workbook is written, the screenshots and registered Excel files are copied into it and removed from the
folder. Files the app downloaded (the Export Excel, PDFs) stay as separate files next to the workbook; the
Overview lists them with a link that opens them.

Modules add their checks with record() / record_rows(config, ...): they go into the sheet of the step
that is running. Without a RunReport (a module run on its own) both do nothing.
"""
import io
import math
import os
import re
import time
from collections import OrderedDict
from datetime import datetime

COLUMNS = ["Group", "Check", "Expected", "Actual", "Status", "Finding", "Screenshot"]
STATUSES = ["PASS", "FAIL", "ERROR", "KNOWN", "WARN", "NOT RUN"]
FILLS = {"PASS": "C6EFCE", "FAIL": "FFC7CE", "ERROR": "FFC7CE", "KNOWN": "FCE4D6", "WARN": "FFEB9C",
         "NOT RUN": "D9D9D9", "SKIPPED": "D9D9D9"}
BUG_COLUMNS = ["Bug ID", "Module", "Sub Module", "Bug Title", "Environment", "Severity", "Priority",
               "Preconditions", "Steps to Reproduce", "Expected Result", "Actual Result", "Reproducibility",
               "Status", "Attachments"]
IMAGE_EXT = (".png", ".jpg", ".jpeg")
TABLE_EXT = (".xlsx", ".xlsm")
SHOT_WIDTH = 1000            # px: wider screenshots are scaled down in the Screenshots sheet
ROW_PX = 20                  # default Excel row height (15 pt) in px
SHORT_NAMES = [("Summary_History_", "History "), ("Summary_UI_", "Summary "), ("Settings_", "Settings "),
               ("Audit Summary Report", "Export"), ("Audit_Summary_Report", "Export")]


def _short(stem) -> str:
    """Short sheet-name label of a file: 'Summary_History_Audit Summary Report' -> 'History Export'."""
    for long, short in SHORT_NAMES:
        stem = stem.replace(long, short)
    return " ".join(stem.replace("_", " ").split())


def _safe(text) -> str:
    """Text usable in a file / folder name."""
    return re.sub(r'[<>:"/\\|?*\s]+', "_", str(text or "")).strip("_") or "audit"


def _sheet_name(name, used) -> str:
    """Excel sheet name: no []:*?/\\, at most 31 characters, unique."""
    base = re.sub(r"[\[\]:*?/\\]", "", str(name)).strip()[:31].strip() or "Step"
    out, n = base, 2
    while out.lower() in used:
        out = f"{base[:28]}_{n}"
        n += 1
    used.add(out.lower())
    return out


def _txt(value) -> str:
    return " ".join(str("" if value is None else value).split())


class RunReport:
    def __init__(self, config):
        self.config = config
        self.audit = getattr(config, "ap_audit_name", "") or "audit"
        self.started = datetime.now()
        self.finished = None
        base = getattr(config, "e2e_output_dir", "") or os.getcwd()
        self.name = f"Audit_Run_{_safe(self.audit)}_{self.started:%m%d_%H%M}"
        self.folder = os.path.join(base, self.name)
        if os.path.exists(os.path.join(self.folder, f"{self.name}.xlsx")):     # a second run in the same minute
            self.name = f"Audit_Run_{_safe(self.audit)}_{self.started:%m%d_%H%M%S}"
            self.folder = os.path.join(base, self.name)
        os.makedirs(self.folder, exist_ok=True)
        self.steps = OrderedDict()      # sheet -> {"rows", "result", "secs", "note"}
        self.current = None
        self.page = None
        self.attached = []              # screenshots / Excel files of the run folder, kept in memory
        self.embed_tables = set()       # Excel files (names) to copy into the workbook: attach_file()
        config.run_report = self
        config.run_folder = self.folder
        print(f"Run report folder: {self.folder}")

    # ── steps ─────────────────────────────────────────────
    def _step(self, sheet):
        return self.steps.setdefault(sheet, {"rows": [], "result": "", "secs": 0.0, "note": ""})

    def step(self, sheet, fn, *args, results=None, label=None, **kwargs):
        """Run fn(*args, **kwargs) as step `sheet` and return what it returns. Rows that modules record
        meanwhile go into this sheet; so do the new rows of `results` (a stock_audit_checks.Results).
        A step that records nothing gets one '<label> completed' row. An exception is recorded as an
        ERROR row and raised again."""
        st = self._step(sheet)
        if st["result"] == "SKIPPED":
            st["result"], st["note"] = "", ""
        self.current = sheet
        before_rows = len(st["rows"])
        before_res = len(getattr(results, "rows", []) or []) if results is not None else 0
        t0 = time.time()
        page = next((a for a in args if hasattr(a, "screenshot")), None)
        if page is not None:
            self.page = page
        try:
            value = fn(*args, **kwargs)
        except Exception as e:
            self._take_results(results, before_res)
            self.add(label or sheet, "step ran", False, "runs without an error",
                     f"error: {str(e).splitlines()[0][:200] if str(e) else type(e).__name__}",
                     status="ERROR", screenshot=self._shot(sheet))
            st["note"] = f"stopped: {str(e).splitlines()[0][:120] if str(e) else type(e).__name__}"
            st["secs"] += time.time() - t0
            self.current = None
            raise
        self._take_results(results, before_res)
        if len(st["rows"]) == before_rows:
            failed = value is False
            self.add(label or sheet, f"{label or sheet} completed", not failed, "completed",
                     "returned False" if failed else "completed")
        st["secs"] += time.time() - t0
        self.current = None
        return value

    def skip(self, sheet, why):
        st = self._step(sheet)
        if not st["rows"]:
            st["result"], st["note"] = "SKIPPED", why
        print(f"x {sheet}: {why}")

    def _take_results(self, results, start):
        if results is None:
            return
        for row in list(getattr(results, "rows", []) or [])[start:]:
            area, name, ok, detail = (list(row) + ["", "", False, ""])[:4]
            self.add(area, name, ok, "", detail)

    def _shot(self, sheet):
        if self.page is None:
            return ""
        path = os.path.join(self.folder, f"ERROR_{_safe(sheet)[:30]}_{datetime.now():%H%M%S}.png")
        try:
            self.page.screenshot(path=path, full_page=True)
            return path
        except Exception:
            return ""

    # ── rows ──────────────────────────────────────────────
    def add(self, group, check, ok, expected="", actual="", status=None, finding="", screenshot="", sheet=None):
        status = status or ("PASS" if ok else "FAIL")
        self.extend([OrderedDict([("Group", group), ("Check", check), ("Expected", expected), ("Actual", actual),
                                  ("Status", status), ("Finding", finding), ("Screenshot", screenshot)])], sheet)

    def extend(self, rows, sheet=None):
        sheet = sheet or self.current or "Other"
        st = self._step(sheet)
        for r in rows:
            st["rows"].append(OrderedDict((k, _txt(r.get(k, ""))) for k in COLUMNS))

    # ── workbook ──────────────────────────────────────────
    def _counts(self, rows):
        return {s: sum(1 for r in rows if r["Status"] == s) for s in STATUSES}

    def _result(self, st):
        if st["result"] == "SKIPPED":
            return "SKIPPED"
        c = self._counts(st["rows"])
        if c["ERROR"]:
            return "ERROR"
        if c["FAIL"]:
            return "FAIL"
        if c["KNOWN"] or c["WARN"]:
            return "PASS (known)"
        return "PASS" if st["rows"] else "NOT RUN"

    # ── files of the run folder that go into the workbook ──
    def _collect_files(self):
        """Read the new screenshots and registered Excel files of the run folder into memory (oldest first).
        Other Excel files (the app's downloads) are not touched: they stay separate files."""
        done = {a["file"] for a in self.attached}
        names = [f for f in os.listdir(self.folder)
                 if f not in done and not f.startswith((self.name, "~$"))
                 and (f.lower().endswith(IMAGE_EXT) or f in self.embed_tables)]
        for f in sorted(names, key=lambda f: os.path.getmtime(os.path.join(self.folder, f))):
            path = os.path.join(self.folder, f)
            try:
                if f.lower().endswith(IMAGE_EXT):
                    from PIL import Image as PILImage
                    data = open(path, "rb").read()
                    with PILImage.open(io.BytesIO(data)) as im:
                        size = im.size
                    self.attached.append({"file": f, "kind": "image", "data": data, "size": size, "path": path})
                else:
                    from openpyxl import load_workbook
                    src = load_workbook(path, data_only=True, read_only=True)
                    tables = [(ws.title, [list(r) for r in ws.iter_rows(values_only=True)]) for ws in src.worksheets]
                    src.close()
                    self.attached.append({"file": f, "kind": "table", "data": tables, "path": path})
            except Exception as e:
                print(f"   could not copy {f} into the report (left in the folder): {str(e).splitlines()[0][:120]}")

    def _shot_rows(self):
        """{file name: row of its caption in the Screenshots sheet}; the image sits on the next row."""
        rows, at = {}, 1
        for a in self.attached:
            if a["kind"] == "image":
                w, h = a["size"]
                rows[a["file"]] = at
                at += math.ceil(h * min(1.0, SHOT_WIDTH / w) / ROW_PX) + 3
        return rows

    @staticmethod
    def _goto(cell, sheet, row):
        """Make cell a link to A<row> of sheet in this workbook."""
        from openpyxl.styles import Font
        from openpyxl.worksheet.hyperlink import Hyperlink
        cell.hyperlink = Hyperlink(ref=cell.coordinate, location=f"'{sheet}'!A{row}")
        cell.font = Font(color="0563C1", underline="single")

    @classmethod
    def _link(cls, cell, shot_rows, Font):
        """A Screenshot / Attachments cell holding a path: the file name, linked to its image."""
        name = os.path.basename(str(cell.value or ""))
        if name in shot_rows:
            cell.value = name
            cls._goto(cell, "Screenshots", shot_rows[name])

    def write(self) -> str:
        from openpyxl import Workbook
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.styles import Alignment, Font, PatternFill
        self.finished = datetime.now()
        cfg = self.config
        self._collect_files()
        shot_rows = self._shot_rows()
        back = {}                       # screenshot file -> (sheet, row) of its check
        wb = Workbook()
        ov = wb.active
        ov.title = "Overview"
        info = [("Audit", self.audit), ("Audit mode", getattr(cfg, "Audit_mode", "")),
                ("Environment", getattr(cfg, "environments", "")), ("Started", f"{self.started:%Y-%m-%d %H:%M:%S}"),
                ("Finished", f"{self.finished:%Y-%m-%d %H:%M:%S}"), ("Run folder", self.folder)]
        for k, v in info:
            ov.append([k, v])
            ov.cell(ov.max_row, 1).font = Font(bold=True)
        ov.append([])
        head = ["#", "Step", "Result", "Checks"] + STATUSES + ["Duration (s)", "Note"]
        ov.append(head)
        head_row = ov.max_row
        totals = {s: 0 for s in STATUSES}
        used = {"overview", "bugs"}
        bugs = []
        for n, (sheet, st) in enumerate(self.steps.items(), 1):
            counts, result = self._counts(st["rows"]), self._result(st)
            for s in STATUSES:
                totals[s] += counts[s]
            ov.append([n, sheet, result, len(st["rows"])] + [counts[s] for s in STATUSES]
                      + [round(st["secs"], 1), st["note"]])
            ov.cell(ov.max_row, 3).fill = PatternFill("solid", fgColor=FILLS.get(result.split()[0], "FFFFFF"))
            if st["result"] == "SKIPPED":
                continue
            ws = wb.create_sheet(_sheet_name(sheet, used))
            ws.append(COLUMNS)
            for r in st["rows"]:
                ws.append([r[k] for k in COLUMNS])
                ws.cell(ws.max_row, 5).fill = PatternFill("solid", fgColor=FILLS.get(r["Status"], "FFFFFF"))
                if r["Status"] in ("FAIL", "ERROR"):
                    bugs.append((sheet, r))
                if r["Screenshot"]:
                    back.setdefault(os.path.basename(r["Screenshot"]), (ws.title, ws.max_row, r))
            self._style(ws, Alignment, Font)
            for cell in ws["G"][1:]:
                self._link(cell, shot_rows, Font)
        ov.append(["", "TOTAL", "", sum(totals.values())] + [totals[s] for s in STATUSES] + ["", ""])
        for cell in ov[head_row] + ov[ov.max_row]:
            cell.font = Font(bold=True)
        b = wb.create_sheet("Bugs")
        b.append(BUG_COLUMNS)
        for n, (sheet, r) in enumerate(bugs, 1):
            b.append([f"SA-RUN-{n:03d}", "Stock Audit", f"{sheet} — {r['Group']}", r["Check"],
                      getattr(cfg, "environments", "QA"), "Major", "Medium",
                      f"1. User is logged in.\n2. Audit {self.audit} exists.",
                      f"1. Audit.py run, step '{sheet}'.\n2. Check: {r['Group']} > {r['Check']}.",
                      r["Expected"], r["Actual"] + (f"\n{r['Finding']}" if r["Finding"] else ""),
                      "Always", "New", r["Screenshot"]])
        self._style(b, Alignment, Font)
        for cell in b["N"][1:]:
            self._link(cell, shot_rows, Font)

        # Screenshots: file name (+ the check it belongs to, linked back), image below it
        attached_in = []                # (file, where) for the Overview
        if shot_rows:
            sh = wb.create_sheet("Screenshots")
            used.add("screenshots")
            sh.column_dimensions["A"].width = 45
            sh.column_dimensions["B"].width = 90
            for a in self.attached:
                if a["kind"] != "image":
                    continue
                row = shot_rows[a["file"]]
                sh.cell(row, 1, a["file"]).font = Font(bold=True)
                if a["file"] in back:
                    title, at, r = back[a["file"]]
                    self._goto(sh.cell(row, 2, f"{r['Status']}: {title} > {r['Group']} > {r['Check']}"), title, at)
                img = XLImage(io.BytesIO(a["data"]))
                w, h = a["size"]
                scale = min(1.0, SHOT_WIDTH / w)
                img.width, img.height = int(w * scale), int(h * scale)
                sh.add_image(img, f"A{row + 1}")
                attached_in.append((a["file"], f"Screenshots!A{row}"))

        # Excel files: every sheet copied (values) into its own sheet
        for a in self.attached:
            if a["kind"] != "table":
                continue
            label, titles = _short(os.path.splitext(a["file"])[0]), []
            for name, rows in a["data"]:
                ws = wb.create_sheet(_sheet_name(label if len(a["data"]) == 1 else f"{label} - {name}", used))
                for values in rows:
                    ws.append(values)
                self._style(ws, Alignment, Font, header=False)
                titles.append(ws.title)
            attached_in.append((a["file"], ", ".join(titles)))

        if attached_in:
            ov.append([])
            ov.append(["", "Attached file", "In sheet"])
            for cell in ov[ov.max_row]:
                cell.font = Font(bold=True)
            for f, where in attached_in:
                ov.append(["", f, where])
        # the app's downloads (Export Excel, PDFs) stay separate files: list them, a click opens the file
        embedded = {a["file"] for a in self.attached}
        separate = sorted(f for f in os.listdir(self.folder)
                          if f not in embedded and not f.startswith((self.name, "~$"))
                          and os.path.isfile(os.path.join(self.folder, f)))
        if separate:
            ov.append([])
            ov.append(["", "Separate file (in this folder)", "Opens"])
            for cell in ov[ov.max_row]:
                cell.font = Font(bold=True)
            for f in separate:
                ov.append(["", f, "click the file name"])
                cell = ov.cell(ov.max_row, 2)
                cell.hyperlink = f
                cell.font = Font(color="0563C1", underline="single")
        self._style(ov, Alignment, Font, header=False)
        path = os.path.join(self.folder, f"{self.name}.xlsx")
        try:
            wb.save(path)
        except PermissionError:          # the workbook is open in Excel: save next to it
            path = os.path.join(self.folder, f"{self.name}_{datetime.now():%H%M%S}.xlsx")
            wb.save(path)
        # Saved: the copied files are in the workbook now, take them out of the folder
        for a in self.attached:
            if a.get("path"):
                try:
                    os.remove(a["path"])
                    a["path"] = None
                except OSError:
                    pass
        print("\n" + "=" * 70 + f"\n  RUN REPORT — {self.audit}\n" + "=" * 70)
        for sheet, st in self.steps.items():
            print(f"  {self._result(st):<13} {sheet:<22} {len(st['rows'])} check(s)  {st['note']}")
        print(f"  {totals}   bugs: {len(bugs)}   attached: {len(attached_in)} file(s)\n  report: {path}")
        return path

    @staticmethod
    def _style(sheet, Alignment, Font, header=True):
        if header:
            for cell in sheet[1]:
                cell.font = Font(bold=True)
            sheet.freeze_panes = "A2"
        for col in sheet.columns:
            width = max(len(str(x.value or "")) for x in col) + 2
            sheet.column_dimensions[col[0].column_letter].width = min(max(8, width), 70)
            for x in col:
                x.alignment = Alignment(wrap_text=True, vertical="top")


# ── helpers for the modules ───────────────────────────────
def _report(config):
    try:
        return getattr(config, "run_report", None)
    except Exception:
        return None


def record(config, group, check, ok, expected="", actual="", status=None, finding="", screenshot=""):
    """Add one check to the running step's sheet (nothing without a RunReport)."""
    rep = _report(config)
    if rep is not None:
        rep.add(group, check, ok, expected, actual, status=status, finding=finding, screenshot=screenshot)


def record_rows(config, rows):
    """Add rows with the COLUMNS keys (e.g. A_audit_Summary _UIChecks rows) to the running step's sheet."""
    rep = _report(config)
    if rep is not None:
        rep.extend(rows)


def attach_file(config, path):
    """Copy this Excel file into the run workbook (a sheet per sheet) and remove it from the folder when the
    workbook is written. Excel files not registered here (the app's downloads) stay separate files."""
    rep = _report(config)
    if rep is not None:
        rep.embed_tables.add(os.path.basename(path))


def save_to_run_report(config, rows):
    """In an Audit.py run: add rows to the running step's sheet and return the run workbook's path, so the
    module writes no workbook of its own. Run on its own (no RunReport): None, the module writes its own."""
    rep = _report(config)
    if rep is None:
        return None
    rep.extend(rows)
    return os.path.join(rep.folder, f"{rep.name}.xlsx")


def run_files(config, name):
    """(folder, file-name prefix) for a module's files (downloads, PDFs, screenshots).
    In an Audit.py run: the run folder itself and "<name>_" (no subfolders; the prefix keeps e.g. the Summary
    and History downloads apart). Run on its own: a new <e2e_output_dir>/<name>_<audit>_<MMDD_HHMMSS> folder
    and no prefix. The folder is not created here."""
    rep = _report(config)
    if rep is not None:
        return rep.folder, f"{_safe(name)}_"
    base = getattr(config, "e2e_output_dir", None) or os.getcwd()
    audit = _safe(getattr(config, "ap_audit_name", ""))
    return os.path.join(base, f"{name}_{audit}_{datetime.now():%m%d_%H%M%S}"), ""
