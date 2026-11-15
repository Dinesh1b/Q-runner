# Audit Summary — "Summarize As: Location" table: actual logic and formulas

Read-only analysis taken from the code. Nothing in any repository was changed, committed or
pushed.

**Code version:** `main`, 13 Nov 2026.

| Ref | File (on `main`) |
| --- | --- |
| **API** | StockountAPI `src/Stockount.Shared/DTO/ReqDTO/Audit/AuditSummaryReportReqDTO.cs` (commit `d34997cf`) — builds the report SQL |
| **SAVE** | StockountAPI `src/Stockount.Audit/AuditLineItemsService.cs` — how a count is stored |
| **ENT** | StockountAPI `src/Stockount.Data/Entities/Audit/AuditLineItems.cs` |
| **UI-H / UI-T** | stockount_UI `src/app/home/audit/audit-summary/audit-summary.component.html / .ts` (commit `05b9cc90c`) |
| **FMT** | stockount_UI `src/app/home/audit/shared/audit-number-format.util.ts` |

The report is built when Summarize As = `Location` is sent with `IsQuickAudit = false`. Quick
Audits use a separate query (`GetQuickAuditSummaryReports`) not covered here.

---

## 1. The two location fields

Each count (`AuditLineItems` row) stores two locations (ENT 29–45):

| Field | Meaning | How it is saved (SAVE 1904–1990) |
| --- | --- | --- |
| `AuditStockLocation` | **Where the auditor found/counted the item** — shown as **Audited Location** | The location chosen on the counting screen |
| `StockLocation` | **The item's stock-sheet location the count belongs to** — used to match the stock sheet; shown as **Stock Location** through the sheet | The server looks for a stock-sheet row for the same item (and same batch, for batch items) **at the found location**. If one exists, the stock location is saved; **if none exists it is saved as NULL** |
| `RowStockLocation` | The sheet row the count was opened from — display only, never used by this report | Always saved |

So a count made where the stock sheet lists the item **joins that sheet row**. A count made
anywhere else (a location the sheet doesn't list for the item, a blank location, or an item not
on the sheet) is saved with **no stock-location claim** and becomes its own row.

Exception: **Mark Not Found** (from the Complete Audit dialog, SAVE 1380–1475) saves zero
counts with both locations copied from the summary row ("Unassigned" turned back into blank).

---

## 2. How the rows are built

### 2.1 Stock-sheet side — `#SS_Aggregated` (API 1006–1022 with Location keys at 731–733)

```sql
SELECT ItemCode,
       ISNULL(NULLIF(StockLocation,''),'Unassigned') AS StockLocation,
       NULLIF(BatchNo,'')                           AS BatchNo,
       SUM(ISNULL(UOMQty, ISNULL(StockQty,0)))      AS SheetStockQty,  -- qty as entered
       SUM(ISNULL(StockQty,0))                      AS StockQty,       -- primary unit
       MAX(ISNULL(CostPrice,0))                     AS CostPrice
FROM StockSource
WHERE CompanyId=@CompanyId AND BranchId=@BranchId AND AuditId=@AuditId AND IsActive=1
GROUP BY ItemCode, StockLocation, NULLIF(BatchNo,'')
```

### 2.2 Count side — `#ALI_Aggregated` (API 1051–1080 with Location keys at 687–697)

```sql
SELECT ItemCode,
       NULLIF(StockLocation,'')                                AS StockLocation,
       ISNULL(NULLIF(AuditStockLocation,''),'Unassigned')      AS AuditStockLocation,
       NULLIF(BatchNo,'')                                      AS BatchNo,
       SUM(ISNULL(AuditedQty,0))  AS AuditedQty,     -- every count, every auditor
       SUM(ISNULL(DamagedQty,0))  AS DamagedQty,
       SUM(ISNULL(UOMQty, ISNULL(AuditedQty,0))) AS AuditedEnteredQty,
       MAX(UpdatedDate) AS AuditedDate, MAX(AuditorId) AS AuditorId,
       STRING_AGG(MediaLocation, ', ') AS MediaLocation, MAX(Coordinates) AS Coordinates,
       MAX(Reason) AS Reason, MAX(ProductionDate), MAX(ExpiryDate), MAX(Id1Name), MAX(Id2Name), MAX(Id3Name)
FROM AuditLineItems
WHERE CompanyId=@CompanyId AND BranchId=@BranchId AND AuditId=@AuditId AND IsActive=1
GROUP BY ItemCode, StockLocation, AuditStockLocation, NULLIF(BatchNo,''), IsActive
```

