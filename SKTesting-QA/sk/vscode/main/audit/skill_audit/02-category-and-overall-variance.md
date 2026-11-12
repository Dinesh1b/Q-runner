# Audit Summary: Category Wise Variance and Overall Variance (part 2 of 3)

Scope: the chart band on the web Audit Summary page. On desktop it is two cards side by side: **Category Wise Variance** (stacked bar) and **Overall Variance** (doughnut). On mobile it is one "Variance" card with **Category-wise** and **Overall** tabs. Both layouts use the same chart objects. Not covered here: the Audit Details/KPI tiles and the Complete Audit Report or Complete Audit.

Abbreviations used in file references:
- UI = `/home/user/stockount_UI/src/app/home/audit/audit-summary/`
- API = `/home/user/StockountAPI/`
- SVC = `API/Services/AuditSummaryService.cs`

---

## 0. Data pipeline (shared by both charts)

| Step | What happens | Source |
|---|---|---|
| Rendered when | Desktop: `*ngIf="!isQuickAudit && !isWarehouseAudit"`. Each card has `*ngIf="!auditSummaryLoader"`, and a skeleton shows while it loads. Mobile: `*ngIf="!isQuickAudit"` only, so it also renders for Warehouse audits (see F9). | UI `audit-summary.component.html:553,556,566`; UI `audit-summary-mobile/audit-summary-mobile.component.html:82-94` |
| Desktop vs mobile | `*ngIf="!isMobile; else mobileSummaryTpl"`. The mobile component receives `categoryChartData/Options` and `overallChartData/Options` as `@Input`s. Mobile tab default is `activeChartTab = 'category'`. | UI html `:18, :2345-2348`; mobile ts `:58-61, :103, :148-150` |
| UI call | `getAuditSummary()` → `auditService.getAuditSummary(auditId, companyId, branchId)`. `branchId` = `StorageKeysService.getBranchId()` (the branch currently selected in the browser). | UI `audit-summary.component.ts:726-729, 778-784` |
| HTTP | `GET {apiUrl}/audit/getAuditSummary/{auditId}/{companyId}/{branchId}` | `stockount_UI/src/app/services/audit.service.ts:109-110` |
| Controller | `AuditController.GetAuditSummary` → `_auditSummaryService.GetAuditSummary` | API `Controllers/AuditController.cs:1297-1304` |
| Service | `AuditSummaryService.GetAuditSummary`: loads data, then calls `BuildChartData` (Overall) and `PopulateCategoryChartData` (Category). Pure C#/LINQ. No stored procedure, function or view is involved; nothing in `DBAPP_SK_MAIN` feeds these charts. | SVC `:72-139` |
| Stock rows | `StockSource` rows with `CompanyId, BranchId, AuditId` matching and `IsActive`. This is the audit's own stock-sheet snapshot. | SVC `:215-219` |
| Count rows | `AuditLineItems` rows with `CompanyId, BranchId, AuditId` matching and `IsActive`. Superseded recount rows are `IsActive = 0` and drop out. Then `GetAuditedLineItemsListAsync` keeps only rows with `AuditedQty != null` and groups them by `(ItemCode, AuditStockLocation)`, or by `(ItemCode, BatchNo, AuditStockLocation)` for BATCH/SERIALIZED groups. It sums `AuditedQty` and `DamagedQty`. Id1-3 come from the first row in each group. | SVC `:200-204, 221-302` |
| Category list | Distinct `(ItemCategoryId, Category)` from the same audit's active `StockSource` rows where `ItemCategoryId != null`. It is not read from the `ItemsCategory` catalog. | SVC `:140-160` |
| Response fields used | `data.chartData[]` (`{name, value, percentage}`) and `data.categoryChartModel[]` (`{categoryName, stockLoss, excessValue, damagedValue, auditedValue, matchValue}`). Model: `Models/Audit/AuditModels.cs:243-286`. | |

### Common definitions (server)

