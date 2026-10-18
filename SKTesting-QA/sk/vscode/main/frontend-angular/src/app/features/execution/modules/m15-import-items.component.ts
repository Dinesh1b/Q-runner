import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';
import { ExcelUploaderComponent } from '../components/excel-uploader/excel-uploader.component';

@Component({
  selector: 'app-m15-import-items',
  standalone: true,
  imports: [CommonModule, FormsModule, ExcelUploaderComponent],
  template: `
    <div class="module-form-container">
      <!-- 1. Import Options -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title emerald-accent">
            <span class="card-icon">⚙️</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Import Options</div>
              <div style="font-size:12px; color:var(--t3);">Select item creation and bulk import mechanisms</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g3">
            <div
              class="tgl-row"
              style="margin-bottom:0;"
              (click)="configStore.cbRunAddItem.set(!configStore.cbRunAddItem())"
            >
              <div class="tgl-info">
                <div class="tgl-icon">➕</div>
                <div>
                  <div class="tgl-title">Add Item</div>
                  <div class="tgl-sub">Single item entry</div>
                </div>
              </div>
              <label class="toggle-switch" (click)="$event.stopPropagation()">
                <input
                  type="checkbox"
                  [checked]="configStore.cbRunAddItem()"
                  (change)="configStore.cbRunAddItem.set(!configStore.cbRunAddItem())"
                />
                <span class="toggle-slider"></span>
              </label>
            </div>

            <div
              class="tgl-row"
              style="margin-bottom:0;"
              (click)="configStore.cbQuickAdd.set(!configStore.cbQuickAdd())"
            >
              <div class="tgl-info">
                <div class="tgl-icon">⚡</div>
                <div>
                  <div class="tgl-title">Quick Add</div>
                  <div class="tgl-sub">Multiple items</div>
                </div>
              </div>
              <label class="toggle-switch" (click)="$event.stopPropagation()">
                <input
                  type="checkbox"
                  [checked]="configStore.cbQuickAdd()"
                  (change)="configStore.cbQuickAdd.set(!configStore.cbQuickAdd())"
                />
                <span class="toggle-slider"></span>
              </label>
            </div>

            <div
              class="tgl-row"
              style="margin-bottom:0;"
              (click)="configStore.cbImportExcel.set(!configStore.cbImportExcel())"
            >
              <div class="tgl-info">
                <div class="tgl-icon">📊</div>
                <div>
                  <div class="tgl-title">Excel Import</div>
                  <div class="tgl-sub">Bulk from file</div>
                </div>
              </div>
              <label class="toggle-switch" (click)="$event.stopPropagation()">
                <input
                  type="checkbox"
                  [checked]="configStore.cbImportExcel()"
                  (change)="configStore.cbImportExcel.set(!configStore.cbImportExcel())"
                />
                <span class="toggle-slider"></span>
              </label>
            </div>
          </div>
        </div>
      </div>

      <!-- 2. Item Details -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title emerald-accent">
            <span class="card-icon">📦</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Item Details</div>
              <div style="font-size:12px; color:var(--t3);">Single item specifications</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g3">
            <div class="fld">
              <label class="fld-lbl">Item Name</label>
              <input
                type="text"
                [value]="configStore.iiItemName()"
                (input)="configStore.iiItemName.set($any($event.target).value)"
                placeholder="Product Name"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Item Code</label>
              <input
                type="text"
                [value]="configStore.iiItemCode()"
                (input)="configStore.iiItemCode.set($any($event.target).value)"
                placeholder="PROD-001"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">UOM</label>
              <input
                type="text"
                [value]="configStore.iiItemUom()"
                (input)="configStore.iiItemUom.set($any($event.target).value)"
                placeholder="PCS"
              />
            </div>
          </div>

          <div class="g g3" style="margin-top:14px;">
            <div class="fld">
              <label class="fld-lbl">Category</label>
              <input
                type="text"
                [value]="configStore.iiCategory()"
                (input)="configStore.iiCategory.set($any($event.target).value)"
                placeholder="Category"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Tag</label>
              <input
                type="text"
                [value]="configStore.iiTag()"
                (input)="configStore.iiTag.set($any($event.target).value)"
                placeholder="Tag"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Barcode</label>
              <input
                type="text"
                [value]="configStore.iiBarcode()"
                (input)="configStore.iiBarcode.set($any($event.target).value)"
                placeholder="123456789"
              />
            </div>
          </div>

          <div class="g g2" style="margin-top:14px;">
            <div class="fld">
              <label class="fld-lbl">Cost Price</label>
              <input
                type="number"
                [value]="configStore.iiCp()"
                (input)="configStore.iiCp.set(+$any($event.target).value || 0)"
                placeholder="0"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Sell Price</label>
              <input
                type="number"
                [value]="configStore.iiSp()"
                (input)="configStore.iiSp.set(+$any($event.target).value || 0)"
                placeholder="0"
              />
            </div>
          </div>

          <div class="g g2" style="margin-top:14px;">
            <div class="fld">
              <label class="fld-lbl">Description <span class="muted">(optional)</span></label>
              <input
                type="text"
                [value]="configStore.iiDescription()"
                (input)="configStore.iiDescription.set($any($event.target).value)"
                placeholder="Item notes..."
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Tax HSN <span class="muted">(optional)</span></label>
              <input
                type="text"
                [value]="configStore.iiTaxHsn()"
                (input)="configStore.iiTaxHsn.set($any($event.target).value)"
                placeholder="HSN code"
              />
            </div>
          </div>

          <div class="g g2 g-last" style="margin-top:14px;">
            <div class="fld">
              <label class="fld-lbl">Tax <span class="muted">(optional)</span></label>
              <input
                type="text"
                [value]="configStore.iiTax()"
                (input)="configStore.iiTax.set($any($event.target).value)"
                placeholder="GST 18%"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Reorder Limit <span class="muted">(optional)</span></label>
              <input
                type="text"
                [value]="configStore.iiReorderLimit()"
                (input)="configStore.iiReorderLimit.set($any($event.target).value)"
                placeholder="10"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 3. Excel Import -->
      <app-excel-uploader
        label="Drag & Drop 'Item_Unit.xlsx'"
        storageKey="IMPORT_EXCEL"
        sampleUrl="/sample_excel_item_import"
        sampleFilename="item_import.xlsx"
        sheetLabel="Item Import Sheet Name"
        sheetHint="Excel sheet containing item records"
        [selectedSheet]="configStore.iiSheetName()"
        (sheetChange)="configStore.iiSheetName.set($event)"
      />

      <!-- Navigation Row -->
      <div class="nav-row">
        <button
          type="button"
          class="btn btn-ghost"
          (click)="registryStore.selectModuleForEditing(14)"
        >
          ← Location Setup
        </button>
        <button
          type="button"
          class="btn-primary"
          (click)="goToRunTab()"
        >
          Go to Run →
        </button>
      </div>
    </div>
  `
})
export class M15ImportItemsComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);

  goToRunTab(): void {
    // Dispatch custom event or let shell handle it
    const event = new CustomEvent('navigate-tab', { detail: 'run', bubbles: true });
    window.dispatchEvent(event);
  }
}
