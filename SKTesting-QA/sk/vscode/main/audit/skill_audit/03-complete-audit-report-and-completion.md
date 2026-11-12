# Audit Summary page, part 3 of 3: the Complete Audit Report and the Complete Audit action

Scope: the **Complete Audit Report** section (summary page HTML lines 585–1232) and the
**Complete Audit** button (HTML lines 69–75). Audit Details, the KPI tiles and the
Category/Overall Variance charts are covered in parts 1 and 2.

Path abbreviations used below:

| Abbrev. | File |
|---|---|
| `HTML` | `/home/user/stockount_UI/src/app/home/audit/audit-summary/audit-summary.component.html` |
| `TS` | `/home/user/stockount_UI/src/app/home/audit/audit-summary/audit-summary.component.ts` |
| `MOB` | `/home/user/stockount_UI/src/app/home/audit/audit-summary/audit-summary-mobile/audit-summary-mobile.component.{ts,html}` |
| `FMT` | `/home/user/stockount_UI/src/app/home/audit/shared/audit-number-format.util.ts` |
| `PIPE` | `/home/user/stockount_UI/src/app/shared/decimal-format.pipe.ts` |
| `SQL` | `/home/user/StockountAPI/DTO/ReqDTO/Audit/AuditSummaryReportReqDTO.cs` (`GetAuditSummaryReports`, the dynamic T‑SQL behind the report) |
| `TMP` | `/home/user/StockountAPI/DTO/ReqDTO/Audit/AuditSqlTempTables.cs` |
| `SVC` | `/home/user/StockountAPI/Services/AuditService.cs` |
| `SET` | `/home/user/StockountAPI/Services/ControllerServices/AuditSettingService.cs` |
| `PDF` | `/home/user/StockountAPI/Services/ControllerServices/Audit/AuditSummaryDocumentService.cs` |
| `ADJ` | `/home/user/StockountAPI/Services/Audit/Adjustment/AuditAdjustmentService.cs` |
| `VAR` | `/home/user/StockountAPI/DTO/ReqDTO/Audit/AuditVarianceReqDTO.cs` |
| `INS` | `/home/user/StockountAPI/DTO/ReqDTO/Audit/VarianceRankingFiltersReqDTO.cs` (`GetInsightsWithCount`) |
| `ALIS` | `/home/user/StockountAPI/Services/AuditLineItemsService.cs` |
| `MAIL` | `/home/user/StockountAPI/Services/ControllerServices/Audit/AuditEmailService.cs` |

---

## 1. Data pipeline (applies to every field below)

**UI → API.** `TS getAllSummaryReport()` (TS 1552–1662) posts to
`POST /Audit/GetAuditSummaryReport` (`audit.service.ts:160`) with:

| Payload field | Value | Source |
|---|---|---|
| `AuditPlanId`, `AuditId` | from `parentData.auditObj` (or the quick-audit local data) | TS 1556–1557 |
| `BranchId` | `StorageKeysService.getBranchId()` | TS 728 |
| `SummaryType` | active filter chip (`activeBadge`, default `All`) | TS 1559 |
| `SummarizeAs` | `selectedSummarizeAs`; not sent for Quick Audit | TS 1572–1574 |
| `IsFiltersCount` | `true` on first load, after a Summarize As change, after an LPN reconcile | TS 463, 1547, 351 |
| `FilterValue` | search text **plus every ticked column-filter value from every column**, comma-joined into one string (`buildFilterValue`) | TS 619–639 |
| `pagenation` | `PageNo=currentPage`, `PageSize=pageSize` (25 default; options 25/50/100/200), `ColumnName=sortColumn`, `SortBy=sortDirection` | TS 106–109, 1564–1569 |

**API.** `AuditController.GetAuditSummaryReport` (Controllers/AuditController.cs:1428) →
`SVC GetAuditSummaryReport` (SVC 4491–4561): subscription check, reads the audit's
`ConfigurationName`, asks for result sets `TotalCount`, [`FiltersCount` when
`IsFiltersCount || SummaryType=="All"`], `ResultList`, and runs
`SQL GetAuditSummaryReports(companyId, ConfigurationName)`. Quick Audit runs
`GetQuickAuditSummaryReports` instead (§2.9).

**SQL shape** (one statement batch, all temp tables):

1. `#SS_Aggregated` — the stock sheet (`StockSource`, `IsActive=1`, this audit), grouped per mode
   (SQL 943–955):
   - `StockQty = SUM(ISNULL(StockQty,0))` — primary UOM (the import converts sheet qty × UOM factor before saving).
   - `SheetStockQty = SUM(ISNULL(UOMQty, ISNULL(StockQty,0)))` — as entered on the sheet.
   - `CostPrice = MAX(ISNULL(CostPrice,0))`.
2. `#ALI_Aggregated` — the counts (`AuditLineItems`, `IsActive=1`, this audit), grouped per mode
   (SQL 982–1015):
   - `AuditedQty = SUM(ISNULL(AuditedQty,0))` — **every active line from every auditor is summed** (multi-count is cumulative; there is no "last count wins").
   - `DamagedQty = SUM(ISNULL(DamagedQty,0))`; `AuditedEnteredQty = SUM(ISNULL(UOMQty, AuditedQty))`;
     `AuditedDate = MAX(UpdatedDate)`; `MediaLocation = STRING_AGG(MediaLocation, ', ')`;
     `Coordinates = MAX`; `AuditorId = MAX`; `Reason = MAX`.
3. `#TempAuditSummaryData` — `#SS_Aggregated FULL OUTER JOIN #ALI_Aggregated ON ItemCode {+ mode keys}`
   (SQL 1126–1130), left-joined to the Cross Check sub-audit ledger, `AuditResolutionItems`,
   items, UOM, cost fallbacks, category and user (SQL 1131–1231), filtered by `FilterValue`
   (SQL 1233–1285) and the Cycle Count rule, grouped per mode (SQL 1287–1338) and filtered by
   the chip's `HAVING` (SQL 1340–1386).
4. Totals result set (SQL 1407–1440), then `FiltersCount` (SQL 349–377), then the page
   `SELECT * FROM #TempAuditSummaryData ORDER BY … OFFSET/FETCH` (SQL 1443–1444; default order
   `AuditedDate DESC`, helper `Helpers/GeneralHelperService.cs:261–280`).

**Recount and cross-check precedence.** Nothing in this report reads recount quantities while
the audit is open: `AuditedQty` is always the sum of active `AuditLineItems`. Accepted recounts
only reach `AuditLineItems` when the audit is completed (`UpdateAuditLineItemsResolutions`, §3
step 9), which deactivates the item's lines and writes one new line carrying the recount
quantity (SVC 6470–6545). Cross Check quantities are shown in their own columns and never feed
Audited Qty or Variance.

