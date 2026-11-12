# Audit Module — User Guide

## Overview

The Audit module is where you check that the stock you physically hold matches the stock your records say you hold. You plan an audit, auditors count items on the floor, and Stockount compares every count against the expected quantity to show what is matched, short or in excess.

When the counts are in, the module helps you investigate differences, recount where needed, record a resolution for each discrepancy and — where your setup allows — correct the stock records. Every audit ends with a completed, reportable record of what was counted, by whom and what was done about it.

Two kinds of people work in an audit:

- **Audit owners** (managers, supervisors, inventory controllers) create and configure audits, load the stock sheet, review results, resolve discrepancies and complete the audit.
- **Auditors** are assigned to an audit and count the stock, usually on a phone or handheld scanner.

The module supports several audit types — from a full count of everything to a quick spot check of a few items — so the same tool covers year-end stock takes, regular cycle counts and targeted investigations.

---

## Accessing the Audit Module

Open **Audit** from the application switcher at the bottom of the screen — it sits alongside Finance and Inventory. Everything you see is for the **branch** currently selected; audit plans and audits are managed separately for each branch, so switch branch to work on another location.

Inside Audit you will mainly use two screens:

| Screen | What you do there |
| --- | --- |
| **Audit Plans** | Create and manage recurring or one-time plans (Complete Count and Cycle Count), choose owners and auditors, and set counting rules. |
| **Audits** | See every audit, create quick, partial or investigation audits, and open an audit to configure, count, review or resolve it. |

The Audits screen has three tabs:

- **Ongoing Audits** — audits that are in progress, with counted vs. total lines and quantities, and how many lines are matched, short or in excess.
- **Audit History** — audits that have been completed.
- **Archived Audits** — older audits kept for reference.

Selecting an audit opens a short menu so you can jump straight to where you need to be:

- **Audit Summary** — review the progress, activities and overall status of the audit.
- **Settings** — import the stock sheet and configure audit controls.
- **Stock Audit** — perform and monitor the physical counting.

### Who can do what

| Role | Can do |
| --- | --- |
| **Administrator** | Everything in the company; treated as an owner on every plan. |
| **Audit Owner** | Full control of a plan and its audits: settings, stock sheet, review, resolution and completion. A plan can have more than one owner. |
| **Audit Contributor** | Can see everything about the audit and work on the resolution step, but cannot complete the audit. |
| **Auditor** | Is assigned to an audit and counts stock. Being an owner does not make you an auditor — add yourself as an auditor if you also need to count. |

> **Tip:** The screens, cards and buttons you can use depend on the permissions given to your role in **Role Management**. If something you expect is missing, ask your administrator to check your Audit and Audit Plan access.

First time here? Pick the **Demo Audit** from the audit list to take a guided tour of the whole counting workflow using sample data. A **Steps to complete the audit** panel (the **?** button) also appears on supported audits to show where you are and what to do next.

---

## Functionality

Every audit follows the same five-step journey. The audit owner drives steps 1, 2, 4 and 5; auditors do step 3.

1. **Create the audit** — name it, choose the item group, auditors and how work is split.
2. **Import the stock sheet** — load the expected stock the counts will be compared against.
3. **Count the stock** — auditors count items physically and record quantities.
4. **Review the summary** — see matched, short and excess lines and export reports.
5. **Resolve and complete** — decide what to do about each difference, settle stock corrections and close the audit.

A Quick Audit skips step 5: it is a spot check with no resolution phase.

### 1. Choosing the right audit type

| Audit type | Use it when | How it is created |
| --- | --- | --- |
| **Complete Count** | You want to count the entire item group — for example a year-end or periodic stock take. | From an Audit Plan |
| **Cycle Count** | The inventory is too large to count in one go, so you count it in segments (for example by location) on a regular schedule. | From an Audit Plan |
| **Partial Audit** | You want to count a chosen set of items — by category, location, batch, high-value items or items with past variances. | **Create Audit** on the Audits screen |
| **Investigation Audit** | You need to recount items that were flagged for investigation in an earlier audit. | **Create Audit** on the Audits screen |
| **Quick Audit** | You need a fast spot check — just scan and count, with no inventory set-up required. | **Create Audit** on the Audits screen |

