# Audit Summary page — Part 1: Header, Audit Details, top-level KPIs, Auditor table, legacy charts

Scope: `audit-summary.component.html` lines 1–555 (desktop) and the equivalent blocks of
`audit-summary-mobile/` (rendered instead when `deviceDetector.isMobile()`; html:18, html:2320).
Out of scope (other parts): "Category Wise Variance", "Overall Variance", "Complete Audit Report"
(incl. its Stock / Audited / Damaged Qty|Value tiles and the filter-badge counters), "Complete Audit".

Abbreviations used for paths:

- UI-H = `stockount_UI/src/app/home/audit/audit-summary/audit-summary.component.html`
- UI-T = `stockount_UI/src/app/home/audit/audit-summary/audit-summary.component.ts`
- UI-M = `stockount_UI/src/app/home/audit/audit-summary/audit-summary-mobile/audit-summary-mobile.component.{html,ts}`
- UI-WH = `stockount_UI/src/app/home/audit/warehouse-audit/warehouse-audit-summary/warehouse-audit-summary.component.{html,ts}`
- FMT = `stockount_UI/src/app/home/audit/shared/audit-number-format.util.ts`
- STL = `stockount_UI/src/app/home/audit/shared/audit-status-label.util.ts`
- API-SS = `StockountAPI/Services/AuditSummaryService.cs`
- API-AS = `StockountAPI/Services/AuditService.cs`
- API-QA = `StockountAPI/Services/ControllerServices/Audit/QuickAuditService.cs`
- API-LPN = `StockountAPI/Services/Audit/LPN/LPNSummaryBuilder.cs`

No stored procedure / view is involved in any field of this part: all three endpoints are pure
EF Core LINQ over `Audit`, `AuditSettings`, `AuditPlan`, `Frequency`, `ItemsGroup`, `StockSource`,
`AuditLineItems`, `User`/`UserCompanyMapping` (plus `AuditLPN` / `AuditLPNReconciliation` for the
warehouse block). The one indirect "item master" read is `ItemsService.GetItemWithBranch_New`
(auditor table only — see Findings F4).

---

## 0. Data loading and shared formatting

| Concern | Detail | Source |
|---|---|---|
| Entry / context | `parentData` is read from `localStorage` by polling every 50 ms until `parentData.auditObj.auditId` exists. `auditObj` is the `getAudit(...,'recount')` response saved by the audit list. Quick audits instead read `localStorage.quickAuditData` and fabricate a minimal `auditObj` (`primaryAuditStatus = 'I'`). | UI-T:396-404, 427-455, 459-532; `audit.component.ts`:1918-1937 |
| Header data call (standard) | `GET /audit/getAuditSummary/{auditId}/{companyId}/{branchId}` → `AuditController.GetAuditSummary` → `AuditSummaryService.GetAuditSummary`. Response `data` is assigned wholesale to `obj`. | `audit.service.ts`:109-111; `Controllers/AuditController.cs`:1297-1309; API-SS:72-128; UI-T:776-938 |
| Header data call (quick) | `GET /QuickAudit/GetQuickAuditSummary/{auditId}/{branchId}` → `QuickAuditService.GetQuickAuditSummary`; UI maps `data.summary.*` into `obj`. | `Controllers/QuickAuditController.cs`:127-132; API-QA:1228-1310; UI-T:730-772 |
| Auditor table call | `POST /audit/GetAuditorSummary` body `{auditId, auditPlanId, auditors: parentData.auditObj.auditors, BranchId}` (quick: `auditors:''`, `IsQuickAudit:true`, `auditType:'Q'`). Called on load and every 30 s while the dialog is open. | UI-T:1453-1489, 1947-1966; `audit.service.ts`:122-124; `AuditController.cs`:1312-1323; API-AS:3239-4122 |
| Warehouse block call | `GET /audit/{auditId}/lpn/summary` (and the reconcile POST which returns a fresh summary). | `warehouse-audit.service.ts`:53-57; `Controllers/AuditLPNController.cs`:196-215; `AuditLPNService.GetSummary`:554-587; API-LPN:21-327 |
| Quantity format | `formatAuditQuantity(v)` = **truncate (never round)** to 4 dp (from `AuditQuantityNumberFormat '1.0-4'`), drop an all-zero fraction, no thousands separator. `null/undefined/''` → `''`. | FMT:9-63; `ConstantVariable/DataSharingName.ts`:12-14 |
| Value format | `formatAuditValue(v)` = same rule, **2 dp truncated**. | FMT:16-18, 69-71 |
| Name truncation | `truncateName(s, 20)` → first 20 chars + `'...'` if longer; full text in `title` tooltip. Mobile uses 34 / 22. | UI-T:653-655 |
| Date/time zone | API stores `Audit.CreatedDate = DateTime.UtcNow`; it is serialised without offset. The global HTTP interceptor treats any offset-less ISO string as UTC and rewrites it into the **company time zone** (`localData.timeZone`) as `yyyy-MM-dd'T'HH:mm:ss`; the template `date` pipe then formats that string. | `Services/Audit/Handlers/StandardAuditCreateHandler.cs`:~200; `assets/utilities/services/interceptor/interceptor.service.ts`:155-158, 453-481 |

