import { Component, inject, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ModuleRegistryStore } from '../../../state/module-registry.store';
import { RunSessionStore } from '../../../state/run-session.store';
import { MainTab } from '../nav/nav.component';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <aside class="sidebar">
      <div class="sb-scroll-hint" id="sb-scroll-hint">
        <div class="sb-scroll-fade"></div>
        <div class="sb-scroll-pill"><span class="sb-scroll-pill-inner">↓ Scroll</span></div>
      </div>

      <!-- ── Setup Panel ── -->
      @if (activeTab() === 'setup') {
        <div class="sb-panel visible" id="sb-setup">
          <div class="sb-section-label">Configuration</div>
          <div
            class="sb-item"
            id="ssi-0"
            [class.active]="selectedSetupStep() === 0"
            (click)="setupStepChange.emit(0)"
          >
            <div class="sb-item-icon">🌐</div>
            <div>
              <div class="sb-item-name">Environment &amp; Login</div>
              <div class="sb-item-sub">Browser · Credentials</div>
            </div>
          </div>
          <div style="flex:1;"></div>
        </div>
      }

      <!-- ── Execution Panel ── -->
      @if (activeTab() === 'execution') {
        <div class="sb-panel visible" id="sb-execution">
          <div id="sb-exec-scroll" style="flex:1; overflow-y:auto; overflow-x:hidden;">
            <div style="height:6px;"></div>

            <!-- Group 0: Q Audit -->
            <div class="sb-grp">
              <div
                class="sb-grp-hd"
                id="sbh-0"
                [class.open]="registryStore.groupExpanded()[0]"
                (click)="registryStore.toggleGroupExpand(0)"
              >
                <div class="sb-grp-icon">🔍</div>
                <span class="sb-grp-name">Q Audit</span>
                <label class="sb-grp-sw" (click)="$event.stopPropagation()">
                  <input
                    type="checkbox"
                    id="grp-sw-0"
                    [checked]="registryStore.groupEnabled()[0]"
                    (change)="registryStore.toggleGroup(0)"
                  />
                  <span class="sw-track"></span>
                </label>
                <span
                  class="sb-grp-chev"
                  id="sgchev-0"
                  [style.transform]="registryStore.groupExpanded()[0] ? 'rotate(180deg)' : ''"
                >
                  ▾
                </span>
              </div>

              @if (registryStore.groupExpanded()[0]) {
                <div class="sb-grp-body" id="sgbody-0" style="display:block;">
                  @for (mod of getGroupModules(0); track mod.idx) {
                    <div
                      class="sb-sub"
                      [id]="'emr-' + mod.idx"
                      [class.active]="registryStore.selectedModuleIdx() === mod.idx"
                      (click)="registryStore.selectModuleForEditing(mod.idx)"
                    >
                      <span class="sb-sub-icon">{{ mod.icon }}</span>
                      <span class="sb-sub-nm">{{ mod.display }}</span>
                    </div>
                  }
                </div>
              }
            </div>

            <div class="sb-grp-div"></div>

            <!-- Group 1: Audit Plan -->
            <div class="sb-grp">
              <div
                class="sb-grp-hd audit-hd"
                id="sbh-1"
                [class.open]="registryStore.groupExpanded()[1]"
                (click)="registryStore.toggleGroupExpand(1)"
              >
                <div class="sb-grp-icon">📋</div>
                <span class="sb-grp-name">Audit Plan</span>
                <label class="sb-grp-sw" (click)="$event.stopPropagation()">
                  <input
                    type="checkbox"
                    id="grp-sw-1"
                    [checked]="registryStore.groupEnabled()[1]"
                    (change)="registryStore.toggleGroup(1)"
                  />
                  <span class="sw-track"></span>
                </label>
                <span
                  class="sb-grp-chev"
                  id="sgchev-1"
                  [style.transform]="registryStore.groupExpanded()[1] ? 'rotate(180deg)' : ''"
                >
                  ▾
                </span>
              </div>

              @if (registryStore.groupExpanded()[1]) {
                <div class="sb-grp-body" id="sgbody-1" style="display:block;">
                  @for (mod of getGroupModules(1); track mod.idx) {
                    <div
                      class="sb-sub audit-sub"
                      [id]="'emr-' + mod.idx"
                      [class.active]="registryStore.selectedModuleIdx() === mod.idx"
                      (click)="registryStore.selectModuleForEditing(mod.idx)"
                    >
                      <span class="sb-sub-icon">{{ mod.icon }}</span>
                      <span class="sb-sub-nm">{{ mod.display }}</span>
                    </div>
                  }
                </div>
              }
            </div>

            <div class="sb-grp-div"></div>

            <!-- Group 2: Inventory -->
            <div class="sb-grp">
              <div
                class="sb-grp-hd inv-hd"
                id="sbh-2"
                [class.open]="registryStore.groupExpanded()[2]"
                (click)="registryStore.toggleGroupExpand(2)"
              >
                <div class="sb-grp-icon">🗃️</div>
                <span class="sb-grp-name">Inventory</span>
                <label class="sb-grp-sw" (click)="$event.stopPropagation()">
                  <input
                    type="checkbox"
                    id="grp-sw-2"
                    [checked]="registryStore.groupEnabled()[2]"
                    (change)="registryStore.toggleGroup(2)"
                  />
                  <span class="sw-track"></span>
                </label>
                <span
                  class="sb-grp-chev"
                  id="sgchev-2"
                  [style.transform]="registryStore.groupExpanded()[2] ? 'rotate(180deg)' : ''"
                >
                  ▾
                </span>
              </div>

              @if (registryStore.groupExpanded()[2]) {
                <div class="sb-grp-body" id="sgbody-2" style="display:block;">
                  @for (mod of getGroupModules(2); track mod.idx) {
                    <div
                      class="sb-sub inv-sub"
                      [id]="'emr-' + mod.idx"
                      [class.active]="registryStore.selectedModuleIdx() === mod.idx"
                      (click)="registryStore.selectModuleForEditing(mod.idx)"
                    >
                      <span class="sb-sub-icon">{{ mod.icon }}</span>
                      <span class="sb-sub-nm">{{ mod.display }}</span>
                    </div>
                  }
                </div>
              }
            </div>

            <div style="min-height:16px;"></div>
          </div>
        </div>
      }

      <!-- ── Run Panel ── -->
      @if (activeTab() === 'run') {
        <div class="sb-panel visible" id="sb-run">
          @if (sessionStore.isRunning() || sessionStore.runId()) {
            <div class="sb-run-state" id="sb-run-state" style="display:block;">
              <div style="display:flex; align-items:center; gap:7px;">
                <div class="sb-run-state-dot" id="srs-dot" [class.running]="sessionStore.isRunning()"></div>
                <span class="sb-run-state-lbl" id="srs-label">{{ sessionStore.status().toUpperCase() }}</span>
                <span class="sb-run-state-id" id="srs-id">#{{ sessionStore.runId() || '—' }}</span>
              </div>
              <div style="display:flex; justify-content:space-between; align-items:center; gap:6px; margin-top:6px;">
                <span class="sb-run-state-mod" id="srs-mod">{{ sessionStore.currentStepText() }}</span>
                <span class="sb-run-state-pct" id="srs-pct">{{ sessionStore.progress() }}%</span>
              </div>
              <div class="sb-run-state-track" style="margin-top:6px;">
                <div class="sb-run-state-fill" id="srs-fill" [style.width.%]="sessionStore.progress()"></div>
              </div>
            </div>
          } @else {
            <div class="sb-run-empty" id="sb-run-empty">
              <div class="sb-run-empty-icon">
                <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:var(--t4)">
                  <polygon points="5 3 19 12 5 21" />
                </svg>
              </div>
              <div class="sb-run-empty-title">Ready to Run</div>
              <div class="sb-run-empty-body">Configure modules in <strong>Execution</strong>, then launch here.</div>
            </div>
          }

          <div style="flex:1;"></div>

          <div class="sb-foot">
            <div class="sb-foot-row">
              <span class="sb-foot-lbl">Status</span>
              <span class="sb-foot-val" id="run-sb-status">{{ sessionStore.status().toUpperCase() }}</span>
            </div>
            <div class="sb-foot-bar">
              <div class="sb-foot-fill" id="run-sb-fill" [style.width.%]="sessionStore.progress()"></div>
            </div>
          </div>
        </div>
      }
    </aside>
  `
})
export class SidebarComponent {
  readonly registryStore = inject(ModuleRegistryStore);
  readonly sessionStore = inject(RunSessionStore);

  readonly activeTab = input<MainTab>('setup');
  readonly selectedSetupStep = input<number>(0);
  readonly setupStepChange = output<number>();

  getGroupModules(groupIdx: number) {
    return this.registryStore.modules().filter(m => m.group === groupIdx);
  }
}
