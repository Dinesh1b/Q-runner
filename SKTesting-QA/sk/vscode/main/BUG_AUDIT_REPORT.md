# Q-Audit Runner — Bug Audit Report

**Date:** 2026-10-19
**Scope:** `sk/vscode/main`: `frontend-angular/`, `backend/` (Flask + runner), the workflow packages (`audit/`, `Q_audits/`, `inventory/`, `login/`), `modules.json`. Also `../../../playwright-tester/` and the legacy `frontend/`.

---

## Executive summary

**Project health: fair after the fixes. Two serious security issues are still open (OPEN-01, OPEN-02).**
- The core workflow now holds together. Module selection is enforced end to end, a failing module no longer kills the whole run, the run/stop state can't get stuck, and every build and test check passes.
- No Python test suite existed before this audit. The Angular app had a single smoke test.

| | Count |
|---|---|
| Issues identified | 43 |
| Confirmed bugs fixed | 24 |
| Confirmed, not fixed (needs your decision or larger work) | 17 |
| Unverified (suspected, not reproduced) | 2 |

**What was done**
- Every fix is minimal and targeted. The UI, CSS, API routes and response shapes are preserved.
- The legacy `frontend/` folder (old vanilla-JS UI, 21 files) was **removed** after the audit, at your request. Nothing executed it: the only reference was an unused template-folder fallback in `backend/app.py`, which now always points at the Angular build. To restore it: `git checkout -- SKTesting-QA/sk/vscode/main/frontend` (before committing the removal).

**Decisions taken with you**
- A failing module is now recorded and the run **continues** with the next module.
- `/dev/otp` is left as is.
- Hardcoded credentials are reported, not changed.

**Before you test:** the Flask server that was running on port 5000 during the audit (PID 14972) was started before these fixes. **Restart it** to pick up the backend changes.

---

## Architecture (verified)

| Part | Location | Notes |
|---|---|---|
| Angular 19 SPA | `frontend-angular/` | Lazy routes, signal stores. Dev: `npm start`, which proxies `/api /auth /run /stop /stream /history /upload …` to `:5000`. Prod build goes to `dist/frontend-angular/browser` and is served by Flask. |
| Flask backend | `backend/app.py` + `blueprints/` | `python backend/app.py` on port 5000 (`FLASK_PORT`). SQLite in `backend/data/`. |
| Run pipeline | `POST /run` → `services/execution_engine.execute_run` → `services/config_builder.build_config_py` → subprocess `backend/runner.py` | The runner loads the generated Config and calls `backend/workflows/*`, which re-export the functions in `audit/`, `Q_audits/` and `inventory/`. |
| Module registry | `modules.json` | 16 modules in 3 groups. Read by the backend (`models/module_registry.py`, `/api/modules`) and the frontend. |
| playwright-tester | `SKTesting-QA/playwright-tester/` | A separate TypeScript Playwright suite that targets the external STAGING site. |
| Legacy UI | `frontend/` | Removed (see above). Only `frontend-angular/` is executed. |

---

## Fixed bugs

Unless a row says otherwise, **Verified** means covered by a new regression test that passes.