**Cycle Count.** An item appears only if at least one of its rows has `AuditedQty > 0`
anywhere in the audit (`EXISTS #ALI_Aggregated … AuditedQty > 0`, SQL 95–102).

### 1.1 Summarize-as row grain (SQL 386–935, GROUP BY 1287–1338)

| Mode (dropdown value) | Shown for | One row per | Stock ↔ count join | Totals de-dup key (`totalsPartitionBy`) |
|---|---|---|---|---|
| Item | all non-Quick audits | ItemCode | ItemCode | ItemCode, Id1–3, BatchNo |
| Auditor | all non-Quick | ItemCode × AuditorId (uncounted items: one row, no auditor) | ItemCode | ItemCode, Id1–3, BatchNo |
| Location | all non-Quick | ItemCode × sheet location × found location | ItemCode + `ss.StockLocation = ali.StockLocation` (blank only joins "Unassigned" if found-location is blank too) (SQL 655–666) | ItemCode, StockLocation |
| UOM | all non-Quick | ItemCode | ItemCode (no UOM match) | ItemCode |
| Serial (`invType S`, default for serialized groups) | serialized groups | ItemCode × Batch × Id1–3 | ItemCode + Id1/Id2/Id3 (not BatchNo) (SQL 690–692) | ItemCode, Id1–3, BatchNo |
| Batch (default for batch groups) | batch groups | ItemCode × Batch × Id1–3 | ItemCode + BatchNo (SQL 800) | ItemCode, Id1–3, BatchNo |
| Pallet / Case (`LPN`, default for Warehouse) | Warehouse (`AuditMethodCode 'W'`) only | ItemCode × PalletId × CaseId (× VerificationLevel on the count side) | ItemCode + PalletId + CaseId (SQL 760–761) | ItemCode, PalletId, CaseId |

Dropdown list: `Item, Auditor, Location, UOM` (TS 266–269), `+ Serial` or `+ Batch` by item-group
type (TS 511–518); a Warehouse audit replaces the list with `Pallet / Case`, `Item` and
defaults to `LPN` (TS 505–510). Hidden for Quick Audit (HTML 590). Changing it resets the
chip to `All`, sets `IsFiltersCount=true` and reloads (TS 1542–1549) — it does **not** reset
the page number or the column filters.

---

## 2. Complete Audit Report

### 2.1 Header controls

| Field | What it shows | Formula / behaviour | Source |
|---|---|---|---|
| Title / subtitle | "Complete Audit Report — Summary Of The Latest Stock Audit" | static | HTML 588–589 |
| Summarize As | row grain (§1.1) | `onChangeSummarize` → reload | HTML 590–594, TS 1542 |
| Qty / Value toggle | switches the metric strip between quantities and values | `isTotalTypeQty` (default `true`), client only, no reload | HTML 598–603, TS 236 |

### 2.2 Metric strip (Stock / Audited / Damaged)

Bound to `allSummaryCount = resp.data.TotalCount[0]` (TS 1610). Computed over **all rows of
`#TempAuditSummaryData`**, i.e. after the search/column filters and the active chip's
`HAVING`, but before pagination (SQL 1407–1440). Displayed with `formatAuditQuantity`
(truncate to 4 dp, no rounding, no padding, no thousands separator) or `formatAuditValue`
(truncate to 2 dp, no padding) (FMT 25–68).

`rn` = `ROW_NUMBER() OVER (PARTITION BY totalsPartitionBy ORDER BY (SELECT NULL))` — counts a
row's stock only once when one stock origin fans out into several report rows (SQL 1410–1413).

| Metric | Qty mode | Value mode | Source |
|---|---|---|---|
| **Stock** | `TotalStockQty = Σ (rn=1 ? StockQty : 0)`; in **UOM** mode `Σ (rn=1 ? SheetStockQty : 0)` (as entered, mixed UOMs) | `StockValue = Σ (rn=1 ? StockQty × CostPrice : 0)` (primary UOM in all modes) | HTML 606–612; SQL 1401–1432 |
| **Audited** | `TotalAuditedQty = Σ AuditedQty`; in **UOM** mode `Σ ISNULL(AuditedUOMQty, AuditedQty)` (as entered) | `AuditedValue = Σ AuditedQty × CostPrice` | HTML 614–621; SQL 1403–1435 |
| **Damaged** | `TotalDamagedQty = Σ DamagedQty / 1` (primary UOM; `TotalsUomFactor` is hard-coded 1) | `DamagedValue = Σ DamagedQty × CostPrice` | HTML 623–630; SQL 1397, 1426, 1436–1438 |

`CostPrice` per row = `COALESCE(MAX(sheet row CostPrice), MAX(item's sheet CostPrice anywhere in the audit), branch cost price (ufnItemBranchPick rn=1), 0)` (SQL 1108, 966–980).

### 2.3 Filter chips

Click → `activeBadge = value` → reload (TS 1517–1520). The count shown is
`badge.count`: "All" = `TotalCount`, others = `FiltersCount[value]` (TS 1611–1630). Counts are
refreshed only when the request had `IsFiltersCount=true` or the chip is `All` — so on any
other chip the counts are those of the last All/first load. They are computed over
`#TempAuditSummaryData` **after** the search/column filters (SQL 349–377), so typing in search
changes the chip counts.

Row columns used by the counts are the final report columns (`StockQty`, `AuditedQty`,
`AuditorName = CONCAT(FirstName,' ',LastName)` — `' '` when no auditor).

| Chip label (value) | Count formula (`FiltersCount`, SQL 349–377) | Row filter when selected (`HAVING`, SQL 1340–1386) |
|---|---|---|
| All (`All`) | `COUNT_BIG(ItemCode)` | none |
| Matched Line Item (`MatchedItem`) | `ISNULL(Audited,0) = ISNULL(Stock,0)` | `SUM(ISNULL(ali.AuditedQty,0)) = ISNULL(ss.StockQty,0)` |
| Un Verified (`LineItemNotFound`) | `Stock > 0 AND ISNULL(Audited,0) = 0 AND auditor blank` | `SUM(ali.AuditedQty)=0 AND ISNULL(ss.StockQty,0) IS NOT NULL` (always true) `AND auditor name blank` |
| Not Found (`NotFound`) | `Stock > 0 AND Audited = 0 AND auditor not blank` (item was marked Not Found, or counted as 0) | `ISNULL(ss.StockQty,0) > 0 AND ali.AuditedQty = 0 AND auditor not blank` |
| Excess Line Item (`ExcessItems`) | `ISNULL(Stock,0)=0 AND ISNULL(Audited,0)>0` | `MAX(ss.ItemCode) IS NULL` (no sheet row at all) |
| Positive Variance (`PositiveVariance`) | `Audited > Stock` (includes excess rows) | `ISNULL(ali.AuditedQty,0) > ISNULL(ss.StockQty,0)` |
| Negative Variance (`NegativeVariance`) | `auditor not blank AND Audited < Stock` | `ISNULL(ali.AuditedQty,0) < ISNULL(ss.StockQty,0) AND ali.ItemCode IS NOT NULL` |
| Location Conflict (`LocationConflicts`) | `ISNULL(StockLocation,'') <> ISNULL(AuditedLocation,'')` | `ISNULL(MAX(ss.StockLocation),'') <> ISNULL(MAX(ali.AuditStockLocation),'')` |
| Cross Checked Audit (`CrossChecked`) | `ISNULL(CrossAuditedQty,0) > 0` | `MAX(ISNULL(cai.CrossAuditedQty,0)) > 0` |
| Damaged Report (`DamagedItems`) | `ISNULL(DamagedQty,0) > 0` | `ali.DamagedQty > 0` |

