import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';

@Component({
  selector: 'app-m6-audit-plan',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="module-form-container">
      <!-- 1. Audit Type Mode Selector -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title violet-accent">
            <span class="card-icon">⚡</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Audit Type</div>
              <div style="font-size:12px; color:var(--t3);">Select scheduled audit plan or instant ad-hoc audit</div>
            </div>
          </div>
        </div>
        <div class="card-body" style="padding-bottom:16px;">
          <div class="am-mode-grid">
            <div
              class="am-mode-card"
              [class.selected]="configStore.auditMode() === 'Audit_plan'"
              (click)="configStore.auditMode.set('Audit_plan')"
            >
              <div class="am-mode-icon">📋</div>
              <div class="am-mode-label">Audit Plan</div>
              <div class="am-mode-desc">Scheduled, recurring audit plan</div>
              <div class="am-mode-badge">Default</div>
            </div>

            <div
              class="am-mode-card"
              [class.selected]="configStore.auditMode() === 'Ad_hoc'"
              (click)="configStore.auditMode.set('Ad_hoc')"
            >
              <div class="am-mode-icon">⚡</div>
              <div class="am-mode-label">Ad-hoc</div>
              <div class="am-mode-desc">On-demand, unscheduled audit</div>
              <div class="am-mode-badge">Instant</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ════════ AUDIT PLAN SECTIONS ════════ -->
      @if (configStore.auditMode() === 'Audit_plan') {
        <!-- Run Controls -->
        <div class="card" style="margin-bottom:20px;">
          <div class="card-hd">
            <div class="card-title violet-accent">
              <span class="card-icon">⚙️</span>
              <div>
                <div style="font-weight:700; font-size:15px; color:var(--t0);">Run Controls</div>
                <div style="font-size:12px; color:var(--t3);">Audit plan execution sub-steps</div>
              </div>
            </div>
          </div>
          <div class="card-body" style="display:flex; flex-direction:column; gap:12px;">
            <div class="tgl-row" (click)="configStore.cbTz.set(!configStore.cbTz())">
              <div class="tgl-info">
                <div class="tgl-icon">🕐</div>
                <div>
                  <div class="tgl-title">Run Timezone Step</div>
                  <div class="tgl-sub">run_timezone — generate timezone settings</div>
                </div>
              </div>
              <label class="toggle-switch" (click)="$event.stopPropagation()">
                <input
                  type="checkbox"
                  [checked]="configStore.cbTz()"
                  (change)="configStore.cbTz.set(!configStore.cbTz())"
                />
                <span class="toggle-slider"></span>
              </label>
            </div>

            <div class="tgl-row" (click)="configStore.cbCa.set(!configStore.cbCa())">
              <div class="tgl-info">
                <div class="tgl-icon">📅</div>
                <div>
                  <div class="tgl-title">Run Create Audit</div>
                  <div class="tgl-sub">run_create_audit — create the audit plan record</div>
                </div>
              </div>
              <label class="toggle-switch" (click)="$event.stopPropagation()">
                <input
                  type="checkbox"
                  [checked]="configStore.cbCa()"
                  (change)="configStore.cbCa.set(!configStore.cbCa())"
                />
                <span class="toggle-slider"></span>
              </label>
            </div>

            <div class="tgl-row" (click)="configStore.cbUa.set(!configStore.cbUa())">
              <div class="tgl-info">
                <div class="tgl-icon">🔄</div>
                <div>
                  <div class="tgl-title">Run Update Audit</div>
                  <div class="tgl-sub">run_update_audit — update existing audit plan record</div>
                </div>
              </div>
              <label class="toggle-switch" (click)="$event.stopPropagation()">
                <input
                  type="checkbox"
                  [checked]="configStore.cbUa()"
                  (change)="configStore.cbUa.set(!configStore.cbUa())"
                />
                <span class="toggle-slider"></span>
              </label>
            </div>
          </div>
        </div>

        <!-- Plan Details -->
        <div class="card" style="margin-bottom:20px;">
          <div class="card-hd">
            <div class="card-title violet-accent">
              <span class="card-icon">📝</span>
              <div>
                <div style="font-weight:700; font-size:15px; color:var(--t0);">Plan Details</div>
                <div style="font-size:12px; color:var(--t3);">Ownership and plan metadata</div>
              </div>
            </div>
          </div>
          <div class="card-body">
            <div class="g g2">
              <div class="fld">
                <label class="fld-lbl">Audit Owner <span class="req">*</span></label>
                <input
                  type="text"
                  [value]="configStore.apOwner()"
                  (input)="configStore.apOwner.set($any($event.target).value)"
                  placeholder="Dinesh B"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Group Name <span class="req">*</span></label>
                <input
                  type="text"
                  [value]="configStore.apGroup()"
                  (input)="configStore.apGroup.set($any($event.target).value)"
                  placeholder="Group Name"
                />
              </div>
            </div>

            <div class="g g2" style="margin-top:14px;">
              <div class="fld">
                <label class="fld-lbl">Audit Name <span class="req">*</span></label>
                <input
                  type="text"
                  [value]="configStore.apAuditName()"
                  (input)="configStore.apAuditName.set($any($event.target).value)"
                  placeholder="Audit Name"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Audit Type</label>
                <select
                  [value]="configStore.apAuditType()"
                  (change)="configStore.apAuditType.set($any($event.target).value)"
                >
                  <option value="Complete Count">Complete Count</option>
                  <option value="Cycle Count">Cycle Count</option>
                  <option value="Complete Audit">Complete Audit</option>
                  <option value="Partial Audit">Partial Audit</option>
                  <option value="Investigation Audit">Investigation Audit</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <!-- Schedule -->
        <div class="card" style="margin-bottom:20px;">
          <div class="card-hd">
            <div class="card-title violet-accent">
              <span class="card-icon">📆</span>
              <div>
                <div style="font-weight:700; font-size:15px; color:var(--t0);">Schedule</div>
                <div style="font-size:12px; color:var(--t3);">Frequency and target execution timing</div>
              </div>
            </div>
          </div>
          <div class="card-body">
            <div class="g g2">
              <div class="fld">
                <label class="fld-lbl">Frequency</label>
                <select
                  [value]="configStore.apFrequency()"
                  (change)="configStore.apFrequency.set($any($event.target).value)"
                >
                  <option value="Manual">Manual</option>
                  <option value="one-time">one-time</option>
                  <option value="Daily">Daily</option>
                  <option value="Weekly">Weekly</option>
                  <option value="Monthly">Monthly</option>
                </select>
              </div>

              @if (configStore.apFrequency() !== 'one-time' && configStore.apFrequency() !== 'Daily') {
                <div class="fld">
                  <label class="fld-lbl">Days <span class="req">*</span></label>
                  <input
                    type="number"
                    [value]="configStore.apDays()"
                    (input)="configStore.apDays.set(+$any($event.target).value || 30)"
                  />
                </div>
              }
            </div>

            @if (configStore.apFrequency() === 'Weekly') {
              <div class="g g2 g-last" style="margin-top:14px;">
                <div class="fld">
                  <label class="fld-lbl">Target Day</label>
                  <select
                    [value]="configStore.apTargetDay()"
                    (change)="configStore.apTargetDay.set($any($event.target).value)"
                  >
                    <option value="Monday">Monday</option>
                    <option value="Tuesday">Tuesday</option>
                    <option value="Wednesday">Wednesday</option>
                    <option value="Thursday">Thursday</option>
                    <option value="Friday">Friday</option>
                    <option value="Saturday">Saturday</option>
                    <option value="Sunday">Sunday</option>
                  </select>
                </div>
                <div></div>
              </div>
            }

            @if (configStore.apFrequency() === 'Monthly') {
              <div class="g g2 g-last" style="margin-top:14px;">
                <div class="fld">
                  <label class="fld-lbl">Target Date</label>
                  <input
                    type="text"
                    [value]="configStore.apTargetDate()"
                    (input)="configStore.apTargetDate.set($any($event.target).value)"
                    placeholder="DD/MM/YYYY"
                  />
                </div>
                <div></div>
              </div>
            }
          </div>
        </div>

        <!-- Auditors -->
        <div class="card" style="margin-bottom:20px;">
          <div class="card-hd">
            <div class="card-title violet-accent">
              <span class="card-icon">👥</span>
              <div>
                <div style="font-weight:700; font-size:15px; color:var(--t0);">Auditors</div>
                <div style="font-size:12px; color:var(--t3);">Assigned auditors for plan</div>
              </div>
            </div>
          </div>
          <div class="card-body">
            <div class="g g2 g-last">
              <div class="fld">
                <label class="fld-lbl">Auditor 1 <span class="req">*</span></label>
                <input
                  type="text"
                  [value]="configStore.apAuditor1()"
                  (input)="configStore.apAuditor1.set($any($event.target).value)"
                  placeholder="Auditor 1 name"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Auditor 2</label>
                <input
                  type="text"
                  [value]="configStore.apAuditor2()"
                  (input)="configStore.apAuditor2.set($any($event.target).value)"
                  placeholder="Auditor 2 name"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- Cross Audit -->
        <div class="card" style="margin-bottom:20px;">
          <div class="card-hd">
            <div class="card-title violet-accent">
              <span class="card-icon">🔀</span>
              <div>
                <div style="font-weight:700; font-size:15px; color:var(--t0);">Cross Audit</div>
                <div style="font-size:12px; color:var(--t3);">Cross-validation configuration</div>
              </div>
            </div>
          </div>
          <div class="card-body">
            <div class="g g2 g-last">
              <div class="fld">
                <label class="fld-lbl">Cross Audit Type</label>
                <select
                  [value]="configStore.apCrossType()"
                  (change)="configStore.apCrossType.set($any($event.target).value)"
                >
                  <option value="Random Recheck">Random Recheck</option>
                  <option value="Discrepancy Recheck">Discrepancy Recheck</option>
                  <option value="None">None</option>
                </select>
              </div>
              <div class="fld">
                <label class="fld-lbl">Cross Auditor</label>
                <input
                  type="text"
                  [value]="configStore.apCrossAuditor()"
                  (input)="configStore.apCrossAuditor.set($any($event.target).value)"
                  placeholder="Dinesh"
                />
              </div>
            </div>
          </div>
        </div>
      }

      <!-- ════════ AD-HOC SECTIONS ════════ -->
      @if (configStore.auditMode() === 'Ad_hoc') {
        <div class="card" style="margin-bottom:20px;">
          <div class="card-hd">
            <div class="card-title violet-accent">
              <span class="card-icon">⚡</span>
              <div>
                <div style="font-weight:700; font-size:15px; color:var(--t0);">Basic Details</div>
                <div style="font-size:12px; color:var(--t3);">Ad-hoc audit configuration</div>
              </div>
            </div>
          </div>
          <div class="card-body">
            <div class="g g2">
              <div class="fld">
                <label class="fld-lbl">Auditor 1 <span class="req">*</span></label>
                <input
                  type="text"
                  [value]="configStore.ahAuditor1()"
                  (input)="configStore.ahAuditor1.set($any($event.target).value)"
                  placeholder="Auditor 1"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Auditor 2</label>
                <input
                  type="text"
                  [value]="configStore.ahAuditor2()"
                  (input)="configStore.ahAuditor2.set($any($event.target).value)"
                  placeholder="Auditor 2"
                />
              </div>
            </div>

            <div class="g g2 g-last" style="margin-top:14px;">
              <div class="fld">
                <label class="fld-lbl">Group Name <span class="req">*</span></label>
                <input
                  type="text"
                  [value]="configStore.ahGroup()"
                  (input)="configStore.ahGroup.set($any($event.target).value)"
                  placeholder="Group Name"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Audit Name <span class="req">*</span></label>
                <input
                  type="text"
                  [value]="configStore.ahAuditName()"
                  (input)="configStore.ahAuditName.set($any($event.target).value)"
                  placeholder="Audit Name"
                />
              </div>
            </div>
          </div>
        </div>

        <div class="card" style="margin-bottom:20px;">
          <div class="card-hd">
            <div class="card-title violet-accent">
              <span class="card-icon">⚙️</span>
              <div>
                <div style="font-weight:700; font-size:15px; color:var(--t0);">Run Controls</div>
                <div style="font-size:12px; color:var(--t3);">Ad-hoc execution parameters</div>
              </div>
            </div>
          </div>
          <div class="card-body">
            <div class="tgl-row" (click)="configStore.cbAdhocRun.set(!configStore.cbAdhocRun())">
              <div class="tgl-info">
                <div class="tgl-icon">⚡</div>
                <div>
                  <div class="tgl-title">Run Create Ad-hoc Audit</div>
                  <div class="tgl-sub">run_create_Ad_hoc_Audit — create ad-hoc audit record</div>
                </div>
              </div>
              <label class="toggle-switch" (click)="$event.stopPropagation()">
                <input
                  type="checkbox"
                  [checked]="configStore.cbAdhocRun()"
                  (change)="configStore.cbAdhocRun.set(!configStore.cbAdhocRun())"
                />
                <span class="toggle-slider"></span>
              </label>
            </div>

            <div class="g g2 g-last" style="margin-top:14px;">
              <div class="fld">
                <label class="fld-lbl">Audit Type</label>
                <select
                  [value]="configStore.ahAuditTypeMain()"
                  (change)="configStore.ahAuditTypeMain.set($any($event.target).value)"
                >
                  <option value="Complete Audit">Complete Audit</option>
                  <option value="Partial Audit">Partial Audit</option>
                  <option value="Investigation Audit">Investigation Audit</option>
                </select>
              </div>

              <div class="fld">
                <label class="fld-lbl">Static / Dynamic</label>
                <select
                  [value]="configStore.ahAuditType()"
                  (change)="configStore.ahAuditType.set($any($event.target).value)"
                >
                  <option value="Dynamic">Dynamic</option>
                  <option value="Static">Static</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      }

      <!-- ════════ COMMON: CHECKBOXES & PHOTO ════════ -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title violet-accent">
            <span class="card-icon">☑️</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Audit Features</div>
              <div style="font-size:12px; color:var(--t3);">Damage checks, blind counts &amp; photo sampling</div>
            </div>
          </div>
        </div>
        <div class="card-body">
          <div class="chk-grid g3 g-last">
            <div
              class="chk-card"
              [class.selected]="configStore.apCbDamaged()"
              (click)="configStore.apCbDamaged.set(!configStore.apCbDamaged())"
            >
              <input type="checkbox" [checked]="configStore.apCbDamaged()" (click)="$event.stopPropagation()" />
              <div class="chk-box"></div>
              <div class="chk-lbl">Audit Damaged</div>
            </div>

            <div
              class="chk-card"
              [class.selected]="configStore.apCbStock()"
              (click)="configStore.apCbStock.set(!configStore.apCbStock())"
            >
              <input type="checkbox" [checked]="configStore.apCbStock()" (click)="$event.stopPropagation()" />
              <div class="chk-box"></div>
              <div class="chk-lbl">Stock Count</div>
            </div>

            <div
              class="chk-card"
              [class.selected]="configStore.apCbGeo()"
              (click)="configStore.apCbGeo.set(!configStore.apCbGeo())"
            >
              <input type="checkbox" [checked]="configStore.apCbGeo()" (click)="$event.stopPropagation()" />
              <div class="chk-box"></div>
              <div class="chk-lbl">Geo Location</div>
            </div>
          </div>

          <div class="g g2" style="margin-top:16px;">
            <div class="fld">
              <label class="fld-lbl">Photo Validation Type</label>
              <select
                [value]="configStore.apPhotoType()"
                (change)="configStore.apPhotoType.set($any($event.target).value)"
              >
                <option value="None">None</option>
                <option value="Random">Random</option>
                <option value="Damaged">Damaged</option>
              </select>
            </div>

            @if (configStore.apPhotoType() !== 'None') {
              <div class="fld">
                <label class="fld-lbl">Sample Size (%)</label>
                <input
                  type="number"
                  [value]="configStore.apSampleSize()"
                  (input)="configStore.apSampleSize.set(+$any($event.target).value || 0)"
                  placeholder="0"
                />
              </div>
            }
          </div>
        </div>
      </div>

      <!-- ════════ COMMON: AUDIT MAPPING TYPE ════════ -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title violet-accent">
            <span class="card-icon">🗂️</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Audit Mapping Type</div>
              <div style="font-size:12px; color:var(--t3);">Assignment strategy for items</div>
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
              <div class="am-mode-desc">Items assigned randomly across auditors</div>
              <div class="am-mode-badge">Default</div>
            </div>

            <div
              class="am-mode-card"
              [class.selected]="configStore.auditorMappingType() === 'By Category'"
              (click)="configStore.auditorMappingType.set('By Category')"
            >
              <div class="am-mode-icon">🏷️</div>
              <div class="am-mode-label">By Category</div>
              <div class="am-mode-desc">Specific item categories</div>
              <div class="am-mode-badge">Category based</div>
            </div>

            <div
              class="am-mode-card"
              [class.selected]="configStore.auditorMappingType() === 'By Storage'"
              (click)="configStore.auditorMappingType.set('By Storage')"
            >
              <div class="am-mode-icon">🏭</div>
              <div class="am-mode-label">By Storage</div>
              <div class="am-mode-desc">Specific storage zones</div>
              <div class="am-mode-badge">Storage based</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Navigation Row -->
      <div class="nav-row">
        <button
          type="button"
          class="btn btn-ghost"
          (click)="registryStore.selectModuleForEditing(5)"
        >
          ← Q_audit_Summary
        </button>
        <button
          type="button"
          class="btn-primary"
          (click)="registryStore.selectModuleForEditing(7)"
        >
          Ongoing Audit →
        </button>
      </div>
    </div>
  `
})
export class M6AuditPlanComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);
}