---

## 1. Page header (action bar) — UI-H:20-121

| Field / control | What it shows | Formula / visibility rule | Source |
|---|---|---|---|
| Breadcrumb | `<origin> › Audit Summary` | origin = `'Audit History'` if `parentData.sourceTab === 1`, else `'Ongoing Audits'` (quick audits always `'Ongoing Audits'`). Click → `back()`. | UI-H:27; UI-T:93-100, 439 |
| Settings (gear icon) | Navigates to audit settings | always shown | UI-H:43-46 |
| **Stock Audit** button | Opens counting screen | shown when `!isWarehouseAudit`; `isWarehouseAudit = upper(trim(auditObj.AuditMethodCode ?? auditObj.auditMethodCode)) ∈ {'W','WAREHOUSE'}` | UI-H:48-51; UI-T:355-362 |
| **Auditor Insights** button | Opens the Auditor Summary dialog (§4) and starts 30 s polling | always shown | UI-H:52-56; UI-T:1007-1014, 1947-1966 |
| **Archive** | Archives (`primaryAuditStatus='H'`) | shown when `PrimaryAuditStatus != 'H'` | UI-H:60-63 |
| **Restore** | Restores an archived audit | shown when `PrimaryAuditStatus == 'H'` | UI-H:65-69 |
| **Complete Audit** | Starts completion | shown when `PrimaryAuditStatus != 'H'`; disabled when `isCompletingAudit` or `PrimaryAuditStatus ∈ {'C','A'}`; label `'Completing…'` while running | UI-H:71-77 |
| ⋮ menu (Download Pdf / Reopen Audit) | | shown when `parentData.auditObj.primaryAuditStatus ∈ {'C','A'}` | UI-H:94-106 |

`PrimaryAuditStatus` here comes from **`parentData.auditObj.primaryAuditStatus`** (client cache), *not*
from the summary API — see Finding F7.

---

## 2. Warehouse Count block (`<app-warehouse-audit-summary>`) — UI-H:126-130

Rendered only when `isWarehouseAudit` (AuditMethodCode `'W'`). It is the only "top-level KPI tile"
set inside lines 1–555 besides the Audit Details card.