Chip definitions: TS 111–192. Arrow buttons scroll the chip row ±200 px (HTML 641–658).

### 2.4 Search

| Field | Behaviour | Source |
|---|---|---|
| "Search Item Code / Item Name" | Every keystroke (`input`) sets `globalFilterValue`, resets to page 1 and reloads; no debounce, no cancellation of earlier requests | HTML 667–669, TS 1664–1669 |
| Clear (×) | empties the text and reloads; page number kept | HTML 670–672, TS 1671–1675 |
| Server match | `COALESCE(ss.ItemCode, ali.ItemCode) LIKE '%' + FilterValue + '%' OR ItemName LIKE '%' + FilterValue + '%'` — the **whole combined FilterValue string**, including any ticked column-filter values (see §2.6) | SQL 1233–1236 |

### 2.5 Table columns

Display formatters: `formatAuditQuantity` = truncate 4 dp, no grouping (FMT 25–64);
`formatAuditValue` = truncate 2 dp, no padding; `decimalFormat:'quantity'` = truncate 4 dp then
**regional** number format with grouping, `1.0-4` (PIPE 33–49). "Sort" = clicking the header
calls `onColumnClick` (toggle asc/desc, page 1, server `ORDER BY <ColumnName>`) (TS 3076–3086),
and PrimeNG `pSortableColumn` additionally sorts the loaded page in the browser.