| ID | Pri | Area | File / function | Repro → expected / actual | Root cause | Fix | Regression test | Status |
|---|---|---|---|---|---|---|---|---|
| BUG-01 | P0 | Backend / security | `services/config_builder.py` `s()`, `p()`, numeric fields | A password or field containing `"` or `\`, or a blank number. Expected: a valid Config. Actual: SyntaxError (the run dies), or **arbitrary Python executed** by `runner.py` (`exec_module`). | Values were wrapped in `"…"` with no escaping; numeric fields were inserted raw. | Strings are emitted with `repr()`. A new `n()` helper writes numbers as numeric literals (int or float) and falls back to the default for blank or invalid input. | `test_config_builder.py` (7 tests) | Verified |
| BUG-02 | P1 | Backend | `blueprints/runner.py` `run_route` | A non-JSON or invalid `/run` body. Expected: 400. Actual: an exception, and `running` stays True, so **every later run returns 409** until Stop. | The lock was set before parsing, and errors were never handled. | Parse with `get_json(silent=True)` and validate it is an object; wrap `execute_run`, release the lock on any error, and return 400/500 JSON. | `test_api.py::test_run_rejects_non_json…`, `test_run_lock_is_released…` | Verified |
| BUG-03 | P1 | Runner | `config_builder.py` template | Enable **Auditor 2 Table** (idx 10). Expected: it runs. Actual: silently skipped, yet the run reports success. | `modules.json` uses the flag `run_A_as_table`, but the generated Config only had `run_A_SA_table`. | The template emits `run_A_as_table` as well. | `test_auditor2_table_flag_matches_modules_json` | Verified |
| BUG-04 | P1 | Runner | `backend/runner.py` `main()`; `audit/A_audit_Summary.py` | One module fails, or `A_audit_Summary` finishes. Expected: the remaining modules run. Actual: the run ends. `A_audit_Summary` **always** called `sys.exit()`, even on success. | No error handling per module, plus a `sys.exit` inside a workflow. | Each module runs in `_run_isolated()`: an exception, `sys.exit(≠0)` or a `False` return marks FAILED; the next module gets a fresh login; a PASSED/FAILED/SKIPPED summary is printed; exit 1 if anything failed. `A_audit_Summary` now returns its result, like `Q_audit_Summary`. Login is lazy, inside the `try/finally`. Multi-process mode also continues after a failure. | `test_runner_isolation.py` (7 tests) | Verified (with mocked browser) |
| BUG-05 | P1 | Backend | `blueprints/runner.py` `/stop`, `/run`; `execution_engine.py` | Stop, then start a new run. Actual: the old run's thread cleared the new run's lock and process, and its `__ERROR__` ended the new run's stream. A Stop sent before the process was created killed nothing. Chrome child processes could stay alive. | Shared global state was not tied to a run, there was no cancel check, and only the parent process was terminated. | The logger and state setters are bound to the run ID, so stale runs are ignored. An `is_cancelled` check runs before and after each `Popen`. `kill_process_tree()` uses `taskkill /T /F` on Windows. | `test_stale_run_cannot_clear_newer_run_state` | Partly verified (the tree kill was not exercised with a live browser) |
| BUG-06 | P1 | Frontend | `state/run-session.store.ts`, `features/shell/shell.component.ts` | (a) **Clear** during a run left the UI stuck on "running" forever. (b) A dropped log stream did the same. (c) A stream closing without an end marker was shown as **success**. (d) Stop produced both "failed" and "stopped". (e) Run or Re-run could start while a stop was in progress. | `clearSession` unsubscribed the stream but kept the status; error handling was missing or wrong; there was no single place that finishes a run. | Clear during a run only clears the log lines. Losing the stream marks the run failed with a message. `__ERROR__` while stopping counts as stopped. `finishRun` runs only once. A new `isActive` (running or stopping) blocks starting a run. The Re-run buttons have the empty-queue guard. | tsc and build only | Fixed, no unit test (manual UI check recommended) |
| BUG-07 | P1 | Build / runtime | No dependency manifest; project `.venv` | `GET /api/modules` returned **500** in dev. Reproduced: under `.venv`, `create_app()` fails with `ModuleNotFoundError: openpyxl` (`blueprints/uploads.py:10`), so the backend never starts and the Angular dev proxy turns the failed connection into a 500. The handler itself is fine: it returns 200 under the system Python install. | `.venv` lacks openpyxl, pandas, pytz, argon2-cffi, pyautogui and pytest, and no requirements file existed. | Added `backend/requirements.txt` with the versions known to work. | `test_api_modules_returns_registry`; live `GET /api/modules` → 200 | Root cause verified. **You still need to run** `.venv\Scripts\pip install -r backend/requirements.txt` |
| BUG-08 | P2 | Backend | `execute_run` | Run with no module enabled. Expected: rejected. Actual: Chrome launched and logged in, then "Run completed successfully". | Fell back to `total=1`. | Raises `NoModulesEnabled`, which `/run` returns as a 400 with a message the UI shows. | `test_no_enabled_modules_is_rejected`, API tests | Verified |
| BUG-09 | P2 | Integration | `run-config.store.ts` `buildRunConfig` | Set Audit Plan frequency to Weekly. Actual: the backend always used `one-time`. | The payload key was `Frequency`; the backend reads `frequency`. | Renamed the key. | Spec `run payload…`, `test_frequency_is_written` | Verified |
| BUG-10 | P2 | Runner / UI | `pages/login_page.py` `_launch_browser`; `setup.component.ts` | Choose "WebKit / Safari". Actual: `ValueError`, run crashed. Edge was supported by the backend but not offered. | The browser branch was missing. | Added a WebKit launch branch and an **Edge** option to the dropdown (nothing removed). | — | Fixed; WebKit needs `python -m playwright install webkit` (not run) |
| BUG-11 | P2 | Frontend | `run-config.store.ts` | Enter an audited quantity of 0. Actual: 10 was sent. | `x \|\| 10` | Changed to `?? 10` for `audited_qty1/2`. | `test_zero_quantity_is_preserved` (backend) | Verified |
| BUG-12 | P2 | Backend | `execute_run` | Sub-flags sent as strings, such as `"run_timezone":"false"` from JSON imports. Actual: treated as ON for module selection, so what was reported and what ran disagreed. The legacy `run_locatio_setup` was remapped *after* coercion. | Only registry flags were coerced. | The idx-6 sub-flags are coerced too, and the legacy key is remapped first. | `test_string_sub_flags_are_coerced`, `test_legacy_location_setup_key_is_honoured` | Verified |
| BUG-13 | P2 | Runner | `runner.py` `ensure_session` | An account with several companies. Actual: `ValueError("Multiple companies found but no company_name…")`. | `company_name` was generated but never passed to `login()`. | It is passed now. | `test_main_continues…` asserts it | Verified |
| BUG-14 | P2 | Config | `backend/Config.py` (static or CLI fallback) | Running `runner.py` without a generated config: Auditor 2 SA and Location Setup could never run. | `run_stock_audit` appeared twice (the second should be `run_stock_audit2`); typo `run_locatio_setup`. | Corrected both names. Earlier this session `run_Q_audit`, `run_q_setting` and `MODULE_RUN_ORDER` were also reset to OFF/empty. | py_compile | Verified |
| BUG-15 | P2 | Backend / DB | `services/db.py` | A run fails or is stopped. Actual: no history row, because `db_finish_run` only updated rows. Finishing also overwrote every step's status. | No row was written when a run started. | `db_start_run()` writes a "Run" row; steps are closed when recorded; finishing updates only the Run row (and inserts it if missing). | Live `/history` 200 | Fixed; DB writes not unit-tested |
| BUG-16 | P2 | Frontend | `excel-uploader.component.ts` `handleFile` | Upload an Excel file. Actual: the file was uploaded twice when inspect failed; "✓ UPLOADED" showed before (or without) a successful upload; upload errors were ignored, so the run sent an empty path; inspect errors were hidden. | Duplicated upload calls; the badge depended on the file name, not the result. | One upload with an error handler; a new `uploaded` signal drives the badge (with an "UPLOADING…" state); inspect `errors[]` are displayed. | tsc and build | Fixed, no unit test |
| BUG-17 | P2 | Runner | `login_page.py` `login()` | Login fails (bad credentials or a page change). Actual: the browser window it opened stayed open. | No cleanup on error. | Close the browser and re-raise. | — | Fixed (code review) |
| BUG-18 | P2 | Module toggles | `module-registry.store.ts`, `execution.component.ts`, `json-import.service.ts`, `execution_engine.py` | **Mandatory rules D1–D8.** Before: turning a group ON enabled all its modules; expanding a group enabled it; clicking a module turned its group ON; `Config.py` had defaults set to ON; the backend didn't enforce groups. | Automatic defaults. | The group ON/OFF rules described below. | `module-registry.store.spec.ts` (8 tests), `test_group_module_matrix` and 4 related tests | Verified |
| BUG-19 | P3 | Backend | `/stream`, `logger.py` | A client still connected when a new run starts received nothing more. | The read index into the buffer wasn't reset when the buffer was cleared. | A reset counter (`generation()`); the stream restarts from line 0. | Code review | Fixed |
| BUG-20 | P3 | Frontend | `shell.component.ts` | Each time the shell was rebuilt, another `navigate-tab` window listener was added (leak). | No `ngOnDestroy`. | The listener is removed on destroy. | build | Fixed |
| BUG-21 | P3 | Frontend | `auth.service.ts` | Login and signup spinners never showed, so a double submit was possible. | `isLoading` was only set by `/auth/me`. | `withLoading()` (`defer` + `finalize`) wraps the auth POSTs, so the existing bindings now work. | build | Fixed |
| BUG-22 | P3 | Runner | `Q_audits/Q_setting.py:2` | `from turtle import pd` loaded tkinter and fails on Python installs without Tk. | Stray import (immediately shadowed by pandas). | Removed. | py_compile, workflow resolution | Verified |
| BUG-23 | P3 | Frontend | `run-session.store.ts` | The backend's `init` JSON line was printed raw; the step text never changed in single-process mode. | Only `progress` packets and `[STEP]` lines were parsed. | `init` is rendered as "Modules to run (N): …", and `Running module index: N (Name)` updates the step text. | build | Fixed |
| BUG-24 | P3 | Frontend | `shell.component.ts` error banner | The "✕ Stop" button in the error banner did nothing (it only shows after a failure). | `stopRun` returns early when nothing is running. | The button is shown only while a run is active. | build | Fixed |

### Module toggle rules (section D) — final behaviour
1. **Group OFF means none of its modules run.**
   - The UI blocks module switches while the group is OFF.
   - Turning a group OFF clears its modules.
   - The backend `_disable_modules_in_off_groups()` forces off every module in an OFF group (including the Audit Plan sub-flags), whatever the payload says.
2. **Group ON means its modules stay OFF** until the user enables them.
3. **Manual enablement only.**
   - Expanding a group, clicking a module and "Select All" never enable modules.
   - Select All turns groups ON only.
   - JSON import can't enable a module in an OFF group; it reports it as skipped.
4. **No automatic defaults:** `modules.json` has none, the static `Config.py` defaults are all OFF, and nothing is saved in localStorage.
5. **Consistent state:** the UI (`activeModules`), the payload (`grp && mod`), the backend gate and the runner (`_is_enabled`) all agree. Tested in both the spec and pytest.
6. **Disabled modules are skipped** (reported as SKIPPED in the runner summary) without affecting enabled ones.
7. **Enforced in the backend as well as the UI** (rule 1).
8. **Contradictory input is handled safely:** a non-dict payload gives 400, string booleans are coerced, nothing enabled gives 400, and an enabled module in an OFF group gives 400 if nothing else is enabled.

---

## Confirmed issues not fixed

| ID | Pri | Issue | Evidence | Why not fixed / recommendation |
|---|---|---|---|---|
| OPEN-01 | **P0** | `/dev/otp` is unauthenticated and returns the latest OTP for **any** account. Calling forgot-password and then `/dev/otp` lets anyone take over that account's password. OTPs are also printed to stdout. | `blueprints/auth.py:36-42`, `services/auth_service.py:102,201` | Kept at your request. Recommendation: enable it only when `DEV_MODE=1`, or bind the server to `127.0.0.1`. |
| OPEN-02 | **P0/P1** | No route checks the session (`/run`, `/stop`, `/upload`, `/history`). `SKIP_AUTH` defaults to `true`, `CORS(app)` allows every origin, and the server listens on `0.0.0.0`. Anyone on the network can start automation. | `app.py:47-51,93`; no `before_request` / `login_required` | Changing auth behaviour needs your sign-off. Recommendation: add a `login_required` check on run and upload routes, restrict CORS, and default to `127.0.0.1`. |
| OPEN-03 | P1 | Plaintext credentials are committed in `pages/login_page.py:4-25` (4 environments), `Config.py:154-155` and `playwright-tester/tests/helpers.ts:3-6`. Generated runtime configs with passwords are left in `%TEMP%\qaudit_runner\`. If `email2` is empty, Auditor 2 silently logs in as the default account. | listed | Report only, at your request. **Rotate these passwords**, move them to environment variables, and delete the runtime configs after each run. |
| OPEN-04 | P2 | JSON **export** (flat RunConfig) and **import** (nested `project/execution/modules`) use different formats, so re-importing an export does nothing. `public/sample_config.json` keys don't match either. The export contains plaintext passwords. | `setup.component.ts:246-253`, `json-import.service.ts` | Changing the format is a design decision. Recommendation: make import accept the flat format and leave passwords out of exports. |
| OPEN-05 | P2 | UI fields sent but never read by the backend: `ls_zones/aisles/bays/levels` (`inventory/location.py` uses a hardcoded `Config`), `ap_audit_name_adhoc`, `qs_sheet`. | `config_builder.py` doesn't read them | Each needs wiring through the workflow code; not a minimal fix. |
| OPEN-06 | P2 | Audit Plan (idx 6) with `Audit_mode=Ad_hoc` runs Ad-hoc even when only the create or timezone flags are set. `Audit_plan` with only the ad-hoc flag does nothing and reports success. | `runner.py` `run_create_audit` | The UI already filters these flags by mode; only a hand-written Config hits this. |
| OPEN-07 | P2 | Some workflows swallow validation failures and so report PASSED: `Q/A_as_table` print errors and never raise, `Q/A_Recently_audit` catch and print, and `timezone()` returns False, which is ignored. | see audit notes | Needs a decision per workflow on what counts as failure. The runner now treats `return False` as failed, so these workflows only need to return False. |
| OPEN-08 | P2 | The Excel uploader forgets the selected file when you switch modules (the stored path is kept). m0 and m7 share `storageKey="OA_EXCEL"`. | `execution.component.ts` `@switch` | Low risk; needs a UX decision. |
| OPEN-09 | P2 | The Ongoing Audit mapping dropdown shows "Random" while the payload uses the m0/m6 mapping type. | `m7-ongoing-audit.component.ts:147`, `run-config.store.ts:241` | Needs a decision on which control wins. |
| OPEN-10 | P3 | Hardcoded waits, `slow_mo=200` and `headless=False` everywhere. `Q_SA.py:52,81` call `wait_for_timeout(0.08)` with seconds where milliseconds are expected. | grep counts in the audit | Changing timing affects the real automation and needs live testing. |
| OPEN-11 | P3 | There is no live browser stream: `/video_feed` and `/browser_status` aren't implemented (`blueprints/pages.py:28-31`). The legacy UI still polls them. | | A feature gap, not a regression. |
| OPEN-12 | P3 | Reloading the page mid-run loses the run, because there is no status endpoint; the next Run gets a 409 until Stop. | | Needs a new `GET /status` endpoint. |
| OPEN-13 | P3 | Auth details: if `/auth/me` fails, the guards get inconsistent state; Logout appears to do nothing while `SKIP_AUTH` is on; the dev OTP toast reappears every 4 s. | `auth.service.ts:43-47`, `auth.component.ts:856` | Tied to OPEN-01 and OPEN-02. |
| OPEN-14 | P3 | An empty Excel path falls back to `C:/Users/HP/Documents/input/main_qexcel.xlsx`, a path from another machine. | `config_builder.py` `p()` | Kept so behaviour doesn't change. Recommendation: fail fast with a clear message. |
| OPEN-15 | P3 | In multi-process mode (`QA_RUNNER_SINGLE_PROCESS=0`), failures are detected by matching text in stdout. | `execution_engine.py` | Now mostly backed by the exit code (BUG-04). |
| OPEN-16 | P3 | `reportlab` is imported by `backend/tools/pdf_generator.py` but isn't installed anywhere. | | Not on the runtime path; it was left out of `requirements.txt` on purpose. |
| OPEN-17 | P3 | Several workflows call `sys.exit()` when the Excel file or a column is missing (`Auditor_1/2.py`, `Q_SA*.py`, `Item_import_add.py`). | | Mitigated: BUG-04 isolates these to the failing module. |

## Unverified

| ID | Issue | Note |
|---|---|---|
| UNV-01 | `/stream` threads may leak when an idle client disconnects before an end marker. | Not reproduced. The generator only notices on its next `yield`. |
| UNV-02 | The sheet `<select>` may show the wrong option when `default_sheet` isn't the first sheet (`[value]` bound before the `@for` options exist). | Not reproduced in a browser. |

---

## Validation results

| Check | Result | Evidence |
|---|---|---|
| Angular TypeScript | **Pass** | `npx tsc --noEmit -p tsconfig.app.json` and `-p tsconfig.spec.json`: no errors |
| Angular build | **Pass** | `npx ng build` (production): "Application bundle generation complete. [5.7 s]" into `dist/frontend-angular` |
| Angular unit tests | **Pass** | `npx ng test --watch=false --browsers=ChromeHeadless`: `TOTAL: 9 SUCCESS` (8 new module-toggle specs and the existing app spec) |
| Frontend lint | **Not configured** | There is no `lint` target in `angular.json` or `package.json` and no ESLint config |
| Backend tests | **Pass** | `python -m pytest backend/tests`: `30 passed in 1.01s` (config builder 7, execution engine 11, API 5, runner isolation 7) |
| Python syntax | **Pass** | `py_compile` on all 99 `.py` files in backend, audit, Q_audits, inventory and login: 0 failures |
| Workflow imports | **Pass** | All 18 workflow references in `modules.json` (16 plus the ad-hoc and update variants) resolve |
| Backend self-check | **Pass** | `python backend/_verify.py`: "ALL CHECKS PASSED!" |
| API integration | **Pass** | Fresh server on port 5055: `GET /api/modules` 200 (3424 B), `/auth/me` 200, `/history` 200, `/` 200 (SPA); `POST /run` with a text body → 400; with nothing enabled → 400; with the module's group OFF → 400 "No modules enabled". No run against a real environment was started. |
| `.venv` startup | **Fail → root cause found** | `.venv\Scripts\python` `create_app()` raises `ModuleNotFoundError: No module named 'openpyxl'`. Fix: `pip install -r backend/requirements.txt` (not run, because it changes your environment) |
| Playwright tests (`playwright-tester`) | **Blocked** | The last recorded run failed with `ERR_INVALID_PACKAGE_CONFIG …G:\My Drive\vs code\playwright-tester\node_modules\…` (dependencies installed on another machine). The suite targets the external STAGING site with real credentials and was not run without authorization. To unblock: `npm ci` in `playwright-tester`, then `npx playwright test`. |
| End-to-end automation run | **Blocked** | Needs live QA, STAGING or PRODUCTION accounts; not run without authorization. Runner behaviour was verified with a mocked browser instead (`test_runner_isolation.py`). |
| Regression (existing behaviour) | **Pass** | Existing spec, `_verify.py`, the production build and the API probes all pass; route paths and response shapes are unchanged (`/run` gained 400 responses for invalid input) |

---

## Files changed

**Backend and runner**
- `backend/blueprints/runner.py`
- `backend/services/execution_engine.py`
- `backend/services/config_builder.py`
- `backend/services/db.py`
- `backend/logger.py`
- `backend/runner.py`
- `backend/pages/login_page.py`
- `backend/Config.py`
- `audit/A_audit_Summary.py`
- `Q_audits/Q_setting.py`
- **New:** `backend/requirements.txt`, `backend/tests/` (conftest and 4 test modules)

**Frontend**
- `state/module-registry.store.ts`
- `state/run-config.store.ts`
- `state/run-session.store.ts`
- `features/shell/shell.component.ts`
- `features/execution/execution.component.ts`
- `features/execution/components/excel-uploader/excel-uploader.component.ts`
- `features/setup/setup.component.ts`
- `core/services/auth.service.ts`
- `core/services/json-import.service.ts`
- `styles/_ui.scss`
- **New:** `state/module-registry.store.spec.ts`

**Not touched by this audit:** these files already had uncommitted changes before the audit, which were left as they were: `backend/app.py`, `backend/shared/popup_handler.py`, `state/queue.store.ts`, `inventory/Inventory.py`, `inventory/create_group.py`.

## Side effects to be aware of
- **A run with a failing module now continues.** It still ends red ("Run finished with failures"), exits with code 1 and records `error` in history.
- **`/run` now returns 400** instead of starting Chrome when nothing is enabled.
- **Every login now sets a 45 s default Playwright timeout.** Before, only logins after a session switch did.
- **A failed module causes a fresh login before the next module,** which takes a few extra seconds per failure.
- **History rows now include a `Run` row per run,** and step rows have `ended_at` set.

## Recommended next steps
1. Restart the backend, then install `backend/requirements.txt` into `.venv`.
2. Decide on OPEN-01, OPEN-02 and OPEN-03 (security), then rotate the committed passwords.
3. Run one real end-to-end run on QA with two modules, one of them intentionally failing, to confirm the isolation and the Stop/Chrome cleanup with a live browser.
4. Reinstall `playwright-tester` dependencies and run the suite against STAGING once you authorize it.
5. Work through the P2 OPEN items (04, 05, 07), which affect test accuracy.
