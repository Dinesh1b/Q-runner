import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';

@Component({
  selector: 'app-m14-location-setup',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="module-form-container">
      <!-- Run Options -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title emerald-accent">
            <span class="card-icon">⚙️</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Run Options</div>
              <div style="font-size:12px; color:var(--t3);">Choose what this module does</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          @for (opt of runOptions; track opt.title) {
            <div class="tgl-row" (click)="opt.on.set(!opt.on())">
              <div class="tgl-info">
                <div class="tgl-icon">{{ opt.icon }}</div>
                <div>
                  <div class="tgl-title">{{ opt.title }}</div>
                  <div class="tgl-sub">{{ opt.sub }}</div>
                </div>
              </div>
              <label class="toggle-switch" (click)="$event.stopPropagation()">
                <input type="checkbox" [checked]="opt.on()" (change)="opt.on.set(!opt.on())" />
                <span class="toggle-slider"></span>
              </label>
            </div>
          }
        </div>
      </div>

      @if (configStore.lsRunTests()) {
        <!-- Warehouse Tests -->
        <div class="card" style="margin-bottom:20px;">
          <div class="card-hd">
            <div class="card-title emerald-accent">
              <span class="card-icon">🧪</span>
              <div>
                <div style="font-weight:700; font-size:15px; color:var(--t0);">Warehouse Tests</div>
                <div style="font-size:12px; color:var(--t3);">WH_001 – WH_040 · PASS / FAIL / SKIP per case, HTML report in reports/warehouse</div>
              </div>
            </div>
          </div>

          <div class="card-body">
            <div class="fld-hint" style="color:var(--amber); margin-bottom:12px;">
              ⚠ Adds, deletes and saves test locations in the selected environment. Only locations named
              {{ testStamp() }}… are changed; existing locations and the saved mode are left as they are.
            </div>

            <label class="fld-lbl">Groups</label>
            <div class="chk-grid g3" style="margin-bottom:14px;">
              @for (group of testGroups; track group.key) {
                <div class="chk-card" [class.selected]="hasGroup(group.key)" (click)="toggleGroup(group.key)">
                  <input type="checkbox" [checked]="hasGroup(group.key)" (click)="$event.stopPropagation()" />
                  <div class="chk-box"></div>
                  <div class="chk-lbl">{{ group.label }}</div>
                </div>
              }
            </div>

            <div class="g g2">
              <div class="fld">
                <label class="fld-lbl">TC IDs <span class="fld-hint">(comma separated; blank = every case in the groups)</span></label>
                <input
                  type="text"
                  [value]="configStore.lsTestCases()"
                  (input)="configStore.lsTestCases.set($any($event.target).value)"
                  placeholder="WH_007, WH_021"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Test prefix <span class="fld-hint">(up to 3 characters)</span></label>
                <input
                  type="text"
                  maxlength="3"
                  [value]="configStore.lsTestPrefix()"
                  (input)="configStore.lsTestPrefix.set($any($event.target).value)"
                  placeholder="QA"
                />
              </div>
            </div>

            <div class="tgl-row" style="margin-top:14px;" (click)="configStore.lsTestCleanup.set(!configStore.lsTestCleanup())">
              <div class="tgl-info">
                <div class="tgl-icon">🧹</div>
                <div>
                  <div class="tgl-title">Clean up</div>
                  <div class="tgl-sub">ls_test_cleanup — delete the test locations at the end and check the page is back to its start</div>
                </div>
              </div>
              <label class="toggle-switch" (click)="$event.stopPropagation()">
                <input
                  type="checkbox"
                  [checked]="configStore.lsTestCleanup()"
                  (change)="configStore.lsTestCleanup.set(!configStore.lsTestCleanup())"
                />
                <span class="toggle-slider"></span>
              </label>
            </div>
          </div>
        </div>
      }

      <div class="card" [style.display]="configStore.lsRunSetup() ? null : 'none'">
        <div class="card-hd">
          <div class="card-title emerald-accent">
            <span class="card-icon">📍</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Location Structure</div>
              <div style="font-size:12px; color:var(--t3);">Configure zones, aisles, bays and levels</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2">
            <div class="fld">
              <label class="fld-lbl">Zones <span class="fld-hint">(comma separated)</span></label>
              <input
                type="text"
                [value]="configStore.lsZones()"
                (input)="configStore.lsZones.set($any($event.target).value)"
                placeholder="SA, SB"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Aisles</label>
              <input
                type="text"
                [value]="configStore.lsAisles()"
                (input)="configStore.lsAisles.set($any($event.target).value)"
                placeholder="A1, A2"
              />
            </div>
          </div>

          <div class="g g2 g-last" style="margin-top:14px;">
            <div class="fld">
              <label class="fld-lbl">Bays</label>
              <input
                type="text"
                [value]="configStore.lsBays()"
                (input)="configStore.lsBays.set($any($event.target).value)"
                placeholder="B1, B2"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Levels</label>
              <input
                type="text"
                [value]="configStore.lsLevels()"
                (input)="configStore.lsLevels.set($any($event.target).value)"
                placeholder="L1, L2"
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
          (click)="registryStore.selectModuleForEditing(13)"
        >
          ← Create Group
        </button>
        <button
          type="button"
          class="btn-primary"
          style="background: linear-gradient(135deg, #10b981, #059669);"
          (click)="registryStore.selectModuleForEditing(15)"
        >
          Import Items →
        </button>
      </div>
    </div>
  `
})
export class M14LocationSetupComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);

  readonly runOptions = [
    { on: this.configStore.lsRunSetup, icon: '📍', title: 'Run Location Setup',
      sub: 'ls_run_setup — add the zones, aisles, bays and levels below' },
    { on: this.configStore.lsRunTests, icon: '🧪', title: 'Run Warehouse Tests',
      sub: 'ls_run_tests — run the Warehouse Configuration test cases WH_001 – WH_040' },
  ];

  readonly testGroups = [
    { key: 'functional', label: 'Functional (WH_001–020)' },
    { key: 'validation', label: 'Validation (WH_021–030)' },
    { key: 'ui', label: 'UI (WH_031–040)' },
  ];

  hasGroup(key: string): boolean {
    return this.configStore.lsTestGroups().includes(key);
  }

  toggleGroup(key: string): void {
    const groups = this.configStore.lsTestGroups();
    const next = groups.includes(key) ? groups.filter(g => g !== key) : [...groups, key];
    if (next.length) this.configStore.lsTestGroups.set(next);   // keep at least one group
  }

  testStamp(): string {
    return `${(this.configStore.lsTestPrefix() || 'QA').slice(0, 3)}<HHMM>`;
  }
}