| # | Column (header) | Shown when | What it shows | Formula | Source (UI → SQL) |
|---|---|---|---|---|---|
| 1 | S.No | always | position on **this page** | `rowIndex + 1` (restarts at 1 every page) | HTML 708, 1118 |
| 2 | Item Code | always | `ItemCode` | `COALESCE(ss.ItemCode, ali.ItemCode)` | HTML 709, 1119; SQL 1026 |
| 3 | Item Name | always | `ItemName` | `MAX(#Items.ItemName)` (active items of the audit's item group) | HTML 712, 1120; SQL 1026, 1172 |
| 4 | Category | not Quick | `CategoryName` | `MAX(ItemsCategory.CategoryName)` via item's `ItemCategoryId` | HTML 715, 1121; SQL 1028, 1218–1222 |
| 5 | Stock Location | always | `StockLocation` | Item/Auditor: distinct sheet locations of the item, sorted, `', '`-joined, blank → "Unassigned" (SQL 34–51, 485–490). Location: the row's sheet location (blank → "Unassigned"). Serial/LPN: `MAX(StockLocation)` (one arbitrary). Batch/UOM: non-distinct `STRING_AGG` of sheet rows. Then `MAX(ss.StockLocation)` (SQL 1103) | HTML 746, 1122 |
| 6 | Audited Location (filter title "AUDITED WAREHOUSE") | always | `AuditedLocation`, de-duplicated in the browser by `getUniqueLocations` | Item: distinct found locations of the item (`AuditStockLocation`, blank → "Unassigned"); Auditor: same per item × auditor; Location: the row's found location; Serial/Batch/UOM: non-distinct `STRING_AGG`; LPN: `STRING_AGG(NULLIF(...,''))` (blank dropped). Then `MAX(ali.AuditStockLocation)` | HTML 749, 1123; TS 3070–3074; SQL 400–437, 633–634, 694, 744, 795, 841, 1104 |
| 7 | UOM (Primary) | always | Non-UOM modes: the item's **primary** UOM. UOM mode: replaced in the browser by `StockUOM` (UOMs on the item's sheet rows, `', '`-joined) | primary = first `UomConversions` row with no child (item-level, else group-level, else `ItemsNew.UOM`), text before "(" (SQL 1174–1210, 1027). UOM mode: `StockUOM = STRING_AGG(sheet UOM)` (TS 1583; SQL 899–906) | HTML 780–783, 1124 |
| 8 | Stock Quantity | always | Non-UOM: primary-UOM stock. UOM mode: sheet qty as entered | `StockQty = ISNULL(ss.StockQty,0)` = Σ sheet `StockQty` for the row's grain. UOM mode: `SheetStockQty = Σ ISNULL(UOMQty, StockQty)` (TS 1584) | HTML 811, 1125 (`decimalFormat`); SQL 947–948, 1033–1034 |
| 9 | Audited UOM | UOM mode | UOMs the item was counted in | `STRING_AGG(NULLIF(ALI.UOM,''), ', ')` over the item's (UOM) groups | HTML 814, 1126; SQL 878–892, 925 |
| 10 | Audited Quantity | always | Non-UOM: Σ counts in primary UOM. UOM mode: Σ counts as entered | `AuditedQty = ISNULL(SUM(ALI.AuditedQty),0)` (all auditors, all active lines). UOM mode: `AuditedUOMQty = Σ ISNULL(UOMQty, AuditedQty)` (TS 1588) | HTML 842, 1127 (`formatAuditQuantity`); SQL 992, 1037, 882 |
| 11 | Default UOM | UOM mode | the item's Default UOM | `#DefaultUom.ShortName`: the UOM on this audit's sheet rows wins, then the conversion flagged `IsDefault`, then factor 1 (primary) (TMP 95–133). Final: `COALESCE(ali.DefaultUOM, ss.DefaultUOM, primary)` | HTML 845, 1128; SQL 838, 849, 927 |
| 12 | Audited Qty in Default UOM | UOM mode | count converted to the Default UOM | `DefaultQty = Σ ALI.AuditedQty (primary) ÷ Factor(DefaultUOM)`, factor 0/NULL → 1. Factor = product of `UomConversions.Quantity` up the chain from the primary (TMP 52–93). Nothing counted → 0 (TS 1587) | HTML 873, 1129 (`decimalFormat`); SQL 883, 928 |
| 13 | Pallet ID | Warehouse + LPN mode | `PalletId` | `COALESCE(ali.PalletId, ss.PalletId)`, `—` if none | HTML 880, 1133; SQL 757–758 |
| 14 | Case ID | Warehouse + LPN mode | `CaseId` | `COALESCE(ali.CaseId, ss.CaseId)`, `—` if none | HTML 883, 1134; SQL 759 |
| 15 | Count Type | Warehouse + LPN mode | how the qty was obtained | `MAX(ali.VerificationLevel)`: `P`→"Rolldown" (pallet roll-down credit), `C`→"Sealed Case" (sealed-case credit), `I`→"Counted" if the row has a case, else "Loose"; otherwise "-" | HTML 886, 1135; SQL 764–775 |
| 16–18 | Batch No / Production Date / Expiry Date | batch group + Batch mode | batch identity | `COALESCE(ali.BatchNo, ss.BatchNo)`; dates = `MAX(ali.ProductionDate/ExpiryDate)` (count side only, so blank for uncounted batches), shown `MM-dd-yyyy` | HTML 889–900, 1136–1141; SQL 802, 1029–1030 |
| 19–21 | Id1/Id2/Id3 names (group's labels) | serialized group + Serial mode, by `uniqueIdCount` | serial identifiers | `COALESCE(ali.IdN, ss.IdN)` | HTML 901–915, 1142–1150; SQL 699–702 |
| 22 | Variance | always | count − stock | Non-UOM: `Variance = ISNULL(ali.AuditedQty,0) − ISNULL(ss.StockQty,0)` (primary UOM). UOM mode: `ISNULL(ali.DefaultQty,0) − ISNULL(ss.StockDefaultQty,0)` (Default UOM; `StockDefaultQty = Σ sheet StockQty ÷ Factor`). Every row with an item code gets one, so an uncounted item shows `−Stock`. **Damaged qty is not included.** | HTML 916, 1153; SQL 34–41, 855–857, 1068–1073 |
| 23 | Variance Value | always | money value of the variance | `(ISNULL(ali.AuditedQty,0) − ISNULL(ss.StockQty,0)) × CostPrice` — always the primary-UOM difference, also in UOM mode; `CostPrice` as in §2.2. Shown `-` only if NULL | HTML 919, 1154–1155; SQL 1076–1087 |
| 24 | Variance Type | always | Positive / Negative / - | `Audited > Stock` → Positive, `<` → Negative, else `-` (UOM mode compares Default-UOM quantities). Green/red text | HTML 922–951, 1156–1159; SQL 1090–1100 |
| 25 | Variance History | not Quick, and Item / Auditor / UOM mode | the item's variance in its last 5 earlier audits, oldest first, `+` for positive | Per item: audits of the same item group, created **before** this one, status not N/S/I, not Quick Audit, in which the item had a sheet or count row; last 5 by `CreatedDate`. Each value = `FLOOR(((Recount Σ if a Recount sub-audit exists, else Σ AuditedQty) − Σ StockQty) × 10000) / 10000` | HTML 953–957, 1160–1164; TS 677–697; SQL 103–331, 1117 |
| 26 | Damaged Qty | always | Σ damaged | `ISNULL(SUM(ALI.DamagedQty),0)` (primary) | HTML 958, 1165; SQL 993, 1101 |
| 27 | Auditor | always | auditor name | `MAX(CONCAT(User.FirstName,' ',LastName))` of `MAX(ali.AuditorId)` — in Item mode one name per item even when several auditors counted it | HTML 961–990, 1166; SQL 1107, 997 |
| 28 | Audited Date | always | last count time | `MAX(ALI.UpdatedDate)`, shown `MM-dd-yy HH:mm` | HTML 992, 1167; SQL 996, 1105 |
| 29 | Audited Image | always | image icon if the row has photos | `MediaLocation = STRING_AGG(MediaLocation, ', ')`; click opens the gallery | HTML 995, 1168–1181; TS 1329 |
| 30 | Cross AuditedQty | not Quick | Cross Check sub-audit count | `SUM(ISNULL(cai.CrossAuditedQty,0))`, where `cai` = Σ `SubAuditItems.Qty` of the audit's **Cross Check** sub-audit, not voided, per item × batch × ids; joined on ItemCode (+ ids in Serial, + batch in Batch). Serialized groups: −1 → "0", 0 → "-" | HTML 996, 1184–1185; TS 661–668; SQL 492–493, 1131–1167 |
| 31 | Cross DamagedQty | not Quick | Cross Check damaged | `SUM(ISNULL(cai.CrossDamagedQty,0))` | HTML 999, 1186; same |
| 32 | Declaration Note | always | auditor/resolution note | `MAX(AuditResolutionItems.DeclarationNotes)` if any, else `MAX(ALI.Reason)` | HTML 1002–1031, 1188; SQL 1111–1115 |
| 33 | Coordinates | always | GPS of the count | `MAX(ALI.Coordinates)` | HTML 1033, 1189; SQL 1109 |
| 34 | Resolution Status | not Quick, not Warehouse | resolution state | `dbo.GetRecountStatus(MAX(ari.Action), MAX(ari.Status))`: R/A "Recount Accepted", R/I "Moved To Investigation", A/N "Accepted", I/N "Under Investigation", R/N "Recount Pending", P/N "Pending", else "" (`DBAPP_SK_MAIN/dbo/Functions/GetRecountStatus.sql`). `ari` joined on ItemCode (+ ids in Serial, + batch in Batch) | HTML 1047–1078, 1198–1199; SQL 1125, 1168–1176 |
| 35 | Remarks | not Quick | resolution remark | `MAX(AuditResolutionItems.Notes)` | HTML 1079–1110, 1200; SQL 1116 |

Hidden data in every row (not a column): `CostPrice`, `SheetStockQty`, `AuditedEnteredQty`,
`MediaLocation`, `ProductionDate`, `ExpiryDate`, and in UOM mode `StockUOM`, `StockUOMQty`,
`AuditedUOMQty` (SQL 1024–1125, 921–928).

Empty states: spinner while loading with no rows, "nothing here" image when no rows, "No
matching results found." inside the table (HTML 1203–1220).

### 2.6 Column filters

Common mechanics (all columns below):

- Options = distinct non-empty values of that field **on the currently loaded page**, sorted;
  refreshed only after a load where no search text and no column filter is active
  (TS 1595–1607, 543–551).
- Ticking a box only changes `selectedFilters[field]`; **Apply** calls PrimeNG's
  `filterCallback(selected)` (a client-side `in` filter on the loaded page) **and** reloads from
  page 1 with `FilterValue` rebuilt (TS 596–608).
- `FilterValue` is one comma-joined string of the search text and every selected value of every
  field (TS 619–639). The server splits it with `STRING_SPLIT(FilterValue, ',')` and ORs every
  predicate below with each other and with the search `LIKE` (SQL 1233–1285). So server-side
  semantics are **OR within a column and OR across columns**; the PrimeNG client filter then
  narrows the returned page with AND across columns.
- "Select All" ticks every option currently in the cache (TS 558–561).

| Column filter (field) | Server predicate (any value in the split list) | Source |
|---|---|---|
| Category (`CategoryName`) | `ic.CategoryName IN (...)` | HTML 717–742; SQL 1237 |
| Audited Warehouse (`AuditedLocation`) | `ali.AuditStockLocation IN (...)` (the whole aggregated string) | HTML 754–776; SQL 1258 |
| UOM (Primary) (`UOM`) | `displayUom.UomName IN (...)` OR the item's `IsDefault` UOM name IN (...); UOM mode also any of `ss.StockUOM` parts | HTML 785–806; SQL 1239–1251, 862–867 |
| Audited UOM (`AuditedUOM`), UOM mode | any part of `ali.AuditedUOM` IN (...) | HTML 817–839; SQL 864–865 |
| Default UOM (`DefaultUOM`), UOM mode | `COALESCE(ali.DefaultUOM, ss.DefaultUOM) IN (...)` | HTML 848–870; SQL 866 |
| Variance Type (`VarianceType`) | recomputed: Audited>0 ? (A>S Positive / A<S Negative / '-') : (S>0 Negative / '-'); IN (...) | HTML 927–948; SQL 1263–1278 |
| Auditor (`AuditorName`) | `CONCAT(u.FirstName,' ',u.LastName) IN (...)` | HTML 966–988; SQL 1238 |
| Declaration Note (`DeclarationNote`) | `ari.DeclarationNotes IN (...) OR ali.Reason IN (...)` | HTML 1007–1029; SQL 1260–1261 |
| Resolution Status (`ResolutionStatus`) | `dbo.GetRecountStatus(ari.Action, ari.Status) IN (...)` | HTML 1052–1074; SQL 1262 |
| Remarks (`Remarks`) | `ari.Notes IN (...)` | HTML 1084–1106; SQL 1259 |

Stock Location, Stock/Audited/Default quantities, Variance, Variance Value, Damaged, dates,
Cross quantities, Coordinates and Variance History have sort only, no filter.

### 2.7 Sorting, totals and pagination

| Element | Behaviour | Source |
|---|---|---|
| Server sort | `ORDER BY {ColumnName} {SortBy}` interpolated raw into the SQL; default `AuditedDate DESC` (ties unordered) | TS 3076–3086; `GeneralHelperService.cs:261–280`; SQL 1444 |
| Footer / row totals | none in the table; the only totals are the metric strip (§2.2) | — |
| Paging text | `Showing (page−1)×size+1 to min(page×size, total) of total entries` | HTML 1222–1225; TS 1505–1509 |
| Paginator | `rows=pageSize`, `totalRecords=TotalCount` (filtered), options 25/50/100/200; change → reload | HTML 1226–1229; TS 1511–1515 |

### 2.8 Downloads

| Button | Shown / enabled | What it produces | Source |
|---|---|---|---|
| **Export** (Excel) | enabled when the page has rows | `POST /Audit/ExportAuditSummaryReport` with current `SummarizeAs` and `FilterValue`. The server ignores the chip and sort and builds **one sheet per chip**: All, Matched Line Item, Line Items Not Found (= Un Verified; dropped for Cycle Count), Excess Line Item, Positive Variance, Negative Variance, Location Conflict, Cross Checked Audit, Damaged Report (9 sheets; Quick Audit has no Cross Checked sheet). Each sheet = `GetAuditSummaryReport` with page size 1,000,000. File "Audit Summary Report.xlsx" | HTML 692–695; TS 1736–1754, 1767–1792; SVC 4597–4672, 165–187, 4673–4693 |
| Excel columns | the raw report columns, header = SQL column name, in SQL order: ItemCode, ItemName, **UOM (Base)** (UOM mode: **StockUOM**), CategoryName, [BatchNo/ProductionDate/ExpiryDate in Batch mode], [Id1–3Name in Serial mode], StockQty, AuditedQty, Variance, VarianceValue, VarianceType, VarianceHistory, DamagedQty, CrossAuditedQty, CrossDamagedQty, StockLocation, AuditedLocation, AuditedDate (`MM-dd-yyyy`), AuditorName, **CostPrice**, Coordinates, DeclarationNote, Remarks, ResolutionStatus (+ UOM mode: AuditedUOM, DefaultUOM, DefaultQty; LPN: PalletId, CaseId, CountType). Removed: MediaLocation, AuditedEnteredQty, SheetStockQty, StockUOM/StockUOMQty/AuditedUOMQty (their values replace UOM/StockQty/AuditedQty in UOM mode). Quantities in `StockQty, AuditedQty, DamagedQty, Variance` truncated 4 dp; `VarianceValue` 2 dp | SVC 4733–4882, 4896–4917, 145–163 |
| **Download PDF** | only when `obj.auditStatus` is `A` or `C` | `POST /Audit/ExportAuditSummaryPdf` with the current chip, SummarizeAs and FilterValue. Columns by mode: S.No, "Item Code - Item Name - UOM"; Batch No (Batch); Id1–3 + Audited Type (= AuditedQty>0 ? Available : NotAvailable) (Serial); Stock Qty + Audited Qty (Item/Auditor/Location/Batch); Auditor (Serial/Auditor); Variance (Item/Location/Batch); Variance Value (Item); Stock/Audited Location (Location); Declaration Note, Resolution Status, Remarks. Numbers `0.####` | HTML 679–683; TS 1015–1041; PDF 617–735, 25 |
| **Download All Images** | when the loaded page has photos | zip of `allMediaLocations` (photos of the rows on the current page) | HTML 684–687; TS 1612–1618, 1994–2032 |
| Mobile "export selected" | multi-select on the mobile card list | client-side `loadExcelHeader(rows,'completeAudit')` | TS 1691–1696, 1128–1205 |

### 2.9 Variants

- **Warehouse (LPN) audit.** Rows exist only after reconciliation rewrites `AuditLineItems`
  (one row per item × case, `VerificationLevel` I/C/P). Credited quantities follow the
  reconciliation ladder: item scans win; a case opened with the item absent counts 0; a sealed
  case scanned but not opened is credited its expected qty when `LPNSealedCaseCredit` is on
  (`C`); a pallet scanned with no cases opened credits its expected cases when
  `LPNPalletRollDown` is on (`P`); never scanned → shortage
  (`/home/user/StockountAPI/docs/warehouse-lpn-module.md` §6.5–6.6). The report then treats
  those lines exactly like counts. Resolution Status is hidden. `onLpnReconciled` reloads
  the report (TS 349–353).
- **Quick Audit.** `GetQuickAuditSummaryReports` (SQL 1689–1913): stock and counts per sheet
  row; `Variance = Audited − Stock` only when audited > 0 and different, `−Stock` when not
  counted; excess (off-sheet) rows have `StockQty 0`, `CostPrice 0`, `VarianceValue 0`;
  totals are plain sums with no de-dup (SQL 1897–1905); the search matches ItemCode only on
  excess rows.
- **Mobile.** Same data and payload; cards show Stock/Audited/Variance with
  `formatAuditQuantity`; sorting is client-side on the loaded page only (default Variance
  desc) (MOB ts 106–196, html 206–233).

---

## 3. Complete Audit action

Button: HTML 69–75. Hidden when `PrimaryAuditStatus = H` (Archived); disabled while
`isCompletingAudit` or when status is `C` (Completed) or `A` (AutoCompleted). Label becomes
"Completing…" with a spinner. Mobile emits the same `CompleteAuditbtn()` (HTML 2350).

### 3.1 Flow, step by step

1. **Re-entry guard.** If `isCompletingAudit` is already true, do nothing (TS 2090–2093).
2. **Pending recounts.** If `Recountcount > 0` → navigate to `/home/auditresolutionrecount`
   with no message (TS 2094–2097). `Recountcount` = rows with `Status='N' AND Action='R'`
   among the **first 50** rows of `GetRecountedLineItems` (TS 579–603).
3. **Quick Audit** → `completeQuickAudit`: SweetAlert "Are you sure, you want to complete the
   Audit?" (or "Stock Audit is not completed…force complete") → `CompleteStatus='C'`,
   `IsMarkInsvestiage=false` → step 8 (TS 2105–2119).
4. **Already in resolution** (`PrimaryAuditStatus` `K` or `C`): Warehouse → toast "Audit
   completed. Reconcile below to resolve variances." and stop; otherwise navigate to Audit
   Resolution. No API call (TS 2205–2216).
5. **Permission.** Contributor (plan access `C`) → warning "Only Audit Owner can complete the
   audit"; not owner → "Only Audit Owner can perform this action" (TS 2220–2227;
   `models/audit-plan-access.model.ts:22–24`). Owner = `auditObj.auditOwner == userId` or plan
   access `O` (TS 479–491).