| Field | What it shows | Formula | Source (UI → API → data) |
|---|---|---|---|
| Mode chip | `Normal count` / `Blind count` | `expectedVisible ? 'Normal count' : 'Blind count'`, `expectedVisible = !!summary?.showStockToAuditor`; server `ShowStockToAuditor = AuditSettings.IsStockItems ?? false` | UI-WH html:6-8, ts:245-247 → `AuditLPNService.GetSummary`:563-564 → API-LPN:38 |
| "Stock sheet not uploaded — import it" | Link to settings | shown when `summary && !summary.stockSheetUploaded`; `StockSheetUploaded = any StockSource row (IsActive, this audit) with CaseId or PalletId not null` | UI-WH html:9-13 → API-LPN:40 |
| "Last reconciled …" | Latest reconciliation timestamp (`date:'short'`, company tz via interceptor) | `LastReconciledAt = max(AuditLPNReconciliation.ReconciledAt)` over active rows; `null` → "Not yet reconciled". "· audit still open" when `AuditOpen` | UI-WH html:18-24 → API-LPN:41-43 |
| Open-audit note | Warning that unscanned cases count as Missing | `AuditOpen = PrimaryAuditStatus ∉ {'C','A','H'}` | UI-WH html:35-41 → API-LPN:39, 364-365 |
| **Pallets** | `counted` or `counted/expected` | `Pallets = count(distinct PalletId of active, non-voided AuditLPN rows with ScanLevel=Pallet)`; `ExpectedPallets = count(distinct StockSource.PalletId)` (null when 0). Denominator only if `expectedVisible && expected != null` | UI-WH html:50-54, ts:253-257 → API-LPN:57-63, 300-309 |
| **Cases** | `counted` or `counted/expected` | `Cases = number of case nodes with real evidence` (a Case-level scan or ≥1 Item-level scan inside the case; roll-down-credited cases are **excluded**); `ExpectedCases = count(distinct StockSource.CaseId)` | UI-WH html:56-60 → API-LPN:72-76, 96-101, 299, 310-311 |
| **Loose units** | `counted` or `counted/expected` | `LooseUnits = Σ LooseItems.CountedQty` (Item-level scans with no CaseId, summed per ItemCode); `ExpectedLooseUnits = Σ StockSource.StockQty for rows with no Case/Pallet` (null when none) | UI-WH html:62-66 → API-LPN:271-294, 312-313 |
| **Verified vs assumed** % | Share of counted units physically counted | UI: `round(VerifiedUnits / (VerifiedUnits + AssumedUnits) × 100)`, 0 when denominator ≤ 0. Server: `VerifiedUnits = Σ CountedQty of case nodes with VerificationLevel 'I' + Σ LooseItems.CountedQty`; `AssumedUnits = Σ CountedQty of case nodes with level 'C' (sealed case) or 'P' (sealed pallet roll-down)` | UI-WH html:67-78, ts:236-242 → API-LPN:314-320 |
| Sub-line "`n` counted · `m` assumed from sealed LPNs" | raw `verifiedUnits`, `assumedUnits` (no number formatting) | as above | UI-WH html:75-77 |
| Class counters (Matched, Quantity variance, Missing, Extra / unknown, Misplaced, Unverified) | Count per reconcile class; click filters the lists | `countFor(k) = summary.classCounts[k] ?? 0`; server `ClassCounts[k] = count(AuditLPNReconciliation rows with ReconcileClass = k)` — rows of **mixed grain** (see F10) | UI-WH html:82-96, ts:56-93, 203-205 → API-LPN:323-325; `AuditLPNReconciliationService.cs`:219, 331, 355, 374, 412 |

The SKU-level blocks below (Category/Overall charts) are hidden for warehouse audits
(`*ngIf="!isQuickAudit && !isWarehouseAudit"`, UI-H:553).

---

## 3. Audit Details card — UI-H:217-346 (desktop), UI-M html:21-63 (mobile)

API model: `GetAuditSummaryModel` (`Models/Audit/AuditModels.cs`:243-269). Built by
`BuildHeaderSection` (API-SS:393-407), `CalculateOverallProgress` (API-SS:433-464),
`PopulateAuditDates` (API-SS:421-431), plus Frequency / ItemGroup at API-SS:80-101.
All reads are scoped `CompanyId`, `BranchId`, `AuditId`, `IsActive = true`.

