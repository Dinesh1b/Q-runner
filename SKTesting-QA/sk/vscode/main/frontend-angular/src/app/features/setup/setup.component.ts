import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RunConfigStore } from '../../state/run-config.store';
import { ModuleRegistryStore } from '../../state/module-registry.store';

@Component({
  selector: 'app-setup',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div style="padding: 28px 36px; max-width: 980px; margin: 0 auto;">
      <!-- Breadcrumb / Header Actions -->
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 24px;">
        <div>
          <div style="font-family:var(--font-mono); font-size:10px; color:var(--accent); letter-spacing:.14em; text-transform:uppercase;">
            Configuration
          </div>
          <h1 style="font-size:24px; font-weight:800; color:var(--t0); margin-top:2px;">
            Environment &amp; Engine Settings
          </h1>
        </div>

        <div style="display:flex; gap:10px;">
          <button type="button" class="btn btn-ghost" (click)="showImportModal.set(true)">
            📥 Import JSON
          </button>
          <button type="button" class="btn btn-ghost" (click)="exportJson()">
            📤 Export JSON
          </button>
        </div>
      </div>

      <!-- Environment & Login Card -->
      <div class="card" style="margin-bottom: 24px;">
        <div class="card-hd">
          <div class="card-title">
            <span class="card-icon">🌐</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Authentication &amp; Credentials</div>
              <div style="font-size:12px; color:var(--t3);">Configure target portal login credentials</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div style="display:flex; align-items:center; justify-content:space-between; padding:12px 16px; background:var(--glass-2); border-radius:var(--r); border:1px solid var(--glass-border); margin-bottom:18px;">
            <div>
              <div style="font-weight:600; font-size:13px; color:var(--t0);">Use Custom Login Credentials</div>
              <div style="font-size:11.5px; color:var(--t3);">Override backend default accounts with specific test credentials</div>
            </div>
            <label class="toggle-switch">
              <input
                type="checkbox"
                [checked]="configStore.useCustomLogin()"
                (change)="configStore.useCustomLogin.set(!configStore.useCustomLogin())"
              />
              <span class="toggle-slider"></span>
            </label>
          </div>

          @if (configStore.useCustomLogin()) {
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap:16px;">
              <div class="fld">
                <label class="fld-lbl">Auditor 1 Email <span class="req">*</span></label>
                <input
                  type="email"
                  [value]="configStore.email()"
                  (input)="configStore.email.set($any($event.target).value)"
                  placeholder="auditor1@company.com"
                />
              </div>

              <div class="fld">
                <label class="fld-lbl">Auditor 1 Password <span class="req">*</span></label>
                <input
                  type="password"
                  [value]="configStore.password()"
                  (input)="configStore.password.set($any($event.target).value)"
                  placeholder="••••••••"
                />
              </div>

              <div class="fld">
                <label class="fld-lbl">Company Name</label>
                <input
                  type="text"
                  [value]="configStore.companyName()"
                  (input)="configStore.companyName.set($any($event.target).value)"
                  placeholder="Demo Org"
                />
              </div>
            </div>
          }
        </div>
      </div>

      <!-- Browser & Execution Engine Card -->
      <div class="card" style="margin-bottom: 24px;">
        <div class="card-hd">
          <div class="card-title">
            <span class="card-icon">⚡</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Browser &amp; Timing Engine</div>
              <div style="font-size:12px; color:var(--t3);">Fine-tune Playwright browser driver and step intervals</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:16px; margin-bottom: 18px;">
            <div class="fld">
              <label class="fld-lbl">Browser Engine</label>
              <select
                style="background:var(--input-bg); border:1px solid var(--input-border); border-radius:10px; color:var(--t0); font-family:var(--font-mono); font-size:12px; padding:10px 13px; outline:none; width:100%;"
                [value]="configStore.browsername()"
                (change)="configStore.browsername.set($any($event.target).value)"
              >
                <option value="chrome">Google Chrome (Chromium)</option>
                <option value="firefox">Mozilla Firefox</option>
                <option value="edge">Microsoft Edge</option>
              </select>
            </div>

            <div class="fld">
              <label class="fld-lbl">Branch Code</label>
              <input
                type="text"
                [value]="configStore.branch()"
                (input)="configStore.branch.set($any($event.target).value)"
                placeholder="gr"
              />
            </div>
          </div>

          <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:16px;">
            <div class="fld">
              <label class="fld-lbl">Default Timeout (ms)</label>
              <input
                type="number"
                [value]="configStore.defaultTimeout()"
                (input)="configStore.defaultTimeout.set(+$any($event.target).value)"
              />
            </div>

            <div class="fld">
              <label class="fld-lbl">Short Timeout (ms)</label>
              <input
                type="number"
                [value]="configStore.shortTimeout()"
                (input)="configStore.shortTimeout.set(+$any($event.target).value)"
              />
            </div>

            <div class="fld">
              <label class="fld-lbl">Wait After Action (ms)</label>
              <input
                type="number"
                [value]="configStore.waitAfterAction()"
                (input)="configStore.waitAfterAction.set(+$any($event.target).value)"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- JSON Import Modal -->
    @if (showImportModal()) {
      <div style="position:fixed; inset:0; z-index:999; display:flex; align-items:center; justify-content:center; background:rgba(0,0,0,0.5); backdrop-filter:blur(10px);">
        <div class="card" style="width:100%; max-width:540px; margin:20px; box-shadow:var(--shadow-lg);">
          <div class="card-hd" style="display:flex; justify-content:space-between; align-items:center;">
            <div style="font-weight:700; font-size:16px; color:var(--t0);">Import Configuration JSON</div>
            <button type="button" class="btn-link" style="font-size:18px;" (click)="showImportModal.set(false)">✕</button>
          </div>

          <div class="card-body">
            @if (importError()) {
              <div class="alert alert-err" style="margin-bottom:12px;">
                <span class="alert-icon">⚠️</span>
                <div class="alert-body">{{ importError() }}</div>
              </div>
            }

            <div class="fld">
              <label class="fld-lbl">Paste Config JSON or Select File</label>
              <textarea
                style="width:100%; height:180px; background:var(--term-bg); color:#fff; font-family:var(--font-mono); font-size:11px; padding:12px; border-radius:10px; border:1px solid var(--term-border); outline:none; resize:none;"
                placeholder="{ &quot;DEFAULT_TIMEOUT&quot;: 10000, ... }"
                [value]="importJsonText()"
                (input)="importJsonText.set($any($event.target).value)"
              ></textarea>
            </div>

            <div style="margin-top:12px;">
              <input type="file" accept=".json" (change)="onFileSelected($event)" style="font-size:11px; color:var(--t2);" />
            </div>

            <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:20px;">
              <button type="button" class="btn btn-ghost" (click)="showImportModal.set(false)">Cancel</button>
              <button type="button" class="btn-primary" style="width:auto; padding:8px 22px;" (click)="applyImportJson()">
                Apply Configuration
              </button>
            </div>
          </div>
        </div>
      </div>
    }
  `
})
export class SetupComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);

  readonly showImportModal = signal<boolean>(false);
  readonly importJsonText = signal<string>('');
  readonly importError = signal<string | null>(null);

  exportJson(): void {
    const cfg = this.configStore.buildRunConfig();
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(cfg, null, 2));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', dataStr);
    dlAnchor.setAttribute('download', 'qa_runner_config.json');
    dlAnchor.click();
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      const file = input.files[0];
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result as string;
        this.importJsonText.set(text);
      };
      reader.readAsText(file);
    }
  }

  applyImportJson(): void {
    const text = this.importJsonText().trim();
    if (!text) {
      this.importError.set('Please provide JSON content');
      return;
    }

    try {
      const parsed = JSON.parse(text) as Record<string, unknown>;
      if (typeof parsed !== 'object' || parsed === null) {
        throw new Error('Root JSON must be an object');
      }

      if (parsed['DEFAULT_TIMEOUT']) this.configStore.defaultTimeout.set(Number(parsed['DEFAULT_TIMEOUT']));
      if (parsed['SHORT_TIMEOUT']) this.configStore.shortTimeout.set(Number(parsed['SHORT_TIMEOUT']));
      if (parsed['WAIT_AFTER_ACTION']) this.configStore.waitAfterAction.set(Number(parsed['WAIT_AFTER_ACTION']));
      if (parsed['browsername']) this.configStore.browsername.set(String(parsed['browsername']));
      if (parsed['environments']) this.configStore.environments.set(String(parsed['environments']));
      if (parsed['Branch']) this.configStore.branch.set(String(parsed['Branch']));
      if (parsed['USE_CUSTOM_LOGIN'] !== undefined) this.configStore.useCustomLogin.set(Boolean(parsed['USE_CUSTOM_LOGIN']));
      if (parsed['email']) this.configStore.email.set(String(parsed['email']));
      if (parsed['password']) this.configStore.password.set(String(parsed['password']));
      if (parsed['company_name']) this.configStore.companyName.set(String(parsed['company_name']));

      this.importError.set(null);
      this.showImportModal.set(false);
      this.importJsonText.set('');
    } catch (e: unknown) {
      this.importError.set((e as Error).message || 'Invalid JSON format');
    }
  }
}