6. **Dialog step 1, Confirmation.** Message from `checkAuditStatus`
   (`GET /AuditSetting/checkAuditStatus/{id}`, SET 676–724):
   - `isAuditorCompleted` = every entry in `Audit.AuditorStatus` JSON is "Completed";
     `isCrossAuditCompleted` = plan has a cross-check auditor and `Audit.CrossCheckStatus='C'`.
   - Both done (or no cross-auditor and auditors done) → "Are you sure, you want to complete the
     Audit?"; otherwise "The auditor(s) have not completed their audits. Are you sure you want
     to force complete this audit?" — informational only, never blocking (TS 2229–2251).
   - **Yes** → "Checking…" → `GET /Audit/GetResolutionFilterandCount/{id}/{branch}?insightsOnly=true`
     (INS 422–647). `hasResolutionItems` = any insight count > 0 among Excess Line Item,
     Positive Variance, Negative Variance and Not Found (stock rows with no count line at all);
     "Not Found" is ignored for Cycle Count (TS 2984–3006). **No** / close → cancel.
7. **Branching after Yes** (TS 2827–2867):
   - No resolution items → result `complete` → `CompleteStatus='C'`, `IsMarkInsvestiage=false`.
   - Resolution items, not Cycle Count → `unVerifiedCount` = number of distinct ItemCodes in
     the report at **Item** grain with chip `LineItemNotFound` (page size 100,000)
     (TS 2306–2325, 2447–2477). If > 0 → **Step 2 "Unverified items"** ("There are N items not
     counted…"): *Move to Not Found* (items included in variance and Resolution) or *Keep as
     Unverified* (excluded). The Location-grain list is prefetched in the background.
     If 0 or Cycle Count → straight to step 3.
   - **Step 3 "Complete Audit?"**: *Proceed to Resolution* → `CompleteStatus='K'`,
     `IsMarkInsvestiage=false`; *Complete Audit* → `CompleteStatus='C'`,
     `IsMarkInsvestiage=true` ("move all variance items to Investigation").
8. **Mark Not Found** (only if *Move to Not Found* was chosen, TS 2343–2418): take the
   Location-grain `LineItemNotFound` rows, keep only the ItemCodes counted in step 7, and post
   `POST /AuditLineItems/MarkItemNotFound` with `AuditedQty=0, DamagedQty=0`, the row's batch /
   serial / dates and `StockLocation = AuditStockLocation = sheet location`. The server
   (ALIS 1333–1470) bulk-inserts one `AuditLineItems` row per location with
   **`AuditorId = the person completing`**, "Unassigned" turned back to blank, and sets the
   audit to `I` if it had no counted line yet. Failure → "Unable to mark items as Not Found. …"
   and the completion stops (but rows already inserted stay).
9. **Complete call** `POST /AuditSetting/completeAuditByOwner`
   `{auditId, branchId, CompleteStatus, IsMarkInsvestiage}` (TS 2908–2927) →
   `SET CompleteAudit` (SET 733–857):
   1. Role: `K` needs plan role Owner or Contributor; `C` needs Owner or Admin
      (SET 742–749) → else "ONLY_AUDIT_OWNER_COMPLETE".
   2. **Adjustment gate** (only `C`): `GetCompletionBlockAsync` (ADJ 135–159) derives/reads the
      audit's `AuditAdjustment`; if its status is not settled (`NotRequired, Approved, Posted,
      PartiallyPosted, Queued`) the call is refused with "This audit has N accepted variance
      line(s) waiting to be adjusted/posted to … Adjust stocks before completing the audit."
      or "Posting … has not finished…" (ADJ 1125–1147; `Common/AuditAdjustmentConstants.cs:106–108`).
      A gate exception returns null (never blocks).
   3. **Status transition:** `Audit.PrimaryAuditStatus = CompleteStatus` and save — `K`
      (InResolution) or `C` (Completed) (SET 772–774).
   4. `K`: `GetAllVarianceList(loadList:false)` inserts `AuditResolutionItems` with
      `Action='P', Status='N'` (Pending) for every item × batch × serial × sheet location whose
      `Σ audited ≠ stock`, for items counted somewhere in the audit (Cycle Count: counted > 0),
      skipping combinations that already have a row (SET 776–784; SVC 5312–5360;
      VAR 59–72, 267–362).
   5. `C` with `IsMarkInsvestiage`: the same insert with `Action='I', Status='N'`
      ("Under Investigation") (SET 789–796).
   6. `C`: in-app notification "Audit <name> Completed Successfully." (SET 798–817).
   7. `C`: completion e-mail (MAIL 1452–1585): to the audit owner, CC the notification-setting
      users; only if the AuditCompleted e-mail notification is enabled. Attachments: the Audit
      Summary PDF (Summarize As Item, chip All, unfiltered — PDF 175–198) and the adjustment
      workbook when the adjustment has lines. Data read now; PDF/Excel rendered and sent after
      the response (`deferDelivery: true`).
   8. `C` without `IsMarkInsvestiage`: `UpdateAuditLineItemsResolutions` (SVC 6391–6560) —
      **this is what freezes the counts**: for every resolution row with `Status='A'`
      (Recount Accepted) all the item's matching line items (same item/batch/ids, any location)
      are deactivated (`RecountAction='S'`) and replaced by one line with
      `AuditedQty = ReCountAuditQty`, `DamagedQty = ReCountDamagedQty`, UOM qty re-derived from
      the original line's ratio; other rows only get `RecountStatus` stamped on their latest
      line. Owner/Admin only.
   9. `C`: branch item risk score recalculated (best effort) (SET 843–846).
10. **Client after success** (TS 2943–2965): Quick → "Audit completed successfully". `C` with
    investigation → home + "Audit has been completed successfully and the variance item(s)
    have been moved to Investigation."; `C` without → "Audit completed successfully" + home;
    `K` → status set to `K` in `parentData`/localStorage, then Audit Resolution (Warehouse: the
    "Reconcile below" toast instead). Failure → error toast with the server message.
    `isCompletingAudit` cleared in `finally`.

### 3.2 What is frozen or computed on completion

| Item | When | Where |
|---|---|---|
| Audit status `K` / `C` | step 9.3 | `Audit.PrimaryAuditStatus` |
| Not Found count lines (qty 0, auditor = completer) | step 8 | `AuditLineItems` |
| Resolution rows (Pending or Under Investigation) | step 9.4 / 9.5 | `AuditResolutionItems` |
| Accepted recounts replace counted lines | step 9.8 (`C`, not investigate) | `AuditLineItems` (`RecountAction S/R`) |
| Adjustment must be settled first | step 9.2 (`C`) | `AuditAdjustment` |
| Notification, e-mail (summary PDF + adjustment workbook) | `C` | `MAIL`, `PDF` |
| Branch item risk score | `C` | `RecalculateForBranchAsync` |

---

## 4. Findings

Evidence-based inconsistencies, highest impact first.

1. **Search and column filters are merged into one OR'd string, so filters widen instead of
   narrowing, and search stops working once any filter is ticked.** `buildFilterValue` joins
   the search text and every ticked value of every column with commas (TS 619–639). The server
   ORs every predicate (SQL 1233–1285): ticking Category=A and Auditor=B returns rows in A
   **or** by B. With a filter ticked, the search `LIKE '%' + 'abc,A' + '%'` no longer matches
   item codes, while `abc` is tested as a category/auditor/UOM/location name. The PrimeNG
   `filterCallback` then narrows only the loaded page with AND (TS 603), so pages come back
   short while the paginator, "Showing … of N", the metric strip and the chip counts all
   describe the wider OR set. A search text or value containing a comma is split.
2. **Download PDF returns "Audit summary data not found." whenever a chip other than All is
   selected.** The PDF reads result set index 2 (`ResultSet2`, PDF 253). The SQL emits the
   `FiltersCount` set only when `IsFiltersCount` is true or the chip is All (SQL 347). The PDF
   payload never sets `IsFiltersCount` (TS 1767–1792), so with e.g. Positive Variance there are
   only two result sets and no rows → `PrepareFailure("Audit summary data not found.")`
   (PDF 76–81).
3. **The PDF has no quantity columns for UOM, Pallet/Case (LPN) and Serial modes.** Its
   Stock/Audited Qty columns are emitted only for Item/Auditor/Location/Batch, Variance only for
   Item/Location/Batch, and Variance Value only for Item (PDF 640–657, 711–730); the UOM and
   LPN modes fall through to Item text, Declaration Note, Resolution Status and Remarks.
4. **UOM mode's Stock and Audited tiles add up different units.** `TotalStockQty` sums
   `SheetStockQty` and `TotalAuditedQty` sums `AuditedUOMQty` (as entered: Box + Bottle +
   Unit), while Damaged stays in the primary UOM and all values use primary quantities
   (SQL 1401–1438). The UOM-mode row's Stock Quantity is the same mixed sum when an item's sheet
   rows are in several UOMs (`SheetStockQty = Σ UOMQty`, SQL 947, 1034).
5. **UOM mode: three columns in three different units.** Stock and Audited Quantity are as
   entered, Variance is in the Default UOM (`DefaultQty − StockDefaultQty`), Variance Value and
   Damaged Qty are in the primary UOM (SQL 855–857, 1076–1087; TS 1580–1590). The "UOM
   (Primary)" header is kept in UOM mode although the cells now hold the sheet UOM
   (`UOM: item.StockUOM`, HTML 782, TS 1583); the export calls the same column "StockUOM" in UOM
   mode and "UOM (Base)" otherwise (SVC 4857–4859). Sorting "Stock Quantity" in UOM mode
   orders by the primary `StockQty`, not the as-entered value on screen.
6. **Sorting Declaration Note breaks the report.** The header sends `ColumnName='Reason'`
   (HTML 1002–1005, TS 3076), but `#TempAuditSummaryData` has no `Reason` column (it is
   `DeclarationNote`, SQL 1111–1115), so `ORDER BY Reason` fails and the table empties with no
   message (TS 1655–1661). The column name and direction are interpolated into SQL unvalidated
   (`GeneralHelperService.cs:265–267`).