When you create an audit you also choose a **counting method**:

- **Static** or **Dynamic** — available for a Complete Count; Partial Audits always use Static.
- **Location (Warehouse)** — for item groups that track stock by pallet and case labels (License Plate Numbers). Auditors scan pallets and cases rather than individual items only.

> **Not sure what to count?** Open the **Suggested Audits** tab in the Create Audit window and pick an item group. Stockount offers ready-made item lists — such as *Protect High Value Items*, *Protect Loss Values*, *Reduce Variances*, *Fix Erratic Audits*, time-boxed *Priority 15 / 30 / 60 min* lists and a random *Control Sample*. Pick one and it becomes a Partial Audit with those items pre-selected.

### 2. Creating an audit plan (Complete and Cycle Count)

1. Go to **Audit Plans** and select **Add Audit Plan**.
2. Enter the **plan name**, choose the **Item Group**, and add **Audit Owners** and, if needed, **Audit Contributors** with **Share**.
3. Choose the **stock source**:
    - **Real Time** — counts are compared with the stock Stockount already holds.
    - **Stock Report** — use this if you run your main transactions in another system; you upload that system's current stock report as the stock sheet.
4. Choose the **audit type** (Complete Count or Cycle Count) and the **frequency** — **Weekly** (on a set day), **Monthly** (on a set date) or **One-Time**. Set the start and end dates.
5. Set the **auto-completion days** — how long an audit may stay open before it closes automatically.
6. Select the **auditors**, then choose the counting rules (see the next section).
7. Choose a **mapping type** to divide the work: **Random** (anyone counts anything), **By Category** or **By Location** — then assign each auditor their categories or locations.
8. Save. Audits are then generated according to the plan's schedule.

From the Audit Plans list you can also **Rerun** a plan or mark a cycle as **Complete Cycle**. For Cycle Count plans, a dashboard and an **Excess / Shortfall tally** show how results build up across cycles.

### 3. Configuring audit settings

Open an audit and go to **Settings** to review and adjust how it runs before counting starts. Changes save automatically.

| Setting | What it does |
| --- | --- |
| **Auditors and item mapping** | Who counts, and which categories or locations each auditor covers. |
| **Enforce assigned location** | On: auditors see only their assigned locations. Off: everyone can count everywhere; locations outside an auditor's own are highlighted. |
| **Restrict auditors counting same item** | On: once one auditor counts an item at a location, nobody else can count it there. Off: several auditors may count it and their counts are added together. |
| **Allow damaged quantity** | Lets auditors record damaged quantity separately from good stock. |
| **Blind count** | Hides the expected stock quantity from auditors so they count what they see, not what they expect. |
| **Geo-tagging** | Records where each count was made. |
| **Photo validation** | Asks auditors for photos — for a random sample (set the **sample size %**) or for damaged items. |
| **Cross check** | Rechecks counts with a second auditor: **Random Recheck** of a sample, **Discrepancy Recheck** of items with differences, or **Photo validation**. Choose the **Cross Check Auditor**. |
| **Pallet roll-down** (Location audits) | When a pallet is scanned without being opened, treats every case expected on it as present. Off: unscanned cases show as shortages. |
| **Sealed case credit** (Location audits) | When a case is scanned but not opened, credits its expected quantity. Such counts are reported as *assumed*, not verified. |

For Location (Warehouse) audits, cross check, damaged quantity, declaration and location mapping do not apply and are hidden.

### 4. Importing the stock sheet

The stock sheet is the list of expected quantities that counts are compared against. In **Settings**, select **Import stock sheet** and upload the file with item codes and stock quantities (plus location, batch, expiry and serial details where you use them). The sheet then appears in a table showing line items and stock quantity.

If the item group is connected to another business application through the Integration Hub, the stock sheet is fetched from that application instead. The screen shows **Waiting for stock from …** while it arrives, and **Try again** if it could not be read. Do not start counting until the sheet has arrived.

### 5. Counting stock

Auditors open the audit and choose **Stock Audit** (on a phone or handheld, the mobile counting screen opens).

