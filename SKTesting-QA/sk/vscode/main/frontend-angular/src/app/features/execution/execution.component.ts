import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ModuleRegistryStore } from '../../state/module-registry.store';
import { M0QSettingComponent } from './modules/m0-q-setting.component';
import { M1StockAuditA1Component } from './modules/m1-stock-audit-a1.component';
import { M2StockAuditA2Component } from './modules/m2-stock-audit-a2.component';
import { M3SummaryTableComponent } from './modules/m3-summary-table.component';
import { M4RecentlyAuditedComponent } from './modules/m4-recently-audited.component';
import { M5QAuditSummaryComponent } from './modules/m5-q-audit-summary.component';
import { M6AuditPlanComponent } from './modules/m6-audit-plan.component';
import { M7OngoingAuditComponent } from './modules/m7-ongoing-audit.component';
import { M8Auditor1SaComponent } from './modules/m8-auditor1-sa.component';
import { M9Auditor2SaComponent } from './modules/m9-auditor2-sa.component';
import { M10AAsTableComponent } from './modules/m10-a-as-table.component';
import { M11AAuditSummaryComponent } from './modules/m11-a-audit-summary.component';
import { M12ARecentlyAuditComponent } from './modules/m12-a-recently-audit.component';
import { M13CreateGroupComponent } from './modules/m13-create-group.component';
import { M14LocationSetupComponent } from './modules/m14-location-setup.component';
import { M15ImportItemsComponent } from './modules/m15-import-items.component';