| Term | Definition | Source |
|---|---|---|
| **Cost** (the only price used) | `Cost(item) = MAX(StockSource.CostPrice)` over all of the audit's stock rows for that `ItemCode`. Item codes are compared case-insensitively, and NULL counts as 0. This is the cost price from the stock-sheet snapshot. Selling price, MRP and the live item master are **not** used. An item with no stock-sheet row has Cost = 0. | SVC `:684-692` (overall), `:1101-1109` (category) |
| **StockQty** | `StockSource.StockQty`, in the primary (base) UOM. `StockSource.UOMQty` (the sheet's own UOM quantity) is ignored. | SVC `:697-713` |
| **AuditedQty** | `AuditLineItems.AuditedQty`, in the primary UOM (`UOMQty` is the counted-UOM expression and is ignored here). Repeated counts are summed. | SVC `:221-302`; `AuditLineItemsService.cs:1489-1495` |
| **Grain of the variance** | **Per ItemCode.** Quantities are first keyed by `ItemCode|Id1|Id2|Id3|BatchNo`, then **summed per ItemCode** before excess, loss and match are worked out. Locations, batches, serials and Id1-3 variants of the same item **net off against each other**. | SVC `:697-737, 800-812` (overall); `:1120-1128, 1203-1216` (category) |
| **Damaged qty** | Not added to and not subtracted from AuditedQty for match, loss or excess. It only produces a separate `DamagedValue = Σ DamagedQty × Cost`, which these charts **do not display** (the UI filters it out and the "Damaged Value" dataset is commented out). | SVC `:771-777, 1193-1194`; UI ts `:804, 860, 879-884` |
| **Recount** | An accepted recount (`Status 'A'`) sets all earlier rows to `IsActive = 0` and `RecountAction = 'S'`, then inserts a new row with `AuditedQty = ReCountAuditQty` and `DamagedQty = ReCountDamagedQty`. The charts therefore show the recount result once it is accepted. While a recount is pending, the original count stays. | `AuditService.cs:6449-6578` |
| **Cross-check** | `CrossAuditItems` is **not read** (the `GetCrossAuditItemsListAsync` call is commented out). Cross-check counts never affect these charts. | SVC `:96, 307-363` |
| **Not-audited items** | An item code with no counted row is **skipped entirely**. It contributes nothing to Available, Loss or Excess, but it is still inside Total Stock Value. | SVC `:821-825`; `:1203-1204` |
| **LPN / Warehouse** | Uses the same `AuditLineItems` that LPN reconciliation writes, including pallet roll-down and sealed-case credited rows. `VerificationLevel` is not distinguished. The desktop hides the charts for Warehouse audits, but mobile shows them. | — |

---

## 1. Category Wise Variance (stacked bar)

UI: `audit-summary.component.html:556-557` (`<p-card header="Category Wise Variance">`, `<p-chart type="bar">`). Data is built at `audit-summary.component.ts:857-925`. API: `PopulateCategoryChartData`, SVC `:1090-1230`.

For each category C returned by `GetItemCategories`, take that category's item codes. These are the distinct `ItemCode`s of stock rows with `ItemCategoryId = C`, compared case-insensitively (SVC `:1112-1118`). For each item code i **that has at least one counted row** (SVC `:1203`):

```
S(i) = Σ StockSource.StockQty   for ItemCode i (all locations / batches / serials)
A(i) = Σ AuditLineItems.AuditedQty for ItemCode i (all locations / batches / serials)
```

| Field (on screen) | What it shows | Formula | Source (UI → API → code) |
|---|---|---|---|
| X-axis label | Category name, as stored on the stock sheet | `StockSource.Category` for each distinct `(ItemCategoryId, Category)` pair. Rows with `ItemCategoryId IS NULL` are excluded, so there is **no "Uncategorised" bar**. | UI ts `:857` `item.categoryName` → SVC `:150-158, 1219-1221` |
| Series **"Available  Value"** (green `#5dc271`) | Value of the expected stock that was found | `Σ_i min(S(i), A(i)) × Cost(i)`, rounded to 4 dp (`Math.Round` default, banker's rounding) | UI ts `:861, 867-871` → SVC `:1212, 1226` |
| Series **"Stock Loss"** (red `#f76a68`) | Value of the shortage (negative variance), drawn as a **positive** number | `Σ_i max(S(i) − A(i), 0) × Cost(i)`, rounded to 4 dp | UI ts `:858, 872-876` → SVC `:1214-1215, 1222` |
| Series **"Excess Value"** (blue `#61b5fb`) | Value of the surplus (positive variance) | `Σ_i max(A(i) − S(i), 0) × Cost(i)`, rounded to 4 dp | UI ts `:859, 877-881` → SVC `:1209-1210, 1223` |
| Bar total height | Not labelled | `Available + Loss + Excess` = `Σ S(i)×Cost` for **audited** items + Excess. Both axes are `stacked: true`. | UI ts `:903-916` |
| Tooltip | All 3 series for the hovered category (`mode: 'index', intersect: false`) | `"<series label>: " + formatAuditNumber(raw, 'value')`. This **truncates** (does not round) to 2 dp, drops trailing zero decimals, and adds no thousands separator or currency. | UI ts `:891-900`; `home/audit/shared/audit-number-format.util.ts:25-63`; `DataSharingName.ts:12` |
| Y-axis | Value in the company currency | Chart.js default ticks. No currency symbol and no formatter. | UI ts `:910-916` |
| Legend | The 3 series labels, Chart.js default (top) | — | — |
| Returned but not shown | `damagedValue` = `Σ DamagedQty × Cost`; `auditedValue` = `Σ AuditedQty × Cost` | SVC `:1191-1195, 1224-1225`. Commented out in UI ts `:860, 882-886`. | |

The legacy dropdown `pieCategory` / `obj.catoryWisePieChart` / `loadCategoryPieChart` is **dead**. The dropdown is HTML-commented (`audit-summary.component.html:570-574`). `loadCategoryPieChart` and `pieCategory` do not exist in the TS. The API no longer returns `catoryWisePieChart`; its only reference is the commented-out legacy code at `API/Services/AuditService.cs:2664`.

---

## 2. Overall Variance (doughnut)

UI: `audit-summary.component.html:566-577` (header text "Overall Variance", `<p-chart type="doughnut">`). Data is built at `audit-summary.component.ts:797-853`. API: `BuildChartData`, SVC `:673-888`.

For every item code i that appears in StockSource or in the counted rows (SVC `:790-794`), using S(i), A(i) and Cost(i) as above, **skip i if it has no counted row** (SVC `:821-825`).

| Field (on screen) | What it shows | Formula | Source |
|---|---|---|---|
| Denominator (not shown) `StockValue` | Value of the whole stock sheet | `TotalStockValue = Σ over all StockSource rows of StockQty × Cost(ItemCode)`, rounded to 4 dp (half away from zero). This **includes items that were never counted**. Also returned as `model.StockValue` (the KPI tile, part 1). | SVC `:752-762, 850-855, 885` |
| Slice **"Available  Value"** (green) | Share of stock value found | `Value = Σ_i min(S,A)×Cost`; `% = min(100, round(Value / TotalStockValue × 100, 2))`, or 0 when TotalStockValue ≤ 0 | UI ts `:799, 804-826` → SVC `:830, 841, 845-848, 878-883` |
| Slice **"Stock Loss"** (red) | Share lost (negative variance, shown positive) | `Value = Σ_i max(S−A,0)×Cost`; same % formula | UI ts `:800` → SVC `:832-833, 839, 871-876` |
| Slice **"Excess Value"** (blue) | Surplus (positive variance) relative to stock value | `Value = Σ_i max(A−S,0)×Cost`; same % formula. **Capped at 100**. | UI ts `:801` → SVC `:827-828, 838, 857-862` |
| Slice size (what is drawn) | Chart.js `data` = the three **percentages**. Each slice is drawn at `pct_k / (pct_Avail + pct_Loss + pct_Excess)` of the circle. | | UI ts `:818-826` |
| Slice order and colours | Fixed `order = ['MatchValue','LossValue','ExcessValue']`, colours green/red/blue by position. Server names are mapped to the labels above. `StockValue` and `DamagedValue` are filtered out. | | UI ts `:798-816, 823` |
| Tooltip | Two lines: ` Value: <formatAuditNumber(value,'value')>` and ` Percentage: <formatAuditNumber(percentage,'value')>%`. Both truncate to 2 dp. The percentage is the server's share of TotalStockValue, **not** the drawn share of the doughnut. | | UI ts `:837-847` |
| Legend | Top. The `labels.display:false` option is not a Chart.js option, so the legend is still shown. | | UI ts `:831-836` |
| Hole | `cutout: '50%'` | | UI ts `:852` |

### Filters / dropdowns

| Control | Options | Default | Effect | Source |
|---|---|---|---|---|
| Category dropdown (`pieCategory` ← `obj.catoryWisePieChart`, `optionLabel=name`, `optionValue=data`, placeholder "Choose Category") | none | — | **Commented out / dead**. The handler `loadCategoryPieChart` does not exist, and the API does not return `catoryWisePieChart`. | UI html `:570-574` |
| Mobile chart tabs: "Category-wise" / "Overall" | `'category'`, `'overall'` | `'category'` | Switches which `p-chart` is rendered. The data is identical. | mobile html `:85-92`, ts `:103,148-150` |
| Implicit filters | Current browser branch (`branchId`); `IsActive` rows; `AuditedQty != null`; categorised stock rows only (category chart) | — | No user control | see §0 |
| "Summarize As", column filters, badges | — | — | **Do not affect** these charts. The chart data comes only from `getAuditSummary`. | UI ts `:726-925` |

---

## 3. Worked example

Stock sheet: item P (Cost 10), loc A = 10, loc B = 10; item Q (Cost 5) = 20, never counted. Counted: P at loc A = 15, P at loc B = 5.

- S(P) = 20 and A(P) = 20 → Available = 200, Loss = 0, Excess = 0, even though there are two variance lines (+5 and −5).
- TotalStockValue = 200 + 100 = 300 → Available % = 66.67.
- Doughnut data `[66.67, 0, 0]` → drawn as a **100 % green** ring. The tooltip says 66.67 %.

---

## Findings

| # | Finding | Evidence | Effect |
|---|---|---|---|
| F1 | **The doughnut's drawn proportions do not match its own percentages.** Percentages are shares of TotalStockValue, which includes un-counted items. Loss is measured only on counted items, and Excess is added on top (capped at 100). Chart.js then normalises the three numbers to fill 360°. | SVC `:752-762, 821-825, 845-848`; UI ts `:818-826` | A half-counted audit with no variance draws a full green ring. When Excess is large, the "Available" slice shrinks. The visual and the tooltip disagree. |
| F2 | **Un-counted stock is not "Stock Loss".** An item with no counted row is skipped in both charts, so an item nobody counted (or an item missing from the shelf where nobody recorded a 0) never shows as loss. | SVC `:821-825, 1203` | Shortage is understated while counting is in progress, and permanently for items left uncounted. This is most visible in the category chart, which has no denominator. |
| F3 | **Variance is netted per ItemCode across locations, batches, serials and Id1-3.** | SVC `:800-812, 1205-1206` | Offsetting variances (+5 at A, −5 at B; or batch X +3, batch Y −3) show as fully "Available". The chart totals are lower than the line-level variances in the Complete Audit Report or Manage Summary, and lower than the stock adjustment, which works per item + batch + location line (`Services/Audit/Adjustment/AuditAdjustmentLineBuilder.cs:168-203`). |
| F4 | **Cost basis differs from the adjustment.** The charts use `MAX(CostPrice)` per item over all sheet rows. The adjustment uses the matched row's own `CostPrice`. | SVC `:684-692`; `AuditAdjustmentLineBuilder.cs:181,203` | Items with batch- or location-specific costs are valued higher in the charts than in the adjustment. |
| F5 | **Excess on items not on the stock sheet is worth 0.** Cost only comes from StockSource, so an item that was counted but is not on the sheet gets Cost = 0. In the category chart such items appear nowhere, because categories also come from StockSource. | SVC `:684-692, 819, 1112-1118` | Found-but-unlisted stock is invisible in value terms. |
| F6 | **Case-sensitivity mismatch in Overall.** The `itemCodes` set is `OrdinalIgnoreCase`, but `stockQtyByItem` and `auditedQtyByItem` are `Ordinal`. If a sheet row is `abc` and the count is `ABC`, the set keeps one spelling. The lookup with the other spelling fails, `continue` is hit, and the item drops out (neither loss nor excess). The category chart has the same problem: `auditsByItem` and `stockByItem` use the default comparer. | SVC `:790-812, 821-825, 1120-1128` | Silent omission whenever item-code casing differs between the sheet and the counts. |
| F7 | **Duplicate or ambiguous category bars.** Categories are grouped by `(ItemCategoryId, Category)`. If one id has two different `Category` texts on the sheet, there are two bars, each computed over the whole id's items (identical values, double counted). Two ids with the same name produce two bars with the same label. An item whose rows carry different categories is counted in each. | SVC `:152, 1112-1118, 1143-1146` | The sum of the category bars can differ from Overall. |
| F8 | **Category chart excludes uncategorised items** (`ItemCategoryId IS NULL`). There is no "Uncategorised" bar. | SVC `:151, 1113` | The sum of the bars is less than the Overall values. Users have no indication of this. |
| F9 | **Mobile shows the charts for Warehouse (LPN) audits; desktop hides them.** The mobile template only checks `!isQuickAudit`, although `isWarehouseAudit` is passed in. | UI html `:553` vs mobile html `:82` | Platform inconsistency. On LPN audits the values include assumed (roll-down / sealed-case) quantities without any marking. |
| F10 | **Failure leaves an endless skeleton.** If `resp.data` is missing or `chartData`/`categoryChartModel` is null (for example when the audit is not found, the API returns an empty model with null lists, SVC `:75`), `data.chartData.filter(...)` throws inside `next`. `auditSummaryLoader` is never reset and `error` is not called. | UI ts `:786-806, 857, 936-940` | The chart area shows skeletons forever. No error is shown. |
| F11 | **Branch comes from the browser, not the audit.** `branchId` is the currently selected branch. StockSource and AuditLineItems are filtered by it. | UI ts `:728`; SVC `:200-204, 215-219` | If the user switches branch, the charts and Stock Value show zeros (all percentages 0 → empty doughnut). There is no warning. |
| F12 | **Damaged qty is ignored for variance**, and the DamagedValue series and slice are hidden. Older, commented-out code computed variance on `AuditedQty + DamagedQty` (`AuditService.cs:2426-2432`). Whether AuditedQty already includes damaged stock is not defined in code. The guide says "Record damaged stock separately instead of leaving it out of the count". | SVC `:771-777`; UI ts `:804, 860` | If auditors record damaged stock *instead of* including it in AuditedQty, it shows as Stock Loss. |
| F13 | **Excess % is capped at 100** and `TotalStockValue ≤ 0` gives every slice 0 %. | SVC `:845-848` | Doughnut slices are distorted or blank. The tooltip values are still correct. |
| F14 | **Display/rounding details.** The server rounds to 4 dp (Overall: half away from zero; Category: banker's rounding). The UI **truncates** to 2 dp with no thousands separator or currency symbol, and the y-axis is unformatted. The label "Available  Value" has a double space. The legend option `labels.display:false` has no effect. | SVC `:839-842, 1222-1226`; UI ts `:799, 835, 867`; util `:53-63` | Cosmetic. |
| F15 | Dead UI code: the category dropdown (`pieCategory`, `obj.catoryWisePieChart`, `loadCategoryPieChart`) is commented out and has no backing in the TS or the API. | UI html `:570-574`; `AuditService.cs:2664` (commented) | Can be removed. |
