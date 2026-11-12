# Audit Summary page — fields, values, quantities, filters and formulas

Read-only analysis of the Stockount web **Audit Summary** page, traced from the screen
through the API down to the database queries. Nothing in any repository was changed,
committed or pushed.

Prepared 9 Nov 2026 from the current checkouts of `stockount_UI` and `StockountAPI`
(the mobile layout of the same page is covered where it differs).

## Files

| File | Covers |
| --- | --- |
| [01-audit-details-and-kpis.md](./01-audit-details-and-kpis.md) | Header buttons, **Audit Details** tiles (Audit Name, Date & Time, Auditor(s), Group, Audit Type, Frequency – Mapping Type, Progress, Status), Warehouse (LPN) count tiles, Auditor Insights table and its Total row, visibility rules |
| [02-category-and-overall-variance.md](./02-category-and-overall-variance.md) | **Category Wise Variance** bar chart and **Overall Variance** doughnut: every series, tooltip and legend value, with a worked example |
| [03-complete-audit-report-and-completion.md](./03-complete-audit-report-and-completion.md) | **Complete Audit Report**: Summarize As modes, Stock / Audited / Damaged strip, 10 filter chips, search, 35 columns, 10 column filters, sorting, paging, Excel / PDF / image downloads — and the **Complete Audit** action as 10 numbered steps |

Every row in those files gives the field as labelled on screen, what it shows, its formula,
and its source as `UI file:line → API file:line → SQL/LINQ file:line`. Each file ends with
its own **Findings** section.

## Where the numbers come from

| Screen block | Endpoint | Computed in |
| --- | --- | --- |
| Audit Details, Progress, Status, charts | `GET /audit/getAuditSummary` | `Services/AuditSummaryService.cs` (C#/EF Core, no stored procedure) |
| Auditor Insights | auditor summary endpoint | `AuditService.GetAuditorSummary` (quick audits: `QuickAuditService`) |
| Warehouse (LPN) tiles | `/lpn/summary` | `LPNSummaryBuilder` |
| Complete Audit Report, chips, downloads | summary report endpoint | Raw SQL in `DTO/ReqDTO/Audit/AuditSummaryReportReqDTO.cs` |
| Complete Audit | status endpoint | `AuditSettingService.CompleteAudit` + adjustment gate + `AuditEmailService` |

## Formula quick reference

All quantities are in the item's primary (base) unit unless stated.

| Value | Formula |
| --- | --- |
| **Progress** (standard audit) | `min(100, (distinct counted item codes ÷ stock-sheet rows) × 25 + ((Σ Audited + Σ Damaged) ÷ Σ Stock) × 75)`; label rounded to whole % |
| Progress (quick audit) | Same weights, damaged **excluded**, rounded **up** before the 100 cap |
| Progress (per auditor) | Same weights over the auditor's assigned rows, damaged excluded |
| **Status** | N Not Started · S Stock Sheet Updated · I In Progress · K In Resolution · C Completed · A Auto Completed · E Expired · anything else "Unknown" |
| **Date & Time** | Audit **creation** time, stored UTC, shown in the company time zone |
| Chart price | Highest stock-sheet cost price for the item code |
| **Available Value** | `min(Stock, Audited) × cost` (per item code, netted across locations/batches/serials) |
| **Stock Loss** | `max(Stock − Audited, 0) × cost` (drawn positive) |
| **Excess Value** | `max(Audited − Stock, 0) × cost` |
| Overall Variance doughnut % | each value ÷ total stock-sheet value × 100, capped at 100 |
| Report **Variance Qty** | `Σ Audited − Σ Stock` (damaged not included); UOM mode uses Default-unit quantities |
| Report **Variance Value** | `(Audited − Stock) × price`, price = stock-sheet price → item's price elsewhere in the audit → branch cost price |
| Report **Audited Qty** | Sum of every auditor's counts (multi-count is cumulative); accepted recounts replace counts only when the audit is completed |
| Cross-check counts | Not used in the charts or Progress |

## Findings to act on first

Verified directly in the code while compiling this index (others are evidence-based
findings from the three files; see each file for line references):

1. **Report filters widen instead of narrowing** — *verified*. The search text and every
   ticked column-filter value are joined into one comma-separated string
   (`audit-summary.component.ts:621-640`), and the report SQL matches a row if **any** of
   them matches (`AuditSummaryReportReqDTO.cs:1234-1239`, `OR … IN STRING_SPLIT(…)`). Ticking
   a second filter adds rows; once any filter is ticked the search box effectively stops
   working; paging counts, totals and chip counts all describe the wider set.
2. **Progress can never reach full line-item credit when an item has several stock-sheet
   rows** — *verified*. `CalculateOverallProgress` (`AuditSummaryService.cs:433-464`)
   divides **distinct item codes** counted by the **number of stock-sheet rows** (one per
   location / batch / serial). The three Progress formulas (standard, quick, per auditor)
   also disagree on damaged quantity and rounding, and the label rounds where other figures
   truncate, so 99.5 % shows as "100% Completed".
3. **Charts net variances per item code** across locations and batches, so offsetting
   differences cancel out; uncounted items never appear as Stock Loss; counted items not on
   the stock sheet are valued at 0; the doughnut's slices do not match its own tooltip
   percentages (file 02).
4. **UOM summarize mode adds different units together** (boxes + bottles) in the Stock and
   Audited totals, and its columns mix as-entered, Default-unit and primary-unit figures
   (file 03).
5. **Download PDF fails on every chip except All** ("Audit summary data not found"), and
   **sorting by Declaration Note empties the table** (file 03).
6. **Complete Audit is not atomic**: the status is saved before the rest of the completion
   work, so a later failure shows an error on an audit that is already completed, and items
   marked Not Found are not rolled back if completion is refused. "Move all variance items to
   Investigation" skips existing resolution rows and never applies accepted recounts. The
   pending-recount check reads only the first 50 rows (file 03).
7. **Auditor Insights values** use today's item-master cost rather than the stock-sheet
   cost, can double-count items stocked in more than one location, and the Total row
   ignores the search filter (file 01).
8. **Status shows "Unknown" for archived audits**, and the ByStorage → "By Location"
   mapping label never applies because of a case-sensitive comparison (file 01).
9. **Warehouse (LPN) "Blind count" chip** shows while the summary is loading or after it
   fails — against invariant 2 of the Warehouse module (file 01).
10. **`/lpn/summary` does not check the audit belongs to the caller's company** (file 01) —
    worth a security review.

## Not on screen (dead code)

- "Overall LineItem Category Wise" and "Overall LineItem Stocks" charts are behind a flag
  that is never set and have no data source.
- The Overall Variance category dropdown (`pieCategory`) is commented out and its handler no
  longer exists.
