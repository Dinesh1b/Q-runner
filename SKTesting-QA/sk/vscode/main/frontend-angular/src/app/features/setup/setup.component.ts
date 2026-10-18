import { Component, inject, signal, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../state/run-config.store';
import { ModuleRegistryStore } from '../../state/module-registry.store';
import { JsonImportService, ImportResult } from '../../core/services/json-import.service';

@Component({
  selector: 'app-setup',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div id="content-setup" class="content">
      <!-- Environment & Login Page (sp0) -->
      <div class="page active" id="sp0">
        <!-- Browser & Target Environment -->
        <div class="card">
          <div class="card-head">
            <div class="card-title">Browser &amp; Target Environment</div>
          </div>
          <div class="card-body">
            <div class="g g2">
              <div class="fld">
                <label class="fld-lbl">Browser</label>
                <select
                  id="browsername"
                  [value]="configStore.browsername()"
                  (change)="configStore.browsername.set($any($event.target).value)"
                >
                  <option value="chrome">Chrome</option>
                  <option value="firefox">Firefox</option>
                  <option value="webkit">WebKit / Safari</option>
                </select>
              </div>
              <div class="fld">
                <label class="fld-lbl">Environment</label>
                <select
                  id="environments"
                  [value]="configStore.environments()"
                  (change)="configStore.environments.set($any($event.target).value)"
                >
                  <option value="PRODUCTION">PRODUCTION</option>
                  <option value="STAGING">STAGING</option>
                  <option value="QA">QA</option>
                  <option value="DEV">DEV</option>
                </select>
              </div>
            </div>

            <div class="g g2">
              <div class="fld">
                <label class="fld-lbl">Branch</label>
                <input
                  type="text"
                  id="branch"
                  [value]="configStore.branch()"
                  (input)="configStore.branch.set($any($event.target).value)"
                />
                <div class="fld-hint">Branch to select during login</div>
              </div>
              <div class="fld">
                <label class="fld-lbl">Company Name <span class="req">*</span></label>
                <input
                  type="text"
                  id="company_name"
                  [value]="configStore.companyName()"
                  (input)="configStore.companyName.set($any($event.target).value)"
                />
              </div>
            </div>

            <div class="g g3 g-last">
              <div class="fld">
                <label class="fld-lbl">Default Timeout (ms)</label>
                <input
                  type="number"
                  id="DEFAULT_TIMEOUT"
                  [value]="configStore.defaultTimeout()"
                  (input)="configStore.defaultTimeout.set(+$any($event.target).value)"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Short Timeout (ms)</label>
                <input
                  type="number"
                  id="SHORT_TIMEOUT"
                  [value]="configStore.shortTimeout()"
                  (input)="configStore.shortTimeout.set(+$any($event.target).value)"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Wait After Action (ms)</label>
                <input
                  type="number"
                  id="WAIT_AFTER_ACTION"
                  [value]="configStore.waitAfterAction()"
                  (input)="configStore.waitAfterAction.set(+$any($event.target).value)"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- Custom Login Toggle -->
        <div class="tgl-row" id="tgl-cl" (click)="configStore.useCustomLogin.set(!configStore.useCustomLogin())">
          <div class="tgl-info">
            <div class="tgl-icon">🔁</div>
            <div>
              <div class="tgl-title">Use Custom Login</div>
              <div class="tgl-sub">Override ENV_CONFIG default credentials</div>
            </div>
          </div>
          <label class="sw" (click)="$event.stopPropagation()">
            <input
              type="checkbox"
              id="use_custom_login"
              [checked]="configStore.useCustomLogin()"
              (change)="configStore.useCustomLogin.set(!configStore.useCustomLogin())"
            />
            <span class="sw-track"></span>
          </label>
        </div>

        <!-- Auditor 1 Credentials Card -->
        <div class="card" [style.display]="configStore.useCustomLogin() ? 'block' : 'none'">
          <div class="card-head">
            <div class="card-title">Auditor 1 Credentials</div>
          </div>
          <div class="card-body">
            <div class="g g2 g-last">
              <div class="fld">
                <label class="fld-lbl">Email <span class="req">*</span></label>
                <input
                  type="text"
                  id="email"
                  [value]="configStore.email()"
                  (input)="configStore.email.set($any($event.target).value)"
                />
              </div>
              <div class="fld">
                <label class="fld-lbl">Password <span class="req">*</span></label>
                <input
                  type="password"
                  id="password"
                  [value]="configStore.password()"
                  (input)="configStore.password.set($any($event.target).value)"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- Actions & Navigation Row -->
        <div class="nav-row">
          <div class="ji-actions">
            <label class="ji-btn ji-btn-import">
              <span class="ji-btn-icon">📥</span> Import JSON
              <input type="file" accept=".json" (change)="onJsonFileImport($event)" />
            </label>
            <button type="button" class="ji-btn ji-btn-export" (click)="exportJsonConfig()">
              <span class="ji-btn-icon">📤</span> Export JSON
            </button>
          </div>
          <button type="button" class="btn btn-accent btn-lg" (click)="goToExecution()">
            Go to Execution →
          </button>
        </div>
      </div>
    </div>

    <!-- JSON Import Summary Modal -->
    @if (showImportModal()) {
      <div class="ji-modal-overlay show" (click)="onOverlayClick($event)">
        <div class="ji-modal">
          <div class="ji-modal-head">
            <div class="ji-modal-title">Import Summary</div>
            <button type="button" class="ji-modal-close" (click)="showImportModal.set(false)">✕</button>
          </div>
          <div class="ji-modal-body">
            @if (importResult()?.errors?.length) {
              <div class="ji-section">
                <div class="ji-section-hd ji-section-err">❌ Errors ({{ importResult()!.errors.length }})</div>
                <div class="ji-list">
                  @for (err of importResult()!.errors; track err) {
                    <div class="ji-row ji-row-err">
                      <span class="ji-row-icon">✕</span>
                      <span class="ji-row-text">{{ err }}</span>
                    </div>
                  }
                </div>
              </div>
            }

            @if (importResult()?.populated?.length) {
              <div class="ji-section">
                <div class="ji-section-hd ji-section-ok">✅ Populated ({{ importResult()!.populated.length }})</div>
                <div class="ji-list">
                  @for (item of importResult()!.populated; track item.path) {
                    <div class="ji-row ji-row-ok">
                      <span class="ji-row-icon">✓</span>
                      <span class="ji-row-path">{{ item.path }}</span>
                      <span class="ji-row-arrow">→</span>
                      <span class="ji-row-val">{{ item.value }}</span>
                      <span class="ji-row-ctrl">#{{ item.controlId }}</span>
                    </div>
                  }
                </div>
              </div>
            }

            @if (importResult()?.skipped?.length) {
              <div class="ji-section">
                <div class="ji-section-hd ji-section-skip">⏭️ Skipped ({{ importResult()!.skipped.length }})</div>
                <div class="ji-list">
                  @for (item of importResult()!.skipped; track item.path) {
                    <div class="ji-row ji-row-skip">
                      <span class="ji-row-icon">–</span>
                      <span class="ji-row-path">{{ item.path }}</span>
                      <span class="ji-row-reason">{{ item.reason }}</span>
                    </div>
                  }
                </div>
              </div>
            }
          </div>
        </div>
      </div>
    }
  `
})
export class SetupComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);
  private readonly jsonImportService = inject(JsonImportService);

  readonly navigateTab = output<'execution'>();

  readonly showImportModal = signal<boolean>(false);
  readonly importResult = signal<ImportResult | null>(null);

  goToExecution(): void {
    this.navigateTab.emit('execution');
    window.dispatchEvent(new CustomEvent('navigate-tab', { detail: 'execution' }));
  }

  exportJsonConfig(): void {
    const cfg = this.configStore.buildRunConfig();
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(cfg, null, 2));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', dataStr);
    dlAnchor.setAttribute('download', 'qa_runner_config.json');
    dlAnchor.click();
  }

  onJsonFileImport(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || !input.files.length) return;
    const file = input.files[0];

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const res = this.jsonImportService.importJson(text);
      this.importResult.set(res);
      this.showImportModal.set(true);
      input.value = '';
    };
    reader.onerror = () => {
      this.importResult.set({
        success: false,
        populated: [],
        skipped: [],
        errors: ['Failed to read selected file.'],
        summary: ''
      });
      this.showImportModal.set(true);
      input.value = '';
    };
    reader.readAsText(file);
  }

  onOverlayClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('ji-modal-overlay')) {
      this.showImportModal.set(false);
    }
  }
}