Repeat counts are cumulative: counting 8 and then 10 gives 18.

### 2.3 Join (API 1224–1227 with the condition at 719–726)

```sql
FROM #SS_Aggregated ss
FULL OUTER JOIN #ALI_Aggregated ali
  ON  ss.ItemCode = ali.ItemCode
  AND ISNULL(NULLIF(ss.StockLocation,'Unassigned'),'') = ISNULL(ali.StockLocation,'')
  AND (   ISNULL(NULLIF(ss.StockLocation,'Unassigned'),'') <> ''
       OR ISNULL(NULLIF(ali.AuditStockLocation,'Unassigned'),'') = '' )
  AND ISNULL(ss.BatchNo,'') = ISNULL(ali.BatchNo,'')
```

In words: a count meets a sheet row when the **item**, the **saved stock location** and the
**batch** are the same. A sheet row with no location ("Unassigned") is met only by a count whose
found location is also blank.

### 2.4 Grouping (API 1396–1400)

```sql
GROUP BY ss.StockLocation, ali.AuditStockLocation, COALESCE(ss.ItemCode, ali.ItemCode),
         COALESCE(ali.BatchNo, ss.BatchNo), ali.Id1Name, ali.Id2Name, ali.Id3Name,
         ss.StockQty, ali.AuditedQty, ali.DamagedQty, ali.MediaLocation, ali.ItemCode
```

**One row = item × stock-sheet location × found location × batch.**

### 2.5 The kinds of row this produces

| Case | Stock Location | Audited Location | Stock Qty | Audited Qty |
| --- | --- | --- | --- | --- |
| Counted at a location the sheet lists for the item | sheet location | same location | sheet qty | counted qty |
| On the sheet with no location, counted with no location | Unassigned | Unassigned | sheet qty | counted qty |
| Counted at a location the sheet does **not** list for the item | **blank** | found location | **0** | counted qty |
| Counted with no location, item has a located sheet row | **blank** | Unassigned | **0** | counted qty |
| Counted, item **not on the sheet at all** | **blank** | found location / Unassigned | **0** | counted qty |
| On the sheet, never counted | sheet location / Unassigned | **blank** | sheet qty | 0 |
| Batch item: counted batch not on the sheet at that location | **blank** | found location | **0** | counted qty |

---

## 3. Every column

Column order and visibility from UI-H 700–1080 (header) and 1140–1240 (body); values from the
API SELECT (API 1115–1222).

