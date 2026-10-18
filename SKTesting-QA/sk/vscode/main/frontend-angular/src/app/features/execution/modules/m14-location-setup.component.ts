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
      <div class="card">
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
}