| Field (label) | What it shows | Formula | Source (UI → API → data) |
|---|---|---|---|
| **Audit Name** | Audit's name, truncated to 20 chars (+"..."); full name in tooltip | `obj.auditName = Audit.AuditName` | UI-H:234-235 → API-SS:399 (`Audit` where `AuditId, CompanyId, IsActive`, API-SS:130-133). Quick: `summary.auditName` = `Audit.AuditName` (API-QA:1235-1237, 1306) |
| **Date & Time** | When the audit was **created** (not when counting started/ended), `yyyy-MM-dd HH:mm` (mobile: `date:'short'`) in company time zone | `obj.stockAuditDate = Audit.CreatedDate` (stored UTC) → interceptor converts UTC → company tz | UI-H:244-245 → API-SS:402. Quick: `AuditDate = audit.CreatedDate` (API-QA:1307) |
| **Auditor(s)** | Comma list of auditor names, truncated to 20 chars | `Auditors = join(", ", for each GUID in AuditSettings.Auditor: user ? FirstName+" "+LastName : "Unknown")`; user list = `User ⋈ UserCompanyMapping` where `ucm.CompanyId = company AND ucm.IsActive AND u.IsActive` | UI-H:257-258 → API-SS:394-395, 405, 409-418, 155-172. Quick: names of users whose id ∈ `AuditSettings.Auditor` (no company/IsActive filter; unknown ids silently dropped) API-QA:1245-1257 |
| **Group** (desktop only) | Item group name, or `Not Assigned` | `obj.itemGroup = data.itemGroup ?? parentData.auditObj.itemGroup`; server `ItemGroup = ItemsGroup.GroupName where ItemsGroupId = Audit.GroupItems` (no IsActive filter). UI fallback text `'Not Assigned'` when falsy | UI-H:270-271; UI-T:931 → API-SS:101. Quick: `QuickAuditSummaryDTO` has no ItemGroup → always `Not Assigned` (F8) |
| **Cross-Auditor** (mobile only; desktop tile was replaced by Group, UI-H:272-274 commented) | Names of plan cross-check auditors or `Not Assigned` | `CrossAuditor = names(AuditPlan.CrossCheckAuditor)` (same name rule as Auditor(s)); `null` plan → empty | UI-M html:52-55 → API-SS:115, 406 |
| **Audit Type** | Configuration name of the audit | Template: `(auditObj.configurationName ∈ {'Investigation Audit','Partial Count'} OR auditObj.type ∈ {'Investigation Audit','Ad-Hoc Audit'}) ? (auditObj.configurationName ‖ auditObj.type) : obj.auditType`; server `AuditType = Audit.ConfigurationName`. Net effect: always `Audit.ConfigurationName` (F6). Quick: literal `"Quick"`. Mobile: `obj.auditType` directly | UI-H:283-288 → API-SS:401; API-QA:1313 |
| **Frequency - Mapping Type** (mobile: two cells "Frequency", "Mapping") | `<frequency> - <mapping>` | `Frequency = Frequency.FrequencyName where FrequencyId = AuditPlan.FrequencyId`; if the plan is not found (plan null, inactive, or other branch) → `"Manual"`. `MappingType = AuditSettings.AuditMappingType` ∈ {`Random`,`ByCategory`,`ByStorage`,`ByLocation`}; UI maps `trim(mappingType) == 'bystorage'` → `'ByLocation'` (never matches — F1). Quick: Frequency `"Manual"`, Mapping from AuditSettings | UI-H:297-299; UI-M html:56-63 → API-SS:78-90, 398; API-QA:1312, 1314; values: `audit-status.service.ts`:93-98 |
| **Progress** (bar + "`n`% Completed") | Weighted completion of the audit | Server (standard): <br>`assignedQty = Σ StockSource.StockQty` (active rows of this audit)<br>`completedQty = Σ g.AuditedQty + Σ g.DamagedQty` over **grouped audited lines** `g` (AuditLineItems active, `AuditedQty != null`, grouped by ItemCode + AuditStockLocation [+ BatchNo for Batch/Serial]; quantities summed)<br>`totalItems = count(StockSource rows)`<br>`auditedItems = count(distinct ItemCode among g with AuditedQty > 0)`<br>`lineItemProgress = totalItems = 0 ? 0 : auditedItems / totalItems × 25`<br>`quantityProgress = assignedQty = 0 ? 0 : completedQty / assignedQty × 75`<br>**`Progress = min(100, lineItemProgress + quantityProgress)`** (unrounded double).<br>UI: bar width = raw value %; label = `obj.overallProgress > 100 ? 100 : (obj.overallProgress | number:'1.0-0')` → **rounded half-up** to integer. Quantities are base-unit `AuditedQty` / `StockQty` (no UOM conversion here; `UOMQty` is not used). Recount / cross-check quantities are **not** considered (cross-audit list is commented out, API-SS:113). Divide-by-zero guarded.<br>Quick audit: same weights but `completedQty = Σ AuditedQty` only (**damaged excluded**), lines not grouped, and **`Math.Ceiling`** applied before the 100 cap (F3) | UI-H:311-321; UI-M html:39-45 → API-SS:123, 228-242, 433-464; API-QA:1279-1303 |
| **Status** (pill) | Primary audit status label + colour | `obj.auditStatus = Audit.PrimaryAuditStatus`; label via `getAuditStatusLabel`: N→Not Started, S→Stock Sheet Updated, I→In Progress, C→Completed, A→Auto Completed, E→Expired, K→In Resolution, anything else→**Unknown** (incl. `H` Archived — F2). Colours: I warning, S secondary, C success, N danger, A info, E dark, K `#7C0000` | UI-H:330-341; STL:1-20; CSS:425-428 → API-SS:401. Quick: `summary.auditStatus` (API-QA:1308) |