| Column | Shown when | Actual expression | Meaning / notes |
| --- | --- | --- | --- |
| **S.No** | always | `i + 1` | Position on the current page; restarts each page |
| **Item Code** | always | `COALESCE(ss.ItemCode, ali.ItemCode)` | |
| **Item Name** | always | `MAX(i.ItemName)` from the item master | Current name, not the name at import |
| **Category** | not Quick | `MAX(ic.CategoryName)` joined on item group + category, active categories only | Blank if the item has no active category |
| **Stock Location** | always | `MAX(ss.StockLocation)` | Sheet location; **"Unassigned"** when the sheet row has no location; **blank** when the row has no sheet side |
| **Audited Location** (filter title "AUDITED WAREHOUSE") | always | `MAX(ali.AuditStockLocation)`; screen applies `getUniqueLocations` (split on ",", trim, de-duplicate, join ", ") | Found location; **"Unassigned"** when the auditor gave none; **blank** when never counted |
| **UOM (Primary)** | always | First active primary UOM conversion of the item (`UomStructureChildId IS NULL`, by `SerialNumber`), else of the item group, else `Items.UOM`; text before any "(" (API 1262–1310) | Unit name for Stock / Audited / Variance |
| **Stock Quantity** | always | `ISNULL(ss.StockQty, 0)` | Primary unit; sum of the sheet rows for item × location × batch |
| **Audited Quantity** | always | `ISNULL(ali.AuditedQty, 0)` | Sum of every count for item × saved stock location × found location × batch, all auditors |
| **Variance** | always | `CASE WHEN ali.AuditedQty IS NOT NULL THEN ISNULL(ali.AuditedQty,0) - ISNULL(ss.StockQty,0) ELSE 0 END` (API 72, 1159–1164) | Audited − Stock. **A never-counted row shows 0** |
| **Variance Value** | always | `CASE WHEN ali.AuditedQty IS NOT NULL THEN (ISNULL(ali.AuditedQty,0) - ISNULL(ss.StockQty,0)) * COALESCE(MAX(ss.CostPrice), MAX(sc.CostPrice), MAX(ibd.CostPrice), 0) ELSE 0 END` (API 1165–1178) | Variance × price, always in the primary unit. Price order: this sheet row's highest cost → the item's highest sheet cost anywhere in the audit (`#SheetCost`, API 1035–1046) → branch cost price (`ItemBranchDetails`) → 0 |
| **Variance Type** | always | `CASE WHEN ali.AuditedQty IS NULL THEN '-' WHEN Audited > Stock THEN 'Positive' WHEN Audited < Stock THEN 'Negative' ELSE '-' END` (API 1179–1191) | Green for Positive, red for Negative (UI-H 1185) |
| **Batch No** | batch item groups | `COALESCE(ali.BatchNo, ss.BatchNo)` (API 707) | Counted batch, else the sheet batch |
| **Damaged Qty** | always | `ISNULL(ali.DamagedQty, 0)` | Not part of Variance |
| **Auditor** | always | `MAX(CONCAT(u.FirstName,' ',u.LastName))` of `MAX(AuditorId)` | One name only, even when several auditors' counts are added into the row |
| **Audited Date** | always | `MAX(ali.AuditedDate)` = latest `UpdatedDate` of the counts; shown `MM-dd-yy HH:mm` | Blank when never counted |
| **Cross Audited Qty** | not Quick | `SUM(ISNULL(cai.CrossAuditedQty,0))` | Σ `SubAuditItems.Qty` of active, non-voided **Cross Check** sub-audit items of the item (API 1228–1262) |
| **Cross Damaged Qty** | not Quick | `SUM(ISNULL(cai.CrossDamagedQty,0))` | Σ `SubAuditItems.DamagedQty`, same rows |
| **Declaration Note** | always | `ISNULL(MAX(ari.DeclarationNotes), MAX(ali.Reason))` (API 1202–1206) | Resolution declaration, else the auditor's reason |
| **Coordinates** | always | `MAX(ali.Coordinates)` | Geo-tag of a count |
| **Resolution Status** | not Quick, not Warehouse | `CASE WHEN rh.ItemCode IS NOT NULL THEN '' ELSE dbo.GetRecountStatus(MAX(ari.Action), MAX(ari.Status)) END` (API 1217–1222) | From `AuditResolutionItems` (active rows of the item) |
| **Remarks** | not Quick | `MAX(ari.Notes)` | Resolution remarks |
| **Audited Image** | always | `STRING_AGG(MediaLocation)`; icon when not empty | Opens the photo gallery |

Hidden in Location mode: Variance History, Production/Expiry Date, Serial IDs, Audited UOM,
Default UOM/Qty, Pallet/Case.

### Number display (FMT 25–71)

- Quantities: **truncated** (not rounded) to **4** decimals; values: truncated to **2** decimals.
- Trailing zeros dropped (`10.5000` → `10.5`, `3.0` → `3`); no thousands separator, no currency symbol.
- A null Variance Value shows "-" (UI-H 1183).

---

## 4. Filter chips

Badge counts run over the filtered result set (API 380–407); a chip's list adds a HAVING
clause (API 1443–1505).

