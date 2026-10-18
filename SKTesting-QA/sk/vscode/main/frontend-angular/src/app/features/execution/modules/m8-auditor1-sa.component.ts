import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';

@Component({
  selector: 'app-m8-auditor1-sa',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="module-form-container">
      <!-- 1. Auditor 1 Add Item -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title amber-accent">
            <span class="card-icon">➕</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Auditor 1 Add Item</div>
              <div style="font-size:12px; color:var(--t3);">Add new item before audit pass</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div
            class="tgl-row"
            style="margin-bottom:14px;"
            (click)="configStore.cbRunNewAddItem.set(!configStore.cbRunNewAddItem())"
          >
            <div class="tgl-info">
              <div class="tgl-icon">➕</div>
              <div>
                <div class="tgl-title">Add New Item</div>
                <div class="tgl-sub">run_new_add_item — add item before audit</div>
              </div>
            </div>
            <label class="toggle-switch" (click)="$event.stopPropagation()">
              <input
                type="checkbox"
                [checked]="configStore.cbRunNewAddItem()"
                (change)="configStore.cbRunNewAddItem.set(!configStore.cbRunNewAddItem())"
              />
              <span class="toggle-slider"></span>
            </label>
          </div>

          @if (configStore.cbRunNewAddItem()) {
            <div class="g g3">
              <div class="fld">
                <label class="fld-lbl">Item Code</label>
                <input
                  type="text"
                  [value]="configStore.asaItemCode()"
                  (input)="configStore.asaItemCode.set($any($event.target).value)"
                  placeholder="ABC1123"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Item Name</label>
                <input
                  type="text"
                  [value]="configStore.asaItemName()"
                  (input)="configStore.asaItemName.set($any($event.target).value)"
                  placeholder="Test Item"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Category</label>
                <input
                  type="text"
                  [value]="configStore.asaCategory()"
                  (input)="configStore.asaCategory.set($any($event.target).value)"
                  placeholder="Gear"
                />
              </div>
            </div>

            <div class="g g3" style="margin-top:14px;">
              <div class="fld">
                <label class="fld-lbl">Cost Price</label>
                <input
                  type="text"
                  [value]="configStore.asaCp()"
                  (input)="configStore.asaCp.set($any($event.target).value)"
                  placeholder="100"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Sell Price</label>
                <input
                  type="text"
                  [value]="configStore.asaSp()"
                  (input)="configStore.asaSp.set($any($event.target).value)"
                  placeholder="100"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">UOM</label>
                <input
                  type="text"
                  [value]="configStore.asaUom()"
                  (input)="configStore.asaUom.set($any($event.target).value)"
                  placeholder="PCS"
                />
              </div>
            </div>

            <div class="g g3 g-last" style="margin-top:14px;">
              <div class="fld">
                <label class="fld-lbl">Location</label>
                <input
                  type="text"
                  [value]="configStore.asaLocation()"
                  (input)="configStore.asaLocation.set($any($event.target).value)"
                  placeholder="SA-A1"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Barcode</label>
                <input
                  type="text"
                  [value]="configStore.asaBarcode()"
                  (input)="configStore.asaBarcode.set($any($event.target).value)"
                  placeholder="123456789"
                />
              </div>
              <div></div>
            </div>
          }
        </div>
      </div>

      <!-- 2. Audit Count -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title amber-accent">
            <span class="card-icon">🔢</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Audit Count</div>
              <div style="font-size:12px; color:var(--t3);">Audited and damaged quantities</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2 g-last">
            <div class="fld">
              <label class="fld-lbl">Audited Qty</label>
              <input
                type="number"
                [value]="configStore.asaAudQty()"
                (input)="configStore.asaAudQty.set(+$any($event.target).value || 0)"
                placeholder="10"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Damaged Qty</label>
              <input
                type="number"
                [value]="configStore.asaDamQty()"
                (input)="configStore.asaDamQty.set(+$any($event.target).value || 0)"
                placeholder="0"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 3. Excel Configuration -->
      <div class="card">
        <div class="card-hd">
          <div class="card-title amber-accent">
            <span class="card-icon">📊</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Excel Configuration</div>
              <div style="font-size:12px; color:var(--t3);">Sheet name and column headers for Auditor 1</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g3">
            <div class="fld">
              <label class="fld-lbl">Sheet Name</label>
              <input
                type="text"
                [value]="configStore.asaSheet()"
                (input)="configStore.asaSheet.set($any($event.target).value)"
                placeholder="auditor_1"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Location Column</label>
              <input
                type="text"
                [value]="configStore.asaLocCol()"
                (input)="configStore.asaLocCol.set($any($event.target).value)"
                placeholder="locations"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Code Column</label>
              <input
                type="text"
                [value]="configStore.asaCodeCol()"
                (input)="configStore.asaCodeCol.set($any($event.target).value)"
                placeholder="code"
              />
            </div>
          </div>

          <div class="g g2 g-last" style="margin-top:14px;">
            <div class="fld">
              <label class="fld-lbl">Audited Column</label>
              <input
                type="text"
                [value]="configStore.asaAudCol()"
                (input)="configStore.asaAudCol.set($any($event.target).value)"
                placeholder="audited"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Damaged Column</label>
              <input
                type="text"
                [value]="configStore.asaDamCol()"
                (input)="configStore.asaDamCol.set($any($event.target).value)"
                placeholder="damaged"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Navigation Row -->
      <div class="nav-row">
        <button
          type="button"
          class="btn btn-ghost"
          (click)="registryStore.selectModuleForEditing(7)"
        >
          ← Ongoing Audit
        </button>
        <button
          type="button"
          class="btn-primary"
          style="background: linear-gradient(135deg, #f59e0b, #d97706);"
          (click)="registryStore.selectModuleForEditing(9)"
        >
          Auditor 2 SA →
        </button>
      </div>
    </div>
  `
})
export class M8Auditor1SaComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);
}