@Component({
  selector: 'app-execution',
  standalone: true,
  imports: [
    CommonModule,
    M0QSettingComponent,
    M1StockAuditA1Component,
    M2StockAuditA2Component,
    M3SummaryTableComponent,
    M4RecentlyAuditedComponent,
    M5QAuditSummaryComponent,
    M6AuditPlanComponent,
    M7OngoingAuditComponent,
    M8Auditor1SaComponent,
    M9Auditor2SaComponent,
    M10AAsTableComponent,
    M11AAuditSummaryComponent,
    M12ARecentlyAuditComponent,
    M13CreateGroupComponent,
    M14LocationSetupComponent,
    M15ImportItemsComponent,
  ],
  template: `
    <div id="content-execution" style="display:flex; flex-direction:column; flex:1; overflow:hidden;">
      <div class="content" id="exec-content-scroll" style="flex:1; overflow-y:auto; padding:28px 36px;">
        @if (registryStore.selectedModuleIdx() === null) {
          <!-- Empty State (matching index.html exec-empty-state) -->
          <div id="exec-empty-state" class="exec-empty">
            <div class="exec-empty-ring"><span class="exec-empty-icon">🗂️</span></div>
            <div class="exec-empty-title">No Module Selected</div>
            <div class="exec-empty-body">Select a module from the <strong>left panel</strong> to configure it.</div>
            <div class="exec-empty-hints">
              <div class="exec-empty-hint-row" (click)="registryStore.selectModuleForEditing(0)">
                <span class="exec-empty-hint-icon">⚙️</span>
                <span class="exec-empty-hint-name">Q_Setting</span>
                <span class="exec-empty-hint-sub">Config</span>
              </div>
              <div class="exec-empty-hint-row" (click)="registryStore.selectModuleForEditing(1)">
                <span class="exec-empty-hint-icon">📦</span>
                <span class="exec-empty-hint-name">Stock Audit A1</span>
                <span class="exec-empty-hint-sub">Excel · Mapping</span>
              </div>
              <div class="exec-empty-hint-row" (click)="registryStore.selectModuleForEditing(2)">
                <span class="exec-empty-hint-icon">👥</span>
                <span class="exec-empty-hint-name">Stock Audit A2</span>
                <span class="exec-empty-hint-sub">Credentials</span>
              </div>
              <div class="exec-empty-hint-row" (click)="registryStore.selectModuleForEditing(3)">
                <span class="exec-empty-hint-icon">📊</span>
                <span class="exec-empty-hint-name">Summary Table</span>
                <span class="exec-empty-hint-sub">Sheet config</span>
              </div>
              <div class="exec-empty-hint-row" (click)="registryStore.selectModuleForEditing(4)">
                <span class="exec-empty-hint-icon">🕐</span>
                <span class="exec-empty-hint-name">Recently Audited</span>
                <span class="exec-empty-hint-sub">Sheet config</span>
              </div>
              <div class="exec-empty-hint-row" (click)="registryStore.selectModuleForEditing(6)">
                <span class="exec-empty-hint-icon">📋</span>
                <span class="exec-empty-hint-name">Audit Plan</span>
                <span class="exec-empty-hint-sub">Schedule · Cross</span>
              </div>
              <div class="exec-empty-hint-row" (click)="registryStore.selectModuleForEditing(13)">
                <span class="exec-empty-hint-icon">🗃️</span>
                <span class="exec-empty-hint-name">Create Group</span>
                <span class="exec-empty-hint-sub">Inventory · Fields</span>
              </div>
            </div>
          </div>
        } @else {
          @let mod = getSelectedModule();
          @if (mod) {
            <div class="page active" [id]="'ep' + mod.idx" style="display:block;">
              <!-- Module Enable Banner (matching tgl-row) -->
              <div class="tgl-row" [id]="'tgl-mod-' + mod.idx" (click)="registryStore.toggleModule(mod.idx)">
                <div class="tgl-info">
                  <div class="tgl-icon">{{ mod.icon }}</div>
                  <div>
                    <div class="tgl-title">Enable {{ mod.display }}</div>
                    <div class="tgl-sub">{{ mod.workflow || (mod.name + '() — execute module workflow') }}</div>
                  </div>
                </div>
                <label class="sw" (click)="$event.stopPropagation()">
                  <input
                    type="checkbox"
                    [id]="'cb-mod-' + mod.idx"
                    [checked]="registryStore.moduleEnabled()[mod.idx]"
                    (change)="registryStore.toggleModule(mod.idx)"
                  />
                  <span class="sw-track"></span>
                </label>
              </div>

              <!-- Module Sub-component Form -->
              @switch (mod.idx) {
                @case (0) { <app-m0-q-setting /> }
                @case (1) { <app-m1-stock-audit-a1 /> }
                @case (2) { <app-m2-stock-audit-a2 /> }
                @case (3) { <app-m3-summary-table /> }
                @case (4) { <app-m4-recently-audited /> }
                @case (5) { <app-m5-q-audit-summary /> }
                @case (6) { <app-m6-audit-plan /> }
                @case (7) { <app-m7-ongoing-audit /> }
                @case (8) { <app-m8-auditor1-sa /> }
                @case (9) { <app-m9-auditor2-sa /> }
                @case (10) { <app-m10-a-as-table /> }
                @case (11) { <app-m11-a-audit-summary /> }
                @case (12) { <app-m12-a-recently-audit /> }
                @case (13) { <app-m13-create-group /> }
                @case (14) { <app-m14-location-setup /> }
                @case (15) { <app-m15-import-items /> }
              }

              <!-- Bottom Module Navigation Row -->
              <div class="nav-row" style="margin-top:20px; margin-bottom:40px;">
                @if (mod.idx > 0) {
                  <button type="button" class="btn btn-back" (click)="registryStore.selectModuleForEditing(mod.idx - 1)">
                    {{ getPrevModuleName(mod.idx) }}
                  </button>
                } @else {
                  <button type="button" class="btn btn-back" (click)="goToSetup()">
                    Setup
                  </button>
                }

                @if (mod.idx < 15) {
                  <button type="button" class="btn btn-accent btn-lg" (click)="registryStore.selectModuleForEditing(mod.idx + 1)">
                    {{ getNextModuleName(mod.idx) }} →
                  </button>
                } @else {
                  <button type="button" class="btn btn-accent btn-lg" (click)="goToRun()">
                    Go to Run →
                  </button>
                }
              </div>
            </div>
          }
        }
      </div>
    </div>
  `
})
export class ExecutionComponent {
  readonly registryStore = inject(ModuleRegistryStore);

  getSelectedModule() {
    const idx = this.registryStore.selectedModuleIdx();
    if (idx === null) return null;
    return this.registryStore.modules().find(m => m.idx === idx) ?? null;
  }

  getPrevModuleName(currentIdx: number): string {
    const prev = this.registryStore.modules().find(m => m.idx === currentIdx - 1);
    return prev ? prev.display : 'Previous';
  }

  getNextModuleName(currentIdx: number): string {
    const next = this.registryStore.modules().find(m => m.idx === currentIdx + 1);
    return next ? next.display : 'Next';
  }

  goToSetup(): void {
    window.dispatchEvent(new CustomEvent('navigate-tab', { detail: 'setup' }));
  }

  goToRun(): void {
    window.dispatchEvent(new CustomEvent('navigate-tab', { detail: 'run' }));
  }
}