| Chip | Badge count expression | List (HAVING) expression |
| --- | --- | --- |
| **All** | `COUNT_BIG(ItemCode)` | — |
| **Matched Line Item** | `ISNULL(AuditedQty,0) = ISNULL(StockQty,0)` | `ISNULL(ali.AuditedQty,0) = ISNULL(ss.StockQty,0)` |
| **Un Verified** | `StockQty > 0 AND ISNULL(AuditedQty,0) = 0 AND AuditorName blank` | `SUM(ISNULL(ali.AuditedQty,0)) = 0 AND AuditorName blank` |
| **Not Found** | `StockQty > 0 AND AuditedQty = 0 AND AuditorName not blank` | same |
| **Excess Line Item** | `ISNULL(StockQty,0) = 0 AND ISNULL(AuditedQty,0) > 0` | `MAX(ss.ItemCode) IS NULL` (row has no sheet side) |
| **Positive Variance** | `ISNULL(AuditedQty,0) > ISNULL(StockQty,0)` | same |
| **Negative Variance** | `AuditorName not blank AND ISNULL(AuditedQty,0) < ISNULL(StockQty,0)` | `ISNULL(ali.AuditedQty,0) < ISNULL(ss.StockQty,0) AND ali.AuditedQty IS NOT NULL` |
| **Location Conflict** | `ISNULL(AuditedQty,0) > 0 AND ISNULL(StockLocation,'') <> ISNULL(AuditedLocation,'')` | `ISNULL(ali.AuditedQty,0) > 0 AND ISNULL(MAX(ss.StockLocation),'') <> ISNULL(MAX(ali.AuditStockLocation),'')` |
| **Cross Checked Audit** | `ISNULL(CrossAuditedQty,0) > 0` | `MAX(ISNULL(cai.CrossAuditedQty,0)) > 0` |
| **Damaged** | `ISNULL(DamagedQty,0) > 0` | `ali.DamagedQty > 0` |

What lands in Location Conflict, by row kind (§2.5): every counted row whose Stock Location is
blank (counted off-sheet or not on the sheet), and a counted "Unassigned" sheet row only if the
found location differs. Rows counted at their own sheet location never do.

---

## 5. Summary tiles (Stock / Audited / Damaged) with the Qty | Value toggle

API 1510–1550; UI-H 620–656.

```sql
;WITH MarkedRows AS (
  SELECT t.*, ROW_NUMBER() OVER (PARTITION BY ItemCode, StockLocation, BatchNo ORDER BY (SELECT NULL)) AS rn
  FROM #TempAuditSummaryData t )
SELECT COUNT_BIG(ItemCode)                                   AS TotalCount,
       SUM(CASE WHEN rn = 1 THEN StockQty ELSE 0 END)        AS TotalStockQty,
       SUM(AuditedQty)                                       AS TotalAuditedQty,
       SUM(DamagedQty)                                       AS TotalDamagedQty,
       SUM(CASE WHEN rn = 1 THEN StockQty * CostPrice ELSE 0 END) AS StockValue,
       SUM(AuditedQty * CostPrice)                           AS AuditedValue,
       SUM(DamagedQty * CostPrice)                           AS DamagedValue
FROM MarkedRows
```

| Tile | Qty | Value |
| --- | --- | --- |
| Stock | `TotalStockQty` — each item × stock location × batch counted **once** | `StockValue` |
| Audited | `TotalAuditedQty` | `AuditedValue` |
| Damaged | `TotalDamagedQty` | `DamagedValue` |

All quantities are in the primary unit. Tiles follow the active search and column filters.

---

## 6. Search, column filters, sorting, paging

