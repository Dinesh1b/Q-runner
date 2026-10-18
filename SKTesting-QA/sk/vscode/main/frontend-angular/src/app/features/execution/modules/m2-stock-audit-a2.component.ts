import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';

@Component({
  selector: 'app-m2-stock-audit-a2',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="module-form-container">
      <!-- 1. Auditor 2 Credentials -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title">
            <span class="card-icon">👥</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Auditor 2 Credentials</div>
              <div style="font-size:12px; color:var(--t3);">Authentication for second auditor session</div>
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

      <!-- 2. Manual Entry — Auditor 2 -->
      <div class="card">
        <div class="card-hd">
          <div class="card-title">
            <span class="card-icon">📦</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Manual Entry — Auditor 2</div>
              <div style="font-size:12px; color:var(--t3);">Single item audit parameters for Auditor 2</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2">
            <div class="fld">
              <label class="fld-lbl">Location (&#64; separated)</label>
              <input
                type="text"
                [value]="configStore.location2()"
                (input)="configStore.location2.set($any($event.target).value)"
                placeholder="SA-A1&#64;SA-A2"
              />
            </div>

            <div class="fld">
              <label class="fld-lbl">Item Code 2</label>
              <input
                type="text"
                [value]="configStore.code2()"
                (input)="configStore.code2.set($any($event.target).value)"
                placeholder="ABC1123"
              />
            </div>
          </div>

          <div class="g g2 g-last" style="margin-top:14px;">
            <div class="fld">
              <label class="fld-lbl">Audited Qty</label>
              <input
                type="number"
                [value]="configStore.audQty2()"
                (input)="configStore.audQty2.set(+$any($event.target).value || 0)"
                placeholder="0"
              />
            </div>

            <div class="fld">
              <label class="fld-lbl">Damaged Qty</label>
              <input
                type="number"
                [value]="configStore.damQty2()"
                (input)="configStore.damQty2.set(+$any($event.target).value || 0)"
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
          (click)="registryStore.selectModuleForEditing(1)"
        >
          ← Auditor 1
        </button>
        <button
          type="button"
          class="btn-primary"
          (click)="registryStore.selectModuleForEditing(3)"
        >
          Summary Table →
        </button>
      </div>
    </div>
  `
})
export class M2StockAuditA2Component {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);
}
