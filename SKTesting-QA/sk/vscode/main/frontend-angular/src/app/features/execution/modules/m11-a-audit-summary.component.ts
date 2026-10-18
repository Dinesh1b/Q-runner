import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';

@Component({
  selector: 'app-m11-a-audit-summary',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="module-form-container">
      <div class="card">
        <div class="card-hd">
          <div class="card-title amber-accent">
            <span class="card-icon">📊</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Summary Configuration — Auditor 2</div>
              <div style="font-size:12px; color:var(--t3);">A_audit_Summary verification settings</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2 g-last">
            <div class="fld">
              <label class="fld-lbl">Summary Sheet Name</label>
              <input
                type="text"
                [value]="configStore.excelSheetAuditSummary()"
                (input)="configStore.excelSheetAuditSummary.set($any($event.target).value)"
                placeholder="auditSummary"
              />
            </div>
          </div>
          <div class="fld-hint" style="margin-top:8px;">Reads EXCEL_SHEET_audit_Summary — also configured in Q_audit_Summary (Module 5)</div>
        </div>
      </div>

      <!-- Navigation Row -->
      <div class="nav-row">
        <button
          type="button"
          class="btn btn-ghost"
          (click)="registryStore.selectModuleForEditing(10)"
        >
          ← A_as_table
        </button>
        <button
          type="button"
          class="btn-primary"
          style="background: linear-gradient(135deg, #f59e0b, #d97706);"
          (click)="registryStore.selectModuleForEditing(12)"
        >
          A_Recently_Audit →
        </button>
      </div>
    </div>
  `
})
export class M11AAuditSummaryComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);
}
