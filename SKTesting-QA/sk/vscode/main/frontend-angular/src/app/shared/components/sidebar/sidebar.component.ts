import { Component, inject, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ModuleRegistryStore } from '../../../state/module-registry.store';
import { MainTab } from '../nav/nav.component';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <aside class="sidebar" [style.display]="activeTab() === 'run' ? 'none' : ''">
      <!-- ════════ SETUP PANEL ════════ -->
      @if (activeTab() === 'setup') {
        <div class="sb-panel visible">
          <div class="sb-section-label">Configuration</div>
          <div
            class="sb-item"
            [class.active]="selectedSetupStep() === 0"
            (click)="setupStepChange.emit(0)"
          >
            <div class="sb-item-icon">🌐</div>
            <div>
              <div class="sb-item-name">Environment &amp; Login</div>
              <div class="sb-item-sub">Browser · Credentials</div>
            </div>
          </div>
          <div
            class="sb-item"
            [class.active]="selectedSetupStep() === 1"
            (click)="setupStepChange.emit(1)"
            style="margin-top: 6px;"
          >
            <div class="sb-item-icon">⚡</div>
            <div>
              <div class="sb-item-name">Timeouts &amp; Delays</div>
              <div class="sb-item-sub">Wait actions · Intervals</div>
            </div>
          </div>
        </div>
      }

      <!-- ════════ EXECUTION PANEL ════════ -->
      @if (activeTab() === 'execution') {
        <div class="sb-panel visible" style="display:flex; flex-direction:column; height:100%;">
          <!-- Quick Selection Controls -->
          <div style="display:flex; justify-content:space-between; align-items:center; padding: 12px 14px 6px;">
            <div class="sb-section-label" style="margin:0;">Modules</div>
            <div style="display:flex; gap:6px;">
              <button
                type="button"
                class="btn-link"
                style="font-size:9.5px; text-transform:uppercase;"
                (click)="registryStore.selectAll()"
              >
                All
              </button>
              <span style="color:var(--t4);">·</span>
              <button
                type="button"
                class="btn-link"
                style="font-size:9.5px; text-transform:uppercase; color:var(--t3);"
                (click)="registryStore.deselectAll()"
              >
                None
              </button>
            </div>
          </div>

          <!-- Module Groups Accordion -->
          <div style="flex:1; overflow-y:auto; overflow-x:hidden; padding: 0 10px;">
            @for (grp of registryStore.groups(); track grp.idx) {
              <div class="sb-grp" style="margin-bottom:8px;">
                <!-- Group Header -->
                <div
                  class="sb-grp-hd"
                  [class.open]="registryStore.groupExpanded()[grp.idx]"
                  (click)="registryStore.toggleGroupExpand(grp.idx)"
                >
                  <div class="sb-grp-icon">
                    {{ grp.idx === 0 ? '🔍' : grp.idx === 1 ? '📅' : '📦' }}
                  </div>
                  <span class="sb-grp-name">{{ grp.name }}</span>

                  <!-- Group Toggle Switch -->
                  <label class="sb-grp-sw" (click)="$event.stopPropagation()">
                    <input
                      type="checkbox"
                      [checked]="registryStore.groupEnabled()[grp.idx]"
                      (change)="registryStore.toggleGroup(grp.idx)"
                    />
                    <span class="sw-track"></span>
                  </label>

                  <span
                    class="sb-grp-chev"
                    [style.transform]="registryStore.groupExpanded()[grp.idx] ? 'rotate(180deg)' : ''"
                  >
                    ▾
                  </span>
                </div>

                <!-- Group Sub-items -->
                <div
                  class="sb-grp-body"
                  [class.open]="registryStore.groupExpanded()[grp.idx]"
                >
                  @for (mod of getModulesForGroup(grp.idx); track mod.idx) {
                    <div
                      class="sb-sub"
                      [class.active]="registryStore.selectedModuleIdx() === mod.idx"
                      (click)="registryStore.selectModuleForEditing(mod.idx)"
                    >
                      <span class="sb-sub-icon">{{ mod.icon || '⚙️' }}</span>
                      <span class="sb-sub-nm">{{ mod.display }}</span>

                      <!-- Module checkbox toggle -->
                      <label
                        class="toggle-switch small"
                        style="margin-left:auto; cursor:pointer;"
                        (click)="$event.stopPropagation()"
                      >
                        <input
                          type="checkbox"
                          [checked]="registryStore.moduleEnabled()[mod.idx]"
                          (change)="registryStore.toggleModule(mod.idx)"
                        />
                        <span class="toggle-slider"></span>
                      </label>
                    </div>
                  }
                </div>
              </div>
            }
          </div>

          <!-- Footer Count -->
          <div style="padding:14px; border-top:1px solid var(--glass-border-dim); background:var(--glass-4);">
            <div style="display:flex; justify-content:space-between; font-family:var(--font-mono); font-size:10px; color:var(--t3); margin-bottom:6px;">
              <span>Active Modules</span>
              <span>{{ registryStore.activeCount() }} / {{ registryStore.totalCount() }}</span>
            </div>
            <div style="height:4px; width:100%; background:var(--glass-border-dim); border-radius:2px; overflow:hidden;">
              <div
                style="height:100%; background:var(--accent-btn); border-radius:2px; transition:width 0.3s;"
                [style.width.%]="(registryStore.activeCount() / registryStore.totalCount()) * 100"
              ></div>
            </div>
          </div>
        </div>
      }
    </aside>
  `
})
export class SidebarComponent {
  readonly registryStore = inject(ModuleRegistryStore);

  readonly activeTab = input<MainTab>('setup');
  readonly selectedSetupStep = input<number>(0);
  readonly setupStepChange = output<number>();

  getModulesForGroup(groupIdx: number) {
    return this.registryStore.modules().filter(m => m.group === groupIdx);
  }
}