1. **Select the audit location** you are about to count.
2. **Find the item** — type the item code, name or EAN, scan the barcode with a handheld scanner, or use **Scan Barcode** to scan with the device camera. **Continuous Count** keeps the scanner open so you can scan item after item.
3. Check the item details, then enter the **Audited Qty** and, if allowed, the **Damaged Qty**. For batch, expiry or serial-tracked items, fill in those details too.
4. Select **Count** (or **Add Count**) to save. Counting the same item again adds to the earlier count.
5. If the item's recorded location differs from where you found it, Stockount offers to **update the item's location**.
6. When you have counted everything assigned to you, select **Finish Audit** and add any **declaration notes**.

In a **Location (Warehouse) audit**, auditors scan pallets, then the cases on each pallet, then items inside cases where needed. What matters is what the auditor actually observes — a case found on the wrong pallet is reported as misplaced, not matched.

A **Quick Audit** can also be filled by importing counts from Excel.

### 6. Reviewing the audit summary

The **Audit Summary** shows the audit's key figures as counting progresses: audited vs. total lines and quantities, and how many lines are **matched**, **positive variance** (more found than expected) or **negative variance** (less found than expected). Use it to monitor auditors, spot problem areas early and export reports.

### 7. Resolving discrepancies

From the summary, open **Manage Summary** to work through every line with a variance. Select one or more lines and choose an action:

| Action | When to use it |
| --- | --- |
| **Accept** | The count is right and the recorded stock is wrong. The count stands. |
| **Recount** | You are not sure the count is right. Assign the line to an auditor to count again. |
| **Investigate** | The difference needs a closer look. The item is flagged and can be picked up in a later Investigation Audit. |

**Accept All**, **Recount All** and **Investigate All** apply an action to every selected line. Each line shows its stock, audited and variance quantity and value, the auditor, any cross-audit result and declaration note, plus **Recent Audits** of the same item so you can see whether the difference is new or recurring.

Recounts come back to the **Resolution Summary**, where you can accept the recount result or move the item to investigation. The tabs — **All**, **Accepted**, **Recount Accepted**, **Investigation** — show where every line stands. Add a **closure note** to record why.

**Resolution flow at a glance**

```
Variance line ─┬─> Accept ──────────────────────────> Stock adjustment ──> Complete Audit
               │                                            ^
               ├─> Recount ──> Recount Accepted ────────────┘ (count confirmed)
               │      │
               │      └─ still in doubt ─┐
               │                         v
               └─> Investigate ──> Flagged for a later Investigation Audit
```

Accepted and recount-accepted lines feed the stock adjustment, which must be settled before the audit can be completed.

### 8. Adjusting stock

Accepted counts mean the recorded stock is wrong, so it must be corrected before the audit can be completed. How that happens depends on where the stock sheet came from — Stockount decides this automatically:

| Stock sheet came from | How it is settled |
| --- | --- |
| **Stockount's own stock** | Select **Adjust Stocks** to review the adjustment, then an administrator **approves** it and Stockount's stock is updated. |
| **A connected business application** | An administrator approves, and the correction is sent back to that application. A confirmation names the company, site and application it will reach — read it carefully before you confirm. |
| **An uploaded Excel sheet** | Download the **Adjustment Report** and apply the correction in the system the sheet came from. |

The adjustment lines are exactly what the audit found and accepted; they cannot be edited. Only administrators can approve.

### 9. Completing the audit

When every variance has a resolution and any stock adjustment is settled, select **Complete Audit**. If something is still outstanding, the screen tells you what. Audits that stay open past their auto-completion window close automatically. Completed audits move to **Audit History**, and completion summaries are emailed to the people involved.

---

## Key Concepts

