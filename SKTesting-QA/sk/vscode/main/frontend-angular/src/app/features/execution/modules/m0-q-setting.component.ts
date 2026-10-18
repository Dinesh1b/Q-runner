import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';
import { ExcelUploaderComponent } from '../components/excel-uploader/excel-uploader.component';

@Component({
  selector: 'app-m0-q-setting',
  standalone: true,
  imports: [CommonModule, FormsModule, ExcelUploaderComponent],
  template: `
    <div class="module-form-container">
      <!-- 1. General Audit Configuration -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title">
            <span class="card-icon">⚙️</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Q_Setting Configuration</div>
              <div style="font-size:12px; color:var(--t3);">Audit identification and auditor names</div>
            </div>
          </div>
        </div>
        <div class="card-body">
          <div class="g g2">
            <div class="fld">
              <label class="fld-lbl">Audit Name <span class="req">*</span></label>
              <input
                type="text"
                [value]="configStore.qsAuditName()"
                (input)="configStore.qsAuditName.set($any($event.target).value)"
                placeholder="Audit_TEST"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Branch</label>
              <input
                type="text"
                [value]="configStore.branch()"
                (input)="configStore.branch.set($any($event.target).value)"
                placeholder="gr"
              />
            </div>
          </div>

          <div class="g g3 g-last" style="margin-top:14px;">
            <div class="fld">
              <label class="fld-lbl">Auditor 1 Name</label>
              <input
                type="text"
                [value]="configStore.qsA1()"
                (input)="configStore.qsA1.set($any($event.target).value)"
                placeholder="Auditor 1"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Auditor 2 Name</label>
              <input
                type="text"
                [value]="configStore.qsA2()"
                (input)="configStore.qsA2.set($any($event.target).value)"
                placeholder="Auditor 2"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Auditor 3 (optional)</label>
              <input
                type="text"
                [value]="configStore.qsA3()"
                (input)="configStore.qsA3.set($any($event.target).value)"
                placeholder="—"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 2. Checkboxes Card -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title">
            <span class="card-icon">☑️</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Audit Features</div>
              <div style="font-size:12px; color:var(--t3);">Enable specific checks and captures</div>
            </div>
          </div>
        </div>
        <div class="card-body">
          <div class="chk-grid g2 g-last">
            <div
              class="chk-card"
              [class.selected]="configStore.qsCbDamaged()"
              (click)="configStore.qsCbDamaged.set(!configStore.qsCbDamaged())"
            >
              <input type="checkbox" [checked]="configStore.qsCbDamaged()" (click)="$event.stopPropagation()" />
              <div class="chk-box"></div>
              <div class="chk-lbl">Audit Damaged</div>
            </div>

            <div
              class="chk-card"
              [class.selected]="configStore.qsCbStock()"
              (click)="configStore.qsCbStock.set(!configStore.qsCbStock())"
            >
              <input type="checkbox" [checked]="configStore.qsCbStock()" (click)="$event.stopPropagation()" />
              <div class="chk-box"></div>
              <div class="chk-lbl">Stock Count</div>
            </div>

            <div
              class="chk-card"
              [class.selected]="configStore.qsCbGeo()"
              (click)="configStore.qsCbGeo.set(!configStore.qsCbGeo())"
            >
              <input type="checkbox" [checked]="configStore.qsCbGeo()" (click)="$event.stopPropagation()" />
              <div class="chk-box"></div>
              <div class="chk-lbl">Geo Location</div>
            </div>

            <div
              class="chk-card"
              [class.selected]="configStore.qsCbPhoto()"
              (click)="configStore.qsCbPhoto.set(!configStore.qsCbPhoto())"
            >
              <input type="checkbox" [checked]="configStore.qsCbPhoto()" (click)="$event.stopPropagation()" />
              <div class="chk-box"></div>
              <div class="chk-lbl">Photo Capture</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. Auditor Mapping Card -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title">
            <span class="card-icon">👥</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Auditor Mapping</div>
              <div style="font-size:12px; color:var(--t3);">Assignment strategy and column configuration</div>
            </div>
          </div>
        </div>
        <div class="card-body">
          <div class="am-sec-lbl">Assignment Strategy</div>
          <div class="am-mode-grid">
            <div
              class="am-mode-card"
              [class.selected]="configStore.auditorMappingType() === 'Random'"
              (click)="configStore.auditorMappingType.set('Random')"
            >
              <div class="am-mode-icon">🎲</div>
              <div class="am-mode-label">Random</div>
              <div class="am-mode-desc">Items assigned randomly across all auditors</div>
              <div class="am-mode-badge">Default</div>
            </div>

            <div
              class="am-mode-card"
              [class.selected]="configStore.auditorMappingType() === 'By Category'"
              (click)="configStore.auditorMappingType.set('By Category')"
            >
              <div class="am-mode-icon">🏷️</div>
              <div class="am-mode-label">By Category</div>
              <div class="am-mode-desc">Each auditor handles specific categories</div>
              <div class="am-mode-badge">Category col req.</div>
            </div>

            <div
              class="am-mode-card"
              [class.selected]="configStore.auditorMappingType() === 'By Storage'"
              (click)="configStore.auditorMappingType.set('By Storage')"
            >
              <div class="am-mode-icon">🏭</div>
              <div class="am-mode-label">By Storage</div>
              <div class="am-mode-desc">Auditors assigned to storage zones</div>
              <div class="am-mode-badge">Storage col req.</div>
            </div>
          </div>

          <div class="am-sec-lbl" style="margin-top:18px;">Excel Sheet Configuration</div>
          <div class="g g2">
            <div class="fld">
              <label class="fld-lbl">Mapping Sheet Name <span class="req">*</span></label>
              <input
                type="text"
                [value]="configStore.excelSheetAuditorMapping()"
                (input)="configStore.excelSheetAuditorMapping.set($any($event.target).value)"
                placeholder="auditor_mapping"
              />
            </div>
            <div class="fld">
              <label class="fld-lbl">Auditor Column <span class="req">*</span></label>
              <input
                type="text"
                [value]="configStore.excelAuditorCol()"
                (input)="configStore.excelAuditorCol.set($any($event.target).value)"
                placeholder="Auditor"
              />
            </div>
          </div>

          @if (configStore.auditorMappingType() === 'By Category') {
            <div class="am-cond-group">
              <div class="am-info-box">
                <span class="am-info-icon">🏷️</span>
                <span>By Category mode — sheet must include a <strong>Category</strong> column.</span>
              </div>
              <div class="g g2 g-last">
                <div class="fld">
                  <label class="fld-lbl">Category Column <span class="req">*</span></label>
                  <input
                    type="text"
                    [value]="configStore.excelCategoryCol()"
                    (input)="configStore.excelCategoryCol.set($any($event.target).value)"
                    placeholder="Category"
                  />
                </div>
                <div></div>
              </div>
            </div>
          }

          @if (configStore.auditorMappingType() === 'By Storage') {
            <div class="am-cond-group">
              <div class="am-info-box">
                <span class="am-info-icon">🏭</span>
                <span>By Storage mode — sheet must include a <strong>Storage</strong> column.</span>
              </div>
              <div class="g g2 g-last">
                <div class="fld">
                  <label class="fld-lbl">Storage Column <span class="req">*</span></label>
                  <input
                    type="text"
                    [value]="configStore.excelStorageCol()"
                    (input)="configStore.excelStorageCol.set($any($event.target).value)"
                    placeholder="Storage"
                  />
                </div>
                <div></div>
              </div>
            </div>
          }

          @if (configStore.auditorMappingType() === 'Random') {
            <div class="am-cond-group">
              <div class="am-info-box warn">
                <span class="am-info-icon">🎲</span>
                <span>Random mode — only the <strong>Auditor</strong> column is needed.</span>
              </div>
            </div>
          }
        </div>
      </div>

      <!-- 4. Excel Import Component -->
      <app-excel-uploader
        label="Drag & Drop 'main_qexcel.xlsx'"
        storageKey="OA_EXCEL"
        sampleUrl="/sample_excel"
        sampleFilename="main_qexcel.xlsx"
        sheetLabel="Q_Setting Sheet Name"
        sheetHint="Configures which sheet to use for Q_Setting"
        [selectedSheet]="configStore.qsSheet()"
        (sheetChange)="configStore.qsSheet.set($event)"
      />

      <!-- Navigation Row -->
      <div class="nav-row">
        <button type="button" class="btn btn-ghost" style="visibility:hidden;">Placeholder</button>
        <button
          type="button"
          class="btn-primary"
          (click)="registryStore.selectModuleForEditing(1)"
        >
          Stock Audit A1 →
        </button>
      </div>
    </div>
  `
})
export class M0QSettingComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);
}