Hidden / computed-but-not-displayed fields of the same model (for completeness): `AuditNumber`
(1-based index of this audit among the plan's active audits ordered by `CreatedDate`, API-SS:397-398),
`ClosureNotes`, `MinDate`/`MaxDate` (min/max `UpdatedDate` of audited lines) and the client-side
`timing = calculateDateDifference(minDate, maxDate)` (UI-T:792-795) — the "Timing", "Stock Value",
"Stock Loss Value", "Damaged Value" header fields are all commented out (UI-H:136-216).

---

## 4. Auditor Summary dialog ("Auditor Insights") — UI-H:350-526; mobile sheet UI-M html:470-545

One row per auditor id in the **request's** `auditors` string (standard) or in
`AuditSettings.Auditor` (quick). Search box filters on
`auditorName, completedInventoryCount, auditedValue, damagedValue, elapsedTime, auditorStatus, progress`
(UI-H:399-401). Refresh button re-calls the API; auto-refresh every 30 s while open.

Notation (standard audit, API-AS:3634-4113):
- `L` = active `AuditLineItems` of the audit (company, branch), **grouped** by
  (ItemCode, AuditorId, BatchNo, Id1Name, Id2Name, Id3Name) with `AuditedQty = Σ`, `DamagedQty = Σ`,
  `CreatedDate = first row's CreatedDate` (API-AS:3672-3699). `L_a` = rows of `L` for auditor *a*.
- `S` = active `StockSource` rows of the audit.
- `A_a` ("assigned stock") per mapping type: **ByCategory** → `S` rows whose ItemCode is in a
  `StockSource` row whose `ItemCategoryId` ∈ auditor's mapped category ids; **ByStorage** → `S` rows whose
  ItemCode is in the **live item master** list (`GetItemWithBranch_New`) with `Storage` ∈ auditor's mapped
  storages; **Random** → stock rows this auditor counted (>0) + an equal slice of the not-yet-counted stock
  rows (`count / #auditors`, remainder to the last auditor) (API-AS:3730-3836). `ByLocation` matches none of
  the branches → `A_a` empty.
- `cost(item)` = `CostPrice` from the **live item master** (`ItemWithBranchDetailsResDTO.CostPrice`,
  first occurrence per ItemCode, case-insensitive), 0 if absent (API-AS:3847-3853).

| Column | What it shows | Formula (standard) | Formula (quick) | Source |
|---|---|---|---|---|
| **Auditor** | Auditor full name (truncated 20) | `trim(FirstName + " " + LastName)` from `User` by id (no company / IsActive filter) | same, joined to `UserCompanyMapping` on company | UI-H:460-462 → API-AS:4073-4076; quick 3546-3550 |
| **Completed Inventory** | **Quantity** (not an item count) counted by the auditor | `Σ AuditedQty over L_a where AuditedQty > 0` — damaged excluded; not restricted to `A_a` (includes items outside the auditor's assignment and items not on the stock sheet) | `Σ Audit.AuditedQty` over assigned stock rows (first matching line per ItemCode) | UI-H:464 (`formatAuditQuantity`, null→0) → API-AS:3840-3845; quick 3512 |
| **Audited Value** | Value of what the auditor counted | `Σ over (L_a ⟕ A_a on ItemCode+Batch+Id1..3) of AuditedQty × cost(ItemCode)` — a line matching *n* assigned stock rows is counted *n* times (F5) | `Σ Audit.AuditedQty × StockSource.CostPrice` over assigned rows | UI-H:466 (`formatAuditValue`) → API-AS:3992-4050; quick 3531 |
| **Damaged Value** | Value of damaged qty recorded by the auditor | `Σ (same join) DamagedQty × cost(ItemCode)` | `Σ Audit.DamagedQty × StockSource.CostPrice` | UI-H:467 → API-AS:4050; quick 3532 |
| **Elapsed Timing** | `HH:mm` (hours can exceed 24) between the auditor's first and last count | `min/max(CreatedDate) over L_a` (each group's *first* row's CreatedDate); if min = max → `UtcNow − min` (still running clock); format `$"{(int)TotalHours:00}:{Minutes:00}"`; `00:00` when no lines | same, using `max(CreatedDate)` per (ItemCode, Auditor) group over assigned rows | UI-H:469 → API-AS:4054-4072, 4107; quick 3534-3546 |
| **Progress** | Auditor's weighted completion (bar capped 100, label `number:'1.0-0'` rounded) | `auditedCount = count(L_a rows with AuditedQty > 0)`; `lineItem = |A_a| = 0 ? 0 : auditedCount / |A_a| × 25`; `qty = Σ A_a.StockQty = 0 ? 0 : CompletedInventory / Σ A_a.StockQty × 75`; `Progress = min(100, lineItem + qty)` (no rounding server-side) | same weights over assigned rows; `Math.Ceiling` then cap 100 | UI-H:471-477 → API-AS:3896-3916; quick 3510-3523 |
| **Status** | Auditor status text | `"Completed"` if `Audit.AuditorStatus` JSON has `{AuditorId, Status:"Completed"}`; else `"Yet to Start"` if `auditedCount = 0 AND remainingCount = |A_a|`; else `"In Progress"` if `auditedCount > 0`; else `"Unknown"`. `remainingCount = count(A_a rows whose ItemCode the auditor has not counted > 0)` | same | UI-H:479 → API-AS:4062-4071, 3918-3923; quick 3537-3545 |
| **Action** | `Reopen` (status lower-case `complete`/`completed`) or `Finish` | disabled when `obj.auditStatus ∈ {'K','C'}` | — | UI-H:480-495 |
| **Total** row | Column totals | `getTotal(f) = Σ Number(row[f])` over **all** `Auditdata` (not the search-filtered rows — F9); shown only when not loading and (filtered or full) list non-empty; Elapsed/Progress/Status/Action show `--` | — | UI-H:503-520; UI-T:1440-1447; mobile `auditorTotal` UI-M ts:402-407 |

Returned but not displayed: `AssignedInventoryCount (= Σ A_a.StockQty)`, `StockValue`,
`StockLossValue`, `ExcessValue`, `AuditedCount`, `RemainingCount`, `CrossCheckStatus`,
`StatusUpdatedDate` (columns commented out at UI-H:420-447, 465-470).

---

## 5. "Overall LineItem Category Wise" and "Overall LineItem Stocks" charts — UI-H:529-552

**Not rendered.** Both cards (and the "LineItem - <audit>" doughnuts / "Audit Cycle" pie) are inside
HTML comments guarded by `*ngIf="IsPerpetual"`. `IsPerpetual` is declared (UI-T:225) but never
assigned (`loadStatus()` is commented, UI-T:642-651), and `barItemData`, `pieItemData`, `barOptions`,
`pieOptions`, `auditCycleChartData` are not defined in the component (only a commented
`auditCycleChartModels` builder at UI-T:1370-1410). `GetAuditSummaryModel` has no fields that would
feed them (`Models/Audit/AuditModels.cs`:243-269). There is therefore no live formula to document; if
re-enabled they would need new API fields. (The live charts in this region are "Category Wise
Variance" / "Overall Variance", UI-H:553-583 — covered in part 2.)

---

## 6. Visibility matrix (this part)

| Block | Standard | Quick audit | Warehouse (`W`) | Mobile |
|---|---|---|---|---|
| Stock Audit button | yes | yes | **hidden** | n/a (own header) |
| Warehouse Count block | no | no | **yes** | via host input |
| Audit Details card | yes | yes (Group = Not Assigned, Type = Quick, Frequency = Manual) | yes | compact card (Cross-Auditor instead of Group) |
| Auditor dialog | yes | yes (quick branch of API) | yes | bottom sheet |
| Legacy LineItem charts | never | never | never | never |

Inventory type (Unit / Batch / Serial) affects only the server grouping key used by Progress
(BatchNo added for `B`/`S`, API-SS:186-262); nothing in this part hides or shows per inventory type.

---

## Findings

**F1 — "ByLocation" relabel never fires (desktop and mobile).** UI compares
`obj.mappingType.trim() == 'bystorage'` (UI-H:297-298; UI-M html:62), but stored values are PascalCase
`'ByStorage'` (`audit-status.service.ts`:96; API-AS:3491, `AuditLineItemsService.cs`:528). The tile shows
the raw `ByStorage` (and `ByCategory`, `Random`) instead of the intended "ByLocation".

**F2 — Archived audits show Status "Unknown".** The page is reachable for archived audits (Restore button,
UI-H:65), but `getAuditStatusLabel` has no `'H'` case and the pill has no `'H'` colour (STL:1-20;
UI-H:331-339). The mobile pill likewise.

**F3 — Three different "Progress" formulas.**
(a) Standard header: completed = AuditedQty **+ DamagedQty**, no rounding (API-SS:436-438).
(b) Quick header: completed = AuditedQty only, `Math.Ceiling` (API-QA:1286, 1299).
(c) Auditor rows: completed = AuditedQty only (damaged excluded) (API-AS:3840-3845, 3912-3913).
So an auditor who records stock as damaged raises the audit's progress but not their own, and the sum of
auditor quantities never reconciles with the header. Also in (a) the item term mixes units:
numerator = distinct counted ItemCodes (including items **not on the stock sheet**), denominator =
StockSource **rows** (one per location/batch), so a multi-location/batch item that is fully counted can
still be under-weighted, and excess items/quantities inflate progress (only the 100 cap stops it). The UI
then **rounds half-up** (`number:'1.0-0'`, UI-H:319-320), e.g. 99.5 → "100% Completed" on an unfinished
audit, while every other number on the page is truncated (FMT:54-56).

**F4 — Auditor values priced from the live item master, not the audit's snapshot.** Standard Audited /
Damaged Value use `costDict` from `GetItemWithBranch_New` (API-AS:3698-3700, 3847-3853, 4040-4050),
whereas the rest of the summary (and the quick branch) uses `StockSource.CostPrice`. A cost change after
the stock sheet was imported changes the auditor values but not the report values, so the auditor
"Total" will not match the Complete Audit Report's Audited/Damaged Value. The ByStorage assignment
likewise reads live `ItemBranchDetails.Storage` (API-AS:3772) while ByCategory uses the StockSource
snapshot (API-AS:3742-3749) — contrary to the audit-isolation rule cited in the code comments.

**F5 — Audited/Damaged Value can be multiplied by duplicate stock rows.** `auditWithStock` left-joins each
grouped line to `A_a` on ItemCode+Batch+Id1..3 **without location** (API-AS:3992-4047). An item that has
the same key at two stock locations yields two joined rows per audit line, so its AuditedQty × cost is
counted twice. Same pattern in the quick Random branch (join on ItemCode only, API-AS:3480-3494).

**F6 — Audit Type special-case is dead code.** The literal `'Investigation⏎ Audit'` in UI-H:284-285 is
split across a line break, so it contains a newline and indentation and can never equal
`'Investigation Audit'`. Harmless in practice only because both branches resolve to
`Audit.ConfigurationName` (API-SS:401).

**F7 — Two sources of truth for status; tile can go stale.** Header buttons use
`PrimaryAuditStatus` (from `parentData`), while the Status tile and the auditor Reopen/Finish lock use
`obj.auditStatus` (from the summary API). After **Complete Audit** on a warehouse audit the code sets
`PrimaryAuditStatus = 'K'` (UI-T:2946-2953) but does not refresh `obj`, so the tile keeps showing the old
status and the auditor Finish/Reopen links stay enabled (they are only disabled for `obj.auditStatus` K/C,
UI-H:486-493 — and never for `A` Auto Completed or `H` Archived).

**F8 — Quick audit "Group" is always "Not Assigned".** `QuickAuditSummaryDTO` has no ItemGroup
(`Models/Audit/QuickAuditModels.cs`:91-105) and the fabricated quick `auditObj` has none either
(UI-T:426-439), so the fallback text always shows even though the audit has an item group.

**F9 — Auditor "Total" ignores the search filter.** The footer is shown based on
`auditorSummaryTable.filteredValue.length` but `getTotal` sums the unfiltered `Auditdata`
(UI-H:504-512; UI-T:1440-1447). After searching for one auditor, the Total row still shows everyone.

**F10 — Warehouse class counters count reconciliation rows of mixed grain.** `ClassCounts[k]` counts
`AuditLPNReconciliation` rows (API-LPN:323-325), which are one per (case, item) for cases, one per pallet
for unscanned/unknown pallets, and one per ItemCode for loose items
(`AuditLPNReconciliationService.cs`:219, 331, 355, 374, 412). A "Missing 5" can mean 3 cases + 1 pallet + 1
loose SKU, and a multi-SKU case counts once per SKU — while the Cases tile counts cases.

**F11 — Warehouse "Blind count" chip renders without a loaded summary.** The chip is outside the
`*ngIf="summary"` guard and uses `!!summary?.showStockToAuditor` (UI-WH html:6-8, ts:245-247). While
loading, or after `/lpn/summary` fails (error toast only), it shows a confident "Blind count" — the same
trap the module's invariant §2.9 forbids for `isBlindCount` (`StockountAPI/docs/warehouse-lpn-module.md`:134-143).

**F12 — `/lpn/summary` is not tenant-scoped.** `AuditLPNService.GetSummary` loads `Audit`,
`AuditSettings`, `AuditLPN`, `StockSource` and `AuditLPNReconciliation` by `AuditId` only — no
`CompanyId`/`BranchId` filter against the caller (`AuditLPNService.cs`:559-583), unlike
`GetAuditSummary` and `GetAuditorSummary`.

**F13 — Inconsistent auditor sources / name rules.** Header "Auditor(s)" comes from
`AuditSettings.Auditor` and prints `"Unknown"` for a user deactivated in the company
(API-SS:155-172, 409-418); the auditor table iterates the **client-supplied** `auditObj.auditors`
(= `Audit.Auditors`, API-AS:3702) and resolves names without IsActive/company filter (API-AS:4073-4076);
the quick header silently drops unknown ids (API-QA:1253-1257). The same person can therefore appear
as "Unknown" in the header and by name in the table, and the two lists can differ if
`Audit.Auditors` and `AuditSettings.Auditor` diverge.

**F14 — Header crashes the loader on a missing/inactive audit.** `GetAuditSummary` returns a successful
empty model when the audit is not found (API-SS:76) with `ChartData`/`CategoryChartModel` null; the UI
immediately calls `data.chartData.filter(...)` / `data.categoryChartModel.map(...)` (UI-T:806, 857) without
a guard, so the `next` handler throws and `auditSummaryLoader` is never reset (skeletons stay forever).
A missing `AuditSettings` row would instead throw a NullReferenceException in `BuildHeaderSection`
(API-SS:398, 405).

**F15 — Latent double UTC conversion of Min/MaxDate.** `AuditLineItems.UpdatedDate` is written as
`DateTime.UtcNow` (`AuditLineItemsService.cs`:638), but `PopulateAuditDates` passes it through
`ConvertToUtc(…, companyTz)` as if it were company-local (API-SS:427-428). Only the hidden `timing`
uses them today (a difference, so unaffected), but any future display of MinDate/MaxDate would be off by
the company's UTC offset.
