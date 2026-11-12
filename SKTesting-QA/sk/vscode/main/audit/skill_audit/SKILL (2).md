---
name: audit-module
description: Stockount Audit module knowledge — audit types (Complete, Cycle, Partial, Investigation, Quick), audit plans, settings, stock sheet import, counting, summary, resolution (Accept / Recount / Investigate), post-audit stock adjustment and completion. Use when answering how-to or functional questions about audits, writing user-facing audit documentation or training material, or before changing any screen under src/app/home/audit/** or src/app/home/audit-plan/**.
---

# Audit module

Use this skill for two kinds of work:

1. **Functional questions and user-facing writing** — explaining how audits work,
   writing guides, release notes, training or help text.
2. **Code changes** in the audit screens — so the change matches how the
   module is meant to behave and the right documents are updated with it.

## Sources of truth

Read the one that matches the task before answering or editing:

| Need | Read |
| --- | --- |
| How a user does something; screen and button names | [`docs/audit-user-guide.md`](../../../docs/audit-user-guide.md) |
| What owners, contributors and auditors must be able to do | [`docs/audit-skills.md`](../../../docs/audit-skills.md) |
| Warehouse / LPN (Location) audits | [`docs/warehouse-lpn-module.md`](../../../docs/warehouse-lpn-module.md) → canonical `StockountAPI/docs/warehouse-lpn-module.md` |
| Post-audit stock adjustment | [`docs/audit-adjustment-module.md`](../../../docs/audit-adjustment-module.md) → canonical `StockountAPI/docs/audit-adjustment-module.md` |
| Stock sheet from an integration | [`docs/integration-hub-lifecycle.md`](../../../docs/integration-hub-lifecycle.md) |
| Audit type / method codes | `src/app/home/audit/shared/audit-types.constants.ts` |

If the guide and the code disagree, the code is right: say so and fix the guide in
the same change.

## The workflow in one view

Owner: **create → import stock sheet → (auditors count) → review summary →
resolve → adjust stock → complete**. A Quick Audit has no resolution step.

| Audit type | Created from | Notes |
| --- | --- | --- |
| Complete Count | Audit Plan | Whole item group; Static or Dynamic method |
| Cycle Count | Audit Plan | Segmented, scheduled (Weekly / Monthly / One-Time) |
| Partial Audit | Create Audit | Chosen items; always Static; Suggested Audits feed it |
| Investigation Audit | Create Audit | Items flagged *Investigate* in earlier audits |
| Quick Audit | Create Audit | Spot check; no resolution phase |

Counting methods: Static, Dynamic, and Location (Warehouse / LPN — only for item
groups with LPN tracking; it hides cross check, damaged qty, declaration and
location mapping).

Resolution actions: **Accept**, **Recount** (→ Recount Accepted or Investigate),
**Investigate**. Accepted and Recount Accepted lines must be settled by a stock
adjustment before **Complete Audit** is allowed. How it is settled depends on the
stock source: Stockount ledger → approve adjustment; connected ERP → approve and push
back; Excel sheet → Adjustment Report.

Roles: Administrator (all), Audit Owner (full control of a plan; several allowed),
Audit Contributor (view + resolution, cannot complete), Auditor (counts). An owner is
not automatically an auditor.

## Writing user-facing content

- Functional language only: no code, endpoints, table names or status codes.
- Use the on-screen labels exactly (e.g. **Manage Summary**, **Import stock sheet**,
  **Finish Audit**, **Complete Audit**).
- Follow the structure of the existing guides: Overview, Accessing, Functionality,
  Key Concepts, Best Practices, What's Next?
- Known open question: the practical difference between **Static** and **Dynamic**
  is not documented. Don't make one up; say it's unconfirmed.

## Changing audit code — rules that must not break

These come from `CLAUDE.md` and the canonical module documents. Breaking them gives
*plausible-looking but wrong* audit results, not a visible error.

1. **Never pre-fill a case's parent pallet from the stock sheet** in Location audits.
   Parentage is what the auditor observed.
2. **Blind count needs a loaded context.** A failed load must not render a confident
   "Blind count" state.
3. **Use `HidScannerService.getBackgroundScans()`**, not `getScans()`. Quantities are
   deltas, and the legacy stream double-fires.
4. **The adjustment source mode and confirmation sentence come from the server.**
   Never decide or compose them in the browser. Nothing on the adjustment screen is
   editable, and hiding Approve is not the control.
5. **There is one camera scanner** (`src/app/home/shared/camera-scan/`) and one
   barcode format list. Vary it by inputs; never fork it.
6. Counts are **cumulative**: saving 8 then 10 shows 18. Don't "fix" that in the UI.

When a change touches the Warehouse/LPN, adjustment, integration or connector
areas, update that module's canonical document in the same change. When it changes
what users see, update `docs/audit-user-guide.md` and, if a new competency is
involved, `docs/audit-skills.md`.
