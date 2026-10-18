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
    <div style="flex:1; overflow-y:auto; padding:28px 36px; height:100%;">
      @if (registryStore.selectedModuleIdx() === null) {
        <!-- Empty state -->
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:70vh; gap:16px;">
          <div style="font-size:64px; opacity:0.3;">📦</div>
          <div style="font-size:18px; font-weight:700; color:var(--t2);">Select an Execution Module</div>
          <div style="font-size:13px; color:var(--t3); max-width:440px; text-align:center; line-height:1.6;">
            Choose a module from the sidebar accordion to configure its parameters and datasets.
            You can enable entire groups or individual modules.
          </div>

          <!-- Quick Jump Cards -->
          <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:14px; margin-top:20px; max-width:680px; width:100%;">
            <div
              class="card"
              style="cursor:pointer; padding:18px; text-align:center; transition:var(--trans);"
              (click)="registryStore.selectModuleForEditing(0)"
            >
              <div style="font-size:26px; margin-bottom:8px;">⚙️</div>
              <div style="font-weight:700; font-size:13.5px; color:var(--t0);">Q_Setting</div>
              <div style="font-size:11px; color:var(--t3); margin-top:4px;">Group 0 · Q Audit</div>
            </div>

            <div
              class="card"
              style="cursor:pointer; padding:18px; text-align:center; transition:var(--trans);"
              (click)="registryStore.selectModuleForEditing(6)"
            >
              <div style="font-size:26px; margin-bottom:8px;">📅</div>
              <div style="font-weight:700; font-size:13.5px; color:var(--t0);">Audit Plan</div>
              <div style="font-size:11px; color:var(--t3); margin-top:4px;">Group 1 · Audit Plan</div>
            </div>

            <div
              class="card"
              style="cursor:pointer; padding:18px; text-align:center; transition:var(--trans);"
              (click)="registryStore.selectModuleForEditing(13)"
            >
              <div style="font-size:26px; margin-bottom:8px;">📁</div>
              <div style="font-weight:700; font-size:13.5px; color:var(--t0);">Create Group</div>
              <div style="font-size:11px; color:var(--t3); margin-top:4px;">Group 2 · Inventory</div>
            </div>
          </div>
        </div>
      } @else {
        <!-- Selected Module Active Header & Forms -->
        @let mod = getSelectedModule();
        @if (mod) {
          <div style="max-width:980px; margin:0 auto; padding-bottom:60px;">
            <!-- Breadcrumb Header -->
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px;">
              <div>
                <div style="font-family:var(--font-mono); font-size:10px; color:var(--accent); letter-spacing:.14em; text-transform:uppercase;">
                  Module {{ mod.idx }} · {{ mod.session === 'auditor2' ? 'Auditor 2 Session' : 'Auditor 1 Session' }} · Group {{ mod.group }}
                </div>
                <h1 style="font-size:24px; font-weight:800; color:var(--t0); margin-top:3px;">
                  {{ mod.icon }} {{ mod.display }}
                </h1>
              </div>

              <!-- Module Quick Info Chip -->
              <div style="text-align:right;">
                <span
                  style="font-family:var(--font-mono); font-size:9.5px; padding:4px 10px; border-radius:6px; letter-spacing:0.04em;"
                  [style.background]="mod.session === 'auditor2' ? 'var(--violet-soft)' : 'var(--sky-soft)'"
                  [style.color]="mod.session === 'auditor2' ? 'var(--violet)' : 'var(--sky)'"
                >
                  {{ mod.workflow }}
                </span>
              </div>
            </div>

            <!-- Module Enable Toggle Banner -->
            <div class="card" style="margin-bottom:24px;">
              <div class="card-body" style="display:flex; align-items:center; justify-content:space-between; padding:14px 20px;">
                <div>
                  <div style="font-weight:700; font-size:14px; color:var(--t0);">Enable Module in Execution Queue</div>
                  <div style="font-size:12px; color:var(--t3);">
                    Toggle to automatically include or exclude {{ mod.display }} (flag: <code style="color:var(--accent);">{{ mod.flag }}</code>)
                  </div>
                </div>
                <label class="toggle-switch">
                  <input
                    type="checkbox"
                    [checked]="registryStore.moduleEnabled()[mod.idx]"
                    (change)="registryStore.toggleModule(mod.idx)"
                  />
                  <span class="toggle-slider"></span>
                </label>
              </div>
            </div>

            <!-- Specific Module Form -->
            @switch (mod.idx) {
              @case (0) {
                <app-m0-q-setting />
              }
              @case (1) {
                <app-m1-stock-audit-a1 />
              }
              @case (2) {
                <app-m2-stock-audit-a2 />
              }
              @case (3) {
                <app-m3-summary-table />
              }
              @case (4) {
                <app-m4-recently-audited />
              }
              @case (5) {
                <app-m5-q-audit-summary />
              }
              @case (6) {
                <app-m6-audit-plan />
              }
              @case (7) {
                <app-m7-ongoing-audit />
              }
              @case (8) {
                <app-m8-auditor1-sa />
              }
              @case (9) {
                <app-m9-auditor2-sa />
              }
              @case (10) {
                <app-m10-a-as-table />
              }
              @case (11) {
                <app-m11-a-audit-summary />
              }
              @case (12) {
                <app-m12-a-recently-audit />
              }
              @case (13) {
                <app-m13-create-group />
              }
              @case (14) {
                <app-m14-location-setup />
              }
              @case (15) {
                <app-m15-import-items />
              }
            }
          </div>
        }
      }
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
}
