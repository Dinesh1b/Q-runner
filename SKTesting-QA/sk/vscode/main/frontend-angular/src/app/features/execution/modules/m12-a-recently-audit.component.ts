import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';

@Component({
  selector: 'app-m12-a-recently-audit',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="module-form-container">
      <div class="card">
        <div class="card-hd">
          <div class="card-title amber-accent">
            <span class="card-icon">🕐</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Sheet Configuration — Auditor 2 Recent</div>
              <div style="font-size:12px; color:var(--t3);">A_Recently_Audit verification settings</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2 g-last">
            <div class="fld">
              <label class="fld-lbl">Sheet Name</label>
              <input
                type="text"
                [value]="configStore.excelSheetRecentlyAudit()"
                (input)="configStore.excelSheetRecentlyAudit.set($any($event.target).value)"
                placeholder="Recently_Audit"
              />
            </div>
          </div>
          <div class="fld-hint" style="margin-top:8px;">Reads EXCEL_SHEET_Recently_Audit — also used by Q Audit Recently Audited (Module 4)</div>
        </div>
      </div>

      <!-- Navigation Row -->
      <div class="nav-row">
        <button
          type="button"
          class="btn btn-ghost"
          (click)="registryStore.selectModuleForEditing(11)"
        >
          ← A_audit_Summary
        </button>
        <button
          type="button"
          class="btn-primary"
          style="background: linear-gradient(135deg, #10b981, #059669);"
          (click)="registryStore.selectModuleForEditing(13)"
        >
          Create Group →
        </button>
      </div>
    </div>
  `
})
export class M12ARecentlyAuditComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);
}
