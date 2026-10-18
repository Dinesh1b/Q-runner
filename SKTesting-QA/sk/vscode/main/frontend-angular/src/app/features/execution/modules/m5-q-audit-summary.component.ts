import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';

@Component({
  selector: 'app-m5-q-audit-summary',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="module-form-container">
      <div class="card">
        <div class="card-hd">
          <div class="card-title">
            <span class="card-icon">📋</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Summary Configuration</div>
              <div style="font-size:12px; color:var(--t3);">Filter and summarized audit results in Excel</div>
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

            <div class="fld">
              <label class="fld-lbl">Filter Column</label>
              <input
                type="text"
                [value]="configStore.filterColumn()"
                (input)="configStore.filterColumn.set($any($event.target).value)"
                placeholder="filter"
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
          (click)="registryStore.selectModuleForEditing(4)"
        >
          ← Recently Audited
        </button>
        <button
          type="button"
          class="btn-primary"
          style="background: linear-gradient(135deg, #a855f7, #8b5cf6, #7c3aed);"
          (click)="registryStore.selectModuleForEditing(6)"
        >
          Audit Plan →
        </button>
      </div>
    </div>
  `
})
export class M5QAuditSummaryComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);
}