7. **Location Conflict counts every Un Verified and every Excess row.** The count compares
   `ISNULL(StockLocation,'') <> ISNULL(AuditedLocation,'')` (SQL 372); an uncounted row has
   `AuditedLocation` NULL against a sheet location (at least "Unassigned"), and an excess row the
   reverse. In Item/Auditor mode both sides are comma lists, so an item counted at only one of
   its two locations is also a "conflict".
8. **Un Verified chip: count and list use different rules.** Count requires `StockQty > 0`
   (SQL 352–360); the list's `HAVING` uses `ISNULL(ss.StockQty,0) IS NOT NULL`, which is always
   true (SQL 1346–1349), so sheet rows with 0 stock and no count are listed but not counted. The
   same Item-grain list drives the "N items not counted" popup and Mark Not Found (TS 2306–2325),
   so zero-stock rows are also marked Not Found.
9. **Joined resolution rows inflate aggregates in Item / Auditor / Location / UOM modes.**
   `AuditResolutionItems` is joined on ItemCode only (`resolutionStatusJoin` is set only for
   Serial and Batch, SQL 704–706, 806), and there is one resolution row per item × location.
   Each extra row duplicates the group's rows, so `SUM(cai.CrossAuditedQty)` / `CrossDamagedQty`
   are multiplied (SQL 492–493), the Matched chip's `SUM(ali.AuditedQty) = StockQty` fails for
   such items (SQL 1358) although its count (which uses the plain column) includes them, and
   Resolution Status = `GetRecountStatus(MAX(Action), MAX(Status))` can combine an Action
   from one row with a Status from another (SQL 1125).