| Control | Actual logic |
| --- | --- |
| **Search** (Item Code / Item Name) | `COALESCE(ss.ItemCode, ali.ItemCode) LIKE '%'+text+'%' OR i.ItemName LIKE '%'+text+'%'` (API 1333–1335). Each keystroke reloads page 1 |
| **Column filters** | Category, Auditor, UOM, Variance Type, Audited Location, Declaration Note, Resolution Status, Remarks (+ Audited/Default UOM in UOM mode) — UI-T 199–211. Options come from a cache of loaded rows (UI-T 548–556) |
| Filter match | Exact value `IN (STRING_SPLIT(FilterValue, ','))` against: `ic.CategoryName`, auditor name, `displayUom.UomName`, default UOM name, `ali.AuditStockLocation`, `ari.Notes`, `ari.DeclarationNotes`, `ali.Reason`, `GetRecountStatus(...)`, computed Variance Type (API 1336–1372) |
| **How they combine** | The UI joins the search text and **all** ticked values of **all** columns into one comma-separated `FilterValue` (UI-T 624–642). The server keeps a row if **any** condition is true (OR). |
| **Sorting** | Server-side, by the clicked column; default `ORDER BY AuditedDate DESC` (API 1557), so counted rows come first, newest first, then never-counted rows |
| **Paging** | Server-side page of `#TempAuditSummaryData` |

---

## 7. Illustration (made-up data)

Item A: stock sheet has 10 at L1 and 10 at L2, cost 50. Auditor counts 7 at L1 and 3 at W9.
Item B is not on the sheet; 4 counted with no location; branch cost 20.

| Item | Stock Loc | Audited Loc | Stock | Audited | Variance | Variance Value | Type | Chips |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | L1 | L1 | 10 | 7 | −3 | −150 | Negative | Negative |
| A | (blank) | W9 | 0 | 3 | 3 | 150 (item's sheet cost) | Positive | Excess, Positive, Location Conflict |
| A | L2 | (blank) | 10 | 0 | 0 | 0 | - | Un Verified |
| B | (blank) | Unassigned | 0 | 4 | 4 | 80 (branch cost) | Positive | Excess, Positive, Location Conflict |

Tiles: Stock 20, Audited 14, Stock Value 1000, Audited Value 7 × 50 + 3 × 50 + 4 × 20 = 580.

---

## 8. Findings (from the code)

1. **Never-counted rows carry no variance.** Variance, Variance Value and Type are 0 / 0 / "-"
   until a count exists (API 72). A location nobody counted therefore does not appear in
   Negative Variance or in any Variance Value total — only under Un Verified. In the
   illustration, item A's real shortage at L2 (−10, −500) is invisible in the variance columns.
2. **A shortage and an excess of the same item at different places are separate rows.** Item A
   shows −3 at L1 and +3 at W9 with nothing linking them; the stock at L2 is not offset.
3. **Only one auditor is named per row** (`MAX(AuditorId)`), although Audited Quantity adds all
   auditors' counts.
4. **Search and column filters widen instead of narrowing** (§6). Ticking a second value adds
   rows; once any filter is ticked, the search text is only matched as an exact value, so typing
   in search effectively stops filtering. Chips and tiles follow the widened set.
5. **Sorting by Declaration Note fails.** The header sorts on `Reason` (UI-H 1031), but the result
   table has `DeclarationNote`, not `Reason`, so `ORDER BY Reason` errors and the table empties.
6. **Blank vs "Unassigned" mean different things.** Stock Location blank = no sheet side;
   "Unassigned" = sheet row without a location. Audited Location blank = never counted;
   "Unassigned" = counted without a location.
7. **Stock repeats only for counts that bypass the save check.** Normal saves null the stock
   location when the sheet doesn't list the item at the found location (SAVE 1904–1990), so
   one sheet row can't normally split across two found locations. Rows saved by other paths
   (older data, or Mark Not Found copying both locations) can still split; the Stock tile
   removes the duplicates (`rn = 1`), but each row's Variance is taken against the full Stock Qty.
8. **Excess rows are priced from the item's highest sheet cost, else the branch cost** — not the
   price of a specific sheet row.
9. **Accepted recounts are not reflected** in this table until the audit is completed (they are
   copied into the counts on completion — file 03).

## 9. Version differences

| Behaviour | `main` (documented) | `dev_env` and older copies |
| --- | --- | --- |
| Variance of a never-counted row | 0, type "-" | `0 − Stock`, type Negative |
| Location Conflict | requires Audited > 0 | any row whose locations differ, including never-counted rows |
| Batch in Location mode | one row per batch | one row per location; one batch shown |
