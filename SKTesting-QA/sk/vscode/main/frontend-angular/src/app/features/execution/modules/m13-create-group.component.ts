import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';

@Component({
  selector: 'app-m13-create-group',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="module-form-container">
      <!-- 1. Group Details -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title emerald-accent">
            <span class="card-icon">🗃️</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Group Details</div>
              <div style="font-size:12px; color:var(--t3);">Define unique inventory group identifier</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2 g-last">
            <div class="fld">
              <label class="fld-lbl">Group Name <span class="req">*</span></label>
              <input
                type="text"
                [value]="configStore.invGroupName()"
                (input)="configStore.invGroupName.set($any($event.target).value)"
                placeholder="Group_34"
              />
              <div class="fld-hint">Unique identifier for this inventory group</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 2. Inventory Type -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title emerald-accent">
            <span class="card-icon">📦</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Inventory Type</div>
              <div style="font-size:12px; color:var(--t3);">Select item tracking mode</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="am-sec-lbl">Select tracking mode</div>
          <div class="inv-type-grid">
            <div
              class="inv-type-card"
              [class.selected]="configStore.invType() === 'Unit'"
              (click)="configStore.invType.set('Unit')"
            >
              <div class="am-mode-icon">📦</div>
              <div class="am-mode-label">Unit</div>
              <div class="am-mode-desc">Track items as simple unit quantities</div>
              <div class="am-mode-badge">Basic</div>
            </div>

            <div
              class="inv-type-card"
              [class.selected]="configStore.invType() === 'Batch'"
              (click)="configStore.invType.set('Batch')"
            >
              <div class="am-mode-icon">📑</div>
              <div class="am-mode-label">Batch</div>
              <div class="am-mode-desc">Group items by lot or batch number</div>
              <div class="am-mode-badge">Lot-based</div>
            </div>

            <div
              class="inv-type-card"
              [class.selected]="configStore.invType() === 'Serialized'"
              (click)="configStore.invType.set('Serialized')"
            >
              <div class="am-mode-icon">🔖</div>
              <div class="am-mode-label">Serialized</div>
              <div class="am-mode-desc">Each item tracked by unique serial / IMEI</div>
              <div class="am-mode-badge">Per-unit ID</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. Barcode Configuration -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title emerald-accent">
            <span class="card-icon">🏷️</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Barcode Configuration</div>
              <div style="font-size:12px; color:var(--t3);">Custom fields attached to each item</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="fld g-last">
            <label class="fld-lbl">Fields to add <span class="req">*</span></label>
            <textarea
              rows="4"
              [value]="getFieldsAsText()"
              (input)="onFieldsInput($event)"
              placeholder="Item Code&#10;Item Name"
            ></textarea>
            <div class="fld-hint">One field name per line</div>
          </div>
        </div>
      </div>

      <!-- 4. Serial / ID Fields -->
      @if (configStore.invType() === 'Serialized') {
        <div class="card">
          <div class="card-hd">
            <div class="card-title emerald-accent">
              <span class="card-icon">🔖</span>
              <div>
                <div style="font-weight:700; font-size:15px; color:var(--t0);">Serial / ID Fields</div>
                <div style="font-size:12px; color:var(--t3);">Identity columns for Serialized tracking</div>
              </div>
            </div>
          </div>

          <div class="card-body">
            <div class="am-info-box emerald" style="margin-bottom:14px;">
              <span class="am-info-icon">🔖</span>
              <span>Serialized mode — define the ID fields used to uniquely identify each item.</span>
            </div>
            <div class="fld g-last">
              <label class="fld-lbl">ID Fields <span class="req">*</span></label>
              <textarea
                rows="3"
                [value]="getIdsAsText()"
                (input)="onIdsInput($event)"
                placeholder="Serial Number&#10;IMEI&#10;Barcode"
              ></textarea>
              <div class="fld-hint">One ID field per line</div>
            </div>
          </div>
        </div>
      }

      <!-- Navigation Row -->
      <div class="nav-row">
        <button
          type="button"
          class="btn btn-ghost"
          (click)="registryStore.selectModuleForEditing(10)"
        >
          ← Table · Summary · Recent
        </button>
        <button
          type="button"
          class="btn-primary"
          style="background: linear-gradient(135deg, #10b981, #059669);"
          (click)="registryStore.selectModuleForEditing(14)"
        >
          Location Setup →
        </button>
      </div>
    </div>
  `
})
export class M13CreateGroupComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);

  getFieldsAsText(): string {
    return (this.configStore.invFields() || []).join('\n');
  }

  onFieldsInput(e: Event): void {
    const val = (e.target as HTMLTextAreaElement).value;
    const lines = val.split('\n').map(l => l.trim()).filter(Boolean);
    this.configStore.invFields.set(lines);
  }

  getIdsAsText(): string {
    return (this.configStore.invIds() || []).join('\n');
  }

  onIdsInput(e: Event): void {
    const val = (e.target as HTMLTextAreaElement).value;
    const lines = val.split('\n').map(l => l.trim()).filter(Boolean);
    this.configStore.invIds.set(lines);
  }
}