10. **The Audited Warehouse filter cannot match multi-location rows.** Item/Auditor rows hold
    `AuditedLocation = "A, B"`; the option offered is that string, but the server splits the
    selected value on "," and compares `AuditStockLocation IN ('A',' B')` (SQL 1258), which
    never equals "A, B".
11. **Filter options come from one page.** `filterOptionsCache` is built from `allSummaryData`,
    the current page of 25 rows (TS 1595–1607). Values on other pages cannot be picked. It is
    never rebuilt while a filter or search is active, and selections in UOM-only fields stay in
    `FilterValue` after leaving UOM mode.
12. **Un Verified rows carry a negative variance.** Every row with an item code gets
    `Variance = Audited − Stock` (SQL 41, 1068–1073), so an uncounted item shows `−Stock`,
    "Negative" and a negative Variance Value in the report and export. The step-2 dialog says
    these items are "excluded from variance" (TS 2761). That is true for Resolution, not for
    this report.
13. **Excel export does not match the screen.** It ignores the selected chip and sort and always
    writes 9 sheets (SVC 4638–4651); there is no sheet for the **Not Found** chip (SVC 165–176);
    headers are raw SQL names; it adds `CostPrice`; `DefaultQty`, `CrossAuditedQty`,
    `CrossDamagedQty` and `CostPrice` are not in the truncation lists, so they export unformatted
    (SVC 145–163); Serial/Batch/UOM AuditedLocation lists keep duplicates that the screen removes
    with `getUniqueLocations` (TS 3070–3074).
