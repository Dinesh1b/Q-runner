import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';

@Component({
  selector: 'app-m4-recently-audited',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="module-form-container">
      <div class="card">
        <div class="card-hd">
          <div class="card-title">
            <span class="card-icon">🕐</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Sheet Configuration</div>
              <div style="font-size:12px; color:var(--t3);">Q_Recently_Audit verification settings</div>
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
        </div>
      </div>

      <!-- Navigation Row -->
      <div class="nav-row">
        <button
          type="button"
          class="btn btn-ghost"
          (click)="registryStore.selectModuleForEditing(3)"
        >
          ← Summary Table
        </button>
        <button
          type="button"
          class="btn-primary"
          (click)="registryStore.selectModuleForEditing(5)"
        >
          Q_audit_Summary →
        </button>
      </div>
    </div>
  `
})
export class M4RecentlyAuditedComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);
}
