import { Component, WritableSignal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';

interface ReportSection {
  idx: number;
  icon: string;
  title: string;
  hint: string;
  label: string;
  placeholder: string;
  fieldHint: string;
  sheet: WritableSignal<string>;
}

/**
 * Table · Summary · Recent (modules 10, 11, 12) on one page.
 * Each section keeps its own Enable switch — they still run as separate modules.
 */
@Component({
  selector: 'app-m10-a-as-table',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="module-form-container">
      @let groupOn = registryStore.groupEnabled()[1];
      @for (s of sections; track s.idx) {
        <!-- Enable switch (same markup as the module banner) -->
        <div class="tgl-row" [class.disabled]="!groupOn" [id]="'tgl-mod-' + s.idx" (click)="registryStore.toggleModule(s.idx)">
          <div class="tgl-info">
            <div class="tgl-icon">{{ s.icon }}</div>
            <div>
              <div class="tgl-title">Enable {{ s.title }}</div>
              @if (groupOn) {
                <div class="tgl-sub">{{ getWorkflow(s.idx) }}</div>
              } @else {
                <div class="tgl-sub">Turn on the {{ getGroupName() }} group in the sidebar to enable this module</div>
              }
            </div>
          </div>
          <label class="sw" (click)="$event.stopPropagation()">
            <input
              type="checkbox"
              [id]="'cb-mod-' + s.idx"
              [disabled]="!groupOn"
              [checked]="registryStore.moduleEnabled()[s.idx]"
              (change)="registryStore.toggleModule(s.idx)"
            />
            <span class="sw-track"></span>
          </label>
        </div>

        <div class="card">
          <div class="card-hd">
            <div class="card-title amber-accent">
              <span class="card-icon">{{ s.icon }}</span>
              <div>
                <div style="font-weight:700; font-size:15px; color:var(--t0);">Sheet Configuration — {{ s.title }}</div>
                <div style="font-size:12px; color:var(--t3);">{{ s.hint }}</div>
              </div>
            </div>
          </div>

          <div class="card-body">
            <div class="g g2 g-last">
              <div class="fld">
                <label class="fld-lbl">{{ s.label }}</label>
                <input
                  type="text"
                  [value]="s.sheet()"
                  (input)="s.sheet.set($any($event.target).value)"
                  [placeholder]="s.placeholder"
                />
              </div>
            </div>
            <div class="fld-hint" style="margin-top:8px;">{{ s.fieldHint }}</div>
          </div>
        </div>
      }

      <!-- Navigation Row -->
      <div class="nav-row">
        <button
          type="button"
          class="btn btn-ghost"
          (click)="registryStore.selectModuleForEditing(9)"
        >
          ← Auditor 2 SA
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
export class M10AAsTableComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);

  readonly sections: ReportSection[] = [
    {
      idx: 10, icon: '📉', title: 'Table',
      hint: 'A_as_table verification settings',
      label: 'Sheet Name', placeholder: 'as_table',
      fieldHint: 'Reads EXCEL_SHEET_as_table — also used by Q Audit Summary Table',
      sheet: this.configStore.excelSheetAsTable,
    },
    {
      idx: 11, icon: '📊', title: 'Summary',
      hint: 'A_audit_Summary verification settings',
      label: 'Summary Sheet Name', placeholder: 'auditSummary',
      fieldHint: 'Reads EXCEL_SHEET_audit_Summary — also configured in Q_audit_Summary (Module 5)',
      sheet: this.configStore.excelSheetAuditSummary,
    },
    {
      idx: 12, icon: '🕐', title: 'Recent',
      hint: 'A_Recently_Audit verification settings',
      label: 'Sheet Name', placeholder: 'Recently_Audit',
      fieldHint: 'Reads EXCEL_SHEET_Recently_Audit — also used by Q Audit Recently Audited (Module 4)',
      sheet: this.configStore.excelSheetRecentlyAudit,
    },
  ];

  getWorkflow(idx: number): string {
    return this.registryStore.modules().find(m => m.idx === idx)?.workflow ?? '';
  }

  getGroupName(): string {
    return this.registryStore.groups().find(g => g.idx === 1)?.name ?? 'Audit Plan';
  }
}
