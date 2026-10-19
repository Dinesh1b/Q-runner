import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';

@Component({
  selector: 'app-m9-auditor2-sa',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="module-form-container">
      <!-- 1. Auditor 2 Credentials -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title amber-accent">
            <span class="card-icon">👥</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Auditor 2 Credentials</div>
              <div style="font-size:12px; color:var(--t3);">Authentication for second auditor</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2 g-last">
            <div class="fld">
              <label class="fld-lbl">Email <span class="req">*</span></label>
              <input
                type="email"
                [value]="configStore.email2()"
                (input)="configStore.email2.set($any($event.target).value)"
                placeholder="auditor2@company.com"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Password <span class="req">*</span></label>
              <input
                type="password"
                [value]="configStore.password2()"
                (input)="configStore.password2.set($any($event.target).value)"
                placeholder="••••••••"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 2. Auditor 2 Add Item -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title amber-accent">
            <span class="card-icon">➕</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Auditor 2 Add Item</div>
              <div style="font-size:12px; color:var(--t3);">Add item before Auditor 2 audit pass</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div
            class="tgl-row"
            style="margin-bottom:14px;"
            (click)="configStore.cbNai2.set(!configStore.cbNai2())"
          >
            <div class="tgl-info">
              <div class="tgl-icon">➕</div>
              <div>
                <div class="tgl-title">Add New Item</div>
                <div class="tgl-sub">run_new_add_item2 — add item before Auditor 2 audit</div>
              </div>
            </div>
            <label class="toggle-switch" (click)="$event.stopPropagation()">
              <input
                type="checkbox"
                [checked]="configStore.cbNai2()"
                (change)="configStore.cbNai2.set(!configStore.cbNai2())"
              />
              <span class="toggle-slider"></span>
            </label>
          </div>

          @if (configStore.cbNai2()) {
            <div class="g g3">
              <div class="fld">
                <label class="fld-lbl">Item Code</label>
                <input
                  type="text"
                  [value]="configStore.asa2ItemCode()"
                  (input)="configStore.asa2ItemCode.set($any($event.target).value)"
                  placeholder="ABC1123"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Item Name</label>
                <input
                  type="text"
                  [value]="configStore.asa2ItemName()"
                  (input)="configStore.asa2ItemName.set($any($event.target).value)"
                  placeholder="Test Item"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Category</label>
                <input
                  type="text"
                  [value]="configStore.asa2Category()"
                  (input)="configStore.asa2Category.set($any($event.target).value)"
                  placeholder="Gear"
                />
              </div>
            </div>

            <div class="g g3" style="margin-top:14px;">
              <div class="fld">
                <label class="fld-lbl">Cost Price</label>
                <input
                  type="text"
                  [value]="configStore.asa2Cp()"
                  (input)="configStore.asa2Cp.set($any($event.target).value)"
                  placeholder="100"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Sell Price</label>
                <input
                  type="text"
                  [value]="configStore.asa2Sp()"
                  (input)="configStore.asa2Sp.set($any($event.target).value)"
                  placeholder="100"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">UOM</label>
                <input
                  type="text"
                  [value]="configStore.asa2Uom()"
                  (input)="configStore.asa2Uom.set($any($event.target).value)"
                  placeholder="PCS"
                />
              </div>
            </div>

            <div class="g g3 g-last" style="margin-top:14px;">
              <div class="fld">
                <label class="fld-lbl">Location</label>
                <input
                  type="text"
                  [value]="configStore.asa2Location()"
                  (input)="configStore.asa2Location.set($any($event.target).value)"
                  placeholder="SA-A1"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Barcode</label>
                <input
                  type="text"
                  [value]="configStore.asa2Barcode()"
                  (input)="configStore.asa2Barcode.set($any($event.target).value)"
                  placeholder="123456789"
                />
              </div>
              <div></div>
            </div>
          }
        </div>
      </div>

      <!-- 3. Audit Count -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title amber-accent">
            <span class="card-icon">🔢</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Audit Count</div>
              <div style="font-size:12px; color:var(--t3);">Audited and damaged quantities for Auditor 2</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2 g-last">
            <div class="fld">
              <label class="fld-lbl">Audited Qty</label>
              <input
                type="number"
                [value]="configStore.asa2AudQty()"
                (input)="configStore.asa2AudQty.set(+$any($event.target).value || 0)"
                placeholder="10"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Damaged Qty</label>
              <input
                type="number"
                [value]="configStore.asa2DamQty()"
                (input)="configStore.asa2DamQty.set(+$any($event.target).value || 0)"
                placeholder="0"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 4. Excel Configuration -->
      <div class="card">
        <div class="card-hd">
          <div class="card-title amber-accent">
            <span class="card-icon">📊</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Excel Configuration — Auditor 2</div>
              <div style="font-size:12px; color:var(--t3);">Sheet name and column headers for Auditor 2</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g3">
            <div class="fld">
              <label class="fld-lbl">Sheet Name</label>
              <input
                type="text"
                [value]="configStore.asa2Sheet()"
                (input)="configStore.asa2Sheet.set($any($event.target).value)"
                placeholder="auditor_2"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Location Column</label>
              <input
                type="text"
                [value]="configStore.asa2LocCol()"
                (input)="configStore.asa2LocCol.set($any($event.target).value)"
                placeholder="locations"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Code Column</label>
              <input
                type="text"
                [value]="configStore.asa2CodeCol()"
                (input)="configStore.asa2CodeCol.set($any($event.target).value)"
                placeholder="code"
              />
            </div>
          </div>

          <div class="g g2 g-last" style="margin-top:14px;">
            <div class="fld">
              <label class="fld-lbl">Audited Column</label>
              <input
                type="text"
                [value]="configStore.asa2AudCol()"
                (input)="configStore.asa2AudCol.set($any($event.target).value)"
                placeholder="audited"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Damaged Column</label>
              <input
                type="text"
                [value]="configStore.asa2DamCol()"
                (input)="configStore.asa2DamCol.set($any($event.target).value)"
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
          (click)="registryStore.selectModuleForEditing(8)"
        >
          ← Auditor 1 SA
        </button>
        <button
          type="button"
          class="btn-primary"
          style="background: linear-gradient(135deg, #f59e0b, #d97706);"
          (click)="registryStore.selectModuleForEditing(10)"
        >
          Table · Summary · Recent →
        </button>
      </div>
    </div>
  `
})
export class M9Auditor2SaComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);
}
