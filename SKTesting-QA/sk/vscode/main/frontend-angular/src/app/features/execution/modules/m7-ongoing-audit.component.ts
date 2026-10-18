import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';
import { ExcelUploaderComponent } from '../components/excel-uploader/excel-uploader.component';

@Component({
  selector: 'app-m7-ongoing-audit',
  standalone: true,
  imports: [CommonModule, FormsModule, ExcelUploaderComponent],
  template: `
    <div class="module-form-container">
      <!-- 1. Audit Config Card -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title violet-accent">
            <span class="card-icon">🔄</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Audit Configuration</div>
              <div style="font-size:12px; color:var(--t3);">In-progress audit identification and parameters</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2">
            <div class="fld">
              <label class="fld-lbl">Group Name <span class="req">*</span></label>
              <input
                type="text"
                [value]="configStore.oaGroupName()"
                (input)="configStore.oaGroupName.set($any($event.target).value)"
                placeholder="Group Name"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Audit Name <span class="req">*</span></label>
              <input
                type="text"
                [value]="configStore.oaAuditName()"
                (input)="configStore.oaAuditName.set($any($event.target).value)"
                placeholder="Audit Name"
              />
            </div>
          </div>

          <div class="g g2" style="margin-top:14px;">
            <div class="fld">
              <label class="fld-lbl">Auditor 1</label>
              <input
                type="text"
                [value]="configStore.oaAuditor1()"
                (input)="configStore.oaAuditor1.set($any($event.target).value)"
                placeholder="Auditor 1"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Auditor 2</label>
              <input
                type="text"
                [value]="configStore.oaAuditor2()"
                (input)="configStore.oaAuditor2.set($any($event.target).value)"
                placeholder="Auditor 2"
              />
            </div>
          </div>

          <!-- Checkboxes -->
          <div class="chk-grid g3 g-last" style="margin-top:16px;">
            <div
              class="chk-card"
              [class.selected]="configStore.oaCbDamaged()"
              (click)="configStore.oaCbDamaged.set(!configStore.oaCbDamaged())"
            >
              <input type="checkbox" [checked]="configStore.oaCbDamaged()" (click)="$event.stopPropagation()" />
              <div class="chk-box"></div>
              <div class="chk-lbl">Audit Damaged</div>
            </div>

            <div
              class="chk-card"
              [class.selected]="configStore.oaCbStock()"
              (click)="configStore.oaCbStock.set(!configStore.oaCbStock())"
            >
              <input type="checkbox" [checked]="configStore.oaCbStock()" (click)="$event.stopPropagation()" />
              <div class="chk-box"></div>
              <div class="chk-lbl">Stock Items</div>
            </div>

            <div
              class="chk-card"
              [class.selected]="configStore.oaCbGeo()"
              (click)="configStore.oaCbGeo.set(!configStore.oaCbGeo())"
            >
              <input type="checkbox" [checked]="configStore.oaCbGeo()" (click)="$event.stopPropagation()" />
              <div class="chk-box"></div>
              <div class="chk-lbl">Geo Location</div>
            </div>
          </div>

          <div class="g g2" style="margin-top:16px;">
            <div class="fld">
              <label class="fld-lbl">Photo Validation Type</label>
              <select
                [value]="configStore.oaPhotoType()"
                (change)="configStore.oaPhotoType.set($any($event.target).value)"
              >
                <option value="None">None</option>
                <option value="Random">Random</option>
                <option value="Damaged">Damaged</option>
              </select>
            </div>

            @if (configStore.oaPhotoType() !== 'None') {
              <div class="fld">
                <label class="fld-lbl">Sample Size (%)</label>
                <input
                  type="number"
                  [value]="configStore.oaSampleSize()"
                  (input)="configStore.oaSampleSize.set(+$any($event.target).value || 0)"
                  placeholder="0"
                />
              </div>
            }
          </div>
        </div>
      </div>

      <!-- 2. Auditor Mapping Card -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title violet-accent">
            <span class="card-icon">🗂️</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Auditor Mapping</div>
              <div style="font-size:12px; color:var(--t3);">Configure Excel columns and mapping strategy</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2">
            <div class="fld">
              <label class="fld-lbl">Mapping Type</label>
              <select
                [value]="configStore.oaMappingType() || 'Random'"
                (change)="configStore.oaMappingType.set($any($event.target).value)"
              >
                <option value="Random">Random</option>
                <option value="By Category">By Category</option>
                <option value="By Storage">By Storage</option>
              </select>
            </div>
            <div class="fld">
              <label class="fld-lbl">Mapping Sheet</label>
              <input
                type="text"
                [value]="configStore.oaMappingSheet()"
                (input)="configStore.oaMappingSheet.set($any($event.target).value)"
                placeholder="auditor_mapping"
              />
            </div>
          </div>

          <div class="g g3 g-last" style="margin-top:14px;">
            <div class="fld">
              <label class="fld-lbl">Auditor Column</label>
              <input
                type="text"
                [value]="configStore.oaAuditorCol()"
                (input)="configStore.oaAuditorCol.set($any($event.target).value)"
                placeholder="Auditor"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Category Column</label>
              <input
                type="text"
                [value]="configStore.oaCategoryCol()"
                (input)="configStore.oaCategoryCol.set($any($event.target).value)"
                placeholder="Category"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Storage Column</label>
              <input
                type="text"
                [value]="configStore.oaStorageCol()"
                (input)="configStore.oaStorageCol.set($any($event.target).value)"
                placeholder="Storage"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 3. Excel Import -->
      <app-excel-uploader
        label="Drag & Drop 'main_qexcel.xlsx'"
        storageKey="OA_EXCEL"
        sampleUrl="/sample_excel"
        sampleFilename="main_qexcel.xlsx"
        sheetLabel="Ongoing Audit Sheet Name"
        sheetHint="Configures which sheet to use for Ongoing Audit"
        [selectedSheet]="configStore.oaSheet()"
        (sheetChange)="configStore.oaSheet.set($event)"
      />

      <!-- Navigation Row -->
      <div class="nav-row">
        <button
          type="button"
          class="btn btn-ghost"
          (click)="registryStore.selectModuleForEditing(6)"
        >
          ← Audit Plan
        </button>
        <button
          type="button"
          class="btn-primary"
          (click)="registryStore.selectModuleForEditing(8)"
        >
          Auditor 1 SA →
        </button>
      </div>
    </div>
  `
})
export class M7OngoingAuditComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);
}