14. **Mobile "export selected" writes empty columns.** `loadExcelHeader` reads camelCase keys
    (`row.itemCode`, `row.stockQty`, `row.auditer` …, TS 1128–1205) but report rows are
    PascalCase (`ItemCode`, `StockQty`, `AuditorName`).
15. **Paging and stale-request issues.** Chip click, Summarize As change and mobile search keep
    the current page (TS 1517–1520, 1542–1549, 1678–1682), so a narrower result can come back
    empty on page 4. Search fires a request per keystroke and keeps whichever response arrives
    last (TS 1664–1669). The default order `AuditedDate DESC` leaves all uncounted rows (NULL
    date) unordered, so OFFSET paging can repeat or skip them. S.No restarts at 1 on every page
    (HTML 1118).
16. **Totals can double-count stock in Auditor mode.** De-dup is on
    `ItemCode, Id1–3, BatchNo` (SQL 81), but in Auditor mode those come from `MAX()` per auditor
    group (SQL 570–577). Two auditors who scanned different batches of one item produce two
    `rn=1` rows, so `TotalStockQty` and `StockValue` count the item's stock twice.
17. **Inconsistent quantity formatting.** Stock Quantity and Default Qty use the regional
    `decimalFormat` pipe (thousands separators), while Audited Quantity, Variance, Damaged and the
    tiles use `formatAuditQuantity` (no separators) (HTML 1125–1129, 1153, 1165). Variance History
    uses `FLOOR(x*10000)/10000` (SQL 309–313), which rounds negative values down (−1.23456 →
    −1.2346) instead of truncating like everywhere else (−1.2345).
18. **Recount history sums every recount round.** `#HistRecountQty` sums all `Recount Audit`
    sub-audit items for the item (SQL 281–294), so an item recounted twice reports the sum of
    both rounds as its historical count.
19. **"Download All Images" only zips the current page.** `allMediaLocations` is rebuilt from
    the loaded page (TS 1612–1618).
20. **Complete Audit: the pending-recount check reads only the first 50 rows.**
    `checkRecountPending` asks for page 1 with `PageSize 50` (TS 579–603), so pending recounts
    beyond row 50 do not redirect. When they do, the redirect gives no message (TS 2094–2097).
21. **Complete Audit: "move all variance items to Investigation" does not move existing
    rows.** With `IsMarkInsvestiage`, the server re-runs the resolution insert with
    `Action='I'`, but that insert skips combinations that already have an active resolution
    row (VAR 349–361). Rows created earlier (e.g. Pending, from an earlier resolution visit)
    stay as they were. On that path `UpdateAuditLineItemsResolutions` is skipped (SET 830–838),
    so recounts already accepted are never applied to the line items.
22. **Complete Audit: status is saved before the follow-up work.** `PrimaryAuditStatus` is set
    and saved (SET 772–774) before the resolution insert, notification, e-mail and recount
    application. An exception after that returns "internal error" to the UI while the audit is
    already `C`/`K`. A retry repeats the notification. Mark Not Found rows (step 8) are inserted
    before the call and are not rolled back when the gate refuses completion. The server does
    not check the current status (Archived or already-completed audits are accepted).
23. **Complete Audit: the e-mail PDF is taken before recounts are applied.**
    `SendAuditCompleteEmails_New` prepares the summary data (SET 827; MAIL 1508–1516, comment
    "Complete Audit applies recounts to the line items right after this") before
    `UpdateAuditLineItemsResolutions` (SET 830–838). The attached report can therefore differ
    from what the Complete Audit Report shows once the audit is completed.
24. **Complete Audit: step 3 claims variance when there is only unverified stock.**
    `hasResolutionItems` is true when the only insight is "Not Found" (uncounted stock; INS
    611–643). Someone who chooses *Keep as Unverified* still sees "This audit contains some
    unresolved variance items" and must choose Resolution or Investigation, possibly for an
    empty set.
25. **Warehouse audit in resolution says "Audit completed" without completing.** At status `K`
    the button shows "Audit completed. Reconcile below to resolve variances." and returns
    (TS 2205–2213); it never moves the audit to `C`.
26. **Not Found lines name the completer as auditor.** `MarkItemNotFound` writes
    `AuditorId = res.UserId` (ALIS 1391). Afterwards the report shows the owner as the auditor
    of every Not Found row, and those rows move from the Un Verified chip to Not Found.
27. **Owner/Admin mismatch.** The server lets an Admin complete (`C`) (SET 746), but the UI
    stops any non-owner before the dialog (TS 2224–2227).