| Term | Meaning |
| --- | --- |
| **Audit Plan** | A reusable template for Complete or Cycle Counts: item group, owners, auditors, rules and schedule. Audits are generated from it. |
| **Item Group** | The set of items an audit covers. Each audit belongs to one item group. |
| **Stock sheet** | The expected quantity of each item, imported or fetched before counting. Every count is compared with it. |
| **Stock source** | Where the stock sheet comes from: Stockount's own stock (**Real Time**), an uploaded **Stock Report**, or a connected business application. |
| **Audit Owner / Contributor** | Owners control a plan and its audits; contributors can view everything and help with resolution. |
| **Auditor** | A person assigned to count stock in an audit. |
| **Mapping type** | How counting work is divided between auditors: Random, By Category or By Location. |
| **Audited quantity** | What the auditor physically counted. Repeated counts of the same item add together. |
| **Damaged quantity** | Stock counted but found damaged, recorded separately when allowed. |
| **Variance** | The difference between the audited quantity and the stock-sheet quantity. **Positive** = more found than expected (excess); **negative** = less found (shortage). **Variance value** is that difference in money. |
| **Matched line** | A line where the count equals the expected quantity. |
| **Blind count** | Auditors do not see the expected quantity, which keeps counts independent. |
| **Cross check** | A second auditor rechecks a random sample or the discrepancies to confirm accuracy. |
| **Recount** | A fresh count of a line, assigned during resolution when the first count is in doubt. |
| **Investigation** | A flag on an item whose difference needs looking into; flagged items feed future Investigation Audits. |
| **Resolution** | The decision recorded for each variance line: Accepted, Recount Accepted or Investigation. |
| **Declaration / closure note** | Notes explaining the count (from the auditor) or the decision (from the owner). |
| **Stock adjustment** | The correction of recorded stock that follows accepted counts, settled before the audit can complete. |
| **Auto-completion window** | The number of days after which an open audit closes automatically. |
| **License Plate Number (LPN)** | A pallet or case label used in Location (Warehouse) audits to count stock by container. |
| **Pallet roll-down / Sealed case credit** | Location-audit options that credit unopened pallets or cases with their expected contents. These results are *assumed*, not verified. |

---

## Best Practices

**Before counting**

- **Load the stock sheet first, and check it.** Confirm the line count and total quantity look right before auditors start. A wrong sheet makes every variance wrong.
- **Wait for a connected source.** If the screen says *Waiting for stock from …*, do not start counting until the sheet arrives.
- **Divide the work clearly.** Use By Location or By Category mapping and turn on **Enforce assigned location** so auditors don't miss or double-count areas.
- **Turn on blind count** for audits where accuracy matters most. Auditors who can't see the expected figure count what is really there.
- **Pick the right audit type.** Use Cycle Counts for large inventories, Partial or Suggested Audits for high-risk items and Quick Audits only for spot checks.

**While counting**

- **Count by location, one at a time.** Select the location before you scan, and finish it before moving on.
- **Scan rather than type** wherever a barcode exists, to avoid picking the wrong item.
- **Remember counts add up.** Counting an item again adds to the earlier count — enter only the extra quantity, not a new total.
- **Record damaged stock separately** instead of leaving it out of the count.
- **In Location audits, record what you see.** If a case is on a different pallet from the one on record, scan it where it actually is.
- **Add declaration notes** for anything unusual before you finish.

**After counting**

- **Look for patterns before accepting.** Use **Recent Audits** on each line — a variance that repeats every audit points to a process problem, not a counting slip.
- **Recount large or high-value differences** before accepting them.
- **Write closure notes** so anyone reading the audit later knows why each decision was made.
- **Read the adjustment confirmation in full** before approving a correction to a connected application — it names exactly where the change will go.
- **Complete audits promptly** so results reach Audit History and stock records are corrected while the count is still current.

---

## What's Next?

- **Run your first audit:** open the **Demo Audit** and follow the guided tour, then create a Quick Audit on a small item group.
- **Set up a routine:** create a Cycle Count plan with a weekly or monthly frequency so your inventory is checked continuously rather than once a year.
- **Target your risk:** use **Suggested Audits** to count high-value and frequently mismatched items first.
- **Follow up investigations:** create an Investigation Audit for items flagged in earlier audits.
- **Connect your stock source:** if your stock lives in another business application, ask your administrator about connecting it through the Integration Hub so stock sheets arrive automatically and corrections flow back.
- **Related guides:** the [Inward and Outward Module — User Guide](./inward-outward-user-guide.md) covers receiving and dispatching goods, the movements that change the stock your audits check.

> **Open question:** the practical difference between the **Static** and **Dynamic** counting methods should be confirmed with the product team and added to section 1 of Functionality.
