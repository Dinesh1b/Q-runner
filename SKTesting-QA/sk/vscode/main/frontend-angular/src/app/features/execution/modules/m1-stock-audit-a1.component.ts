import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';

@Component({
  selector: 'app-m1-stock-audit-a1',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="module-form-container">
      <div class="card">
        <div class="card-hd">
          <div class="card-title">
            <span class="card-icon">📦</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Manual Entry — Auditor 1</div>
              <div style="font-size:12px; color:var(--t3);">Single item audit parameters for primary auditor</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2">
            <div class="fld">
              <label class="fld-lbl">Location (&#64; separated)</label>
              <input
                type="text"
                [value]="configStore.location1()"
                (input)="configStore.location1.set($any($event.target).value)"
                placeholder="SA-A1&#64;SA-A2"
              />
              <div class="fld-hint">Use &#64; to separate multiple locations</div>
            </div>

            <div class="fld">
              <label class="fld-lbl">Item Code</label>
              <input
                type="text"
                [value]="configStore.code1()"
                (input)="configStore.code1.set($any($event.target).value)"
                placeholder="ABC1123"
              />
            </div>
          </div>

          <div class="g g2 g-last" style="margin-top:14px;">
            <div class="fld">
              <label class="fld-lbl">Audited Qty</label>
              <input
                type="number"
                [value]="configStore.audQty1()"
                (input)="configStore.audQty1.set(+$any($event.target).value || 0)"
                placeholder="0"
              />
            </div>

            <div class="fld">
              <label class="fld-lbl">Damaged Qty</label>
              <input
                type="number"
                [value]="configStore.damQty1()"
                (input)="configStore.damQty1.set(+$any($event.target).value || 0)"
                placeholder="0"
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
          (click)="registryStore.selectModuleForEditing(0)"
        >
          ← Q_Setting
        </button>
        <button
          type="button"
          class="btn-primary"
          (click)="registryStore.selectModuleForEditing(2)"
        >
          Stock Audit A2 →
        </button>
      </div>
    </div>
  `
})
export class M1StockAuditA1Component {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);
}
