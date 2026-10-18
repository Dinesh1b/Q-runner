import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NavComponent, MainTab } from '../../shared/components/nav/nav.component';
import { SidebarComponent } from '../../shared/components/sidebar/sidebar.component';
import { SetupComponent } from '../setup/setup.component';
import { ExecutionComponent } from '../execution/execution.component';
import { ModuleRegistryStore } from '../../state/module-registry.store';
import { QueueStore } from '../../state/queue.store';
import { RunSessionStore } from '../../state/run-session.store';
import { RunConfigStore } from '../../state/run-config.store';
import { CdkDragDrop, DragDropModule } from '@angular/cdk/drag-drop';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [
    CommonModule,
    DragDropModule,
    NavComponent,
    SidebarComponent,
    SetupComponent,
    ExecutionComponent,
  ],
  template: `
    <div class="bg-mesh"></div>
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>

    <app-nav
      [activeTab]="activeTab()"
      (tabChange)="activeTab.set($event)"
    />

    <div class="layout">
      <app-sidebar
        [activeTab]="activeTab()"
        [selectedSetupStep]="setupStep()"
        (setupStepChange)="setupStep.set($event)"
      />

      <main class="main">
        <!-- ════════ SETUP TAB ════════ -->
        @if (activeTab() === 'setup') {
          <app-setup />
        }

        <!-- ════════ EXECUTION TAB ════════ -->
        @if (activeTab() === 'execution') {
          <app-execution style="display:flex; flex:1; overflow:hidden;" />
        }

        <!-- ════════ RUN TAB ════════ -->
        @if (activeTab() === 'run') {
          <div style="display:flex; flex:1; overflow:hidden;">
            <!-- Left: Run Queue + Controls -->
            <div style="width:340px; border-right:1px solid var(--glass-border-dim); display:flex; flex-direction:column; overflow:hidden;">
              <!-- Run Queue Header -->
              <div style="padding:16px 18px 12px; border-bottom:1px solid var(--glass-border-dim);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <div>
                    <div style="font-weight:700; font-size:15px; color:var(--t0);">Run Queue</div>
                    <div style="font-size:11px; color:var(--t3);">Drag to reorder execution priority</div>
                  </div>
                  <div style="font-family:var(--font-mono); font-size:11px; color:var(--accent);">
                    {{ queueStore.queueCount() }} modules
                  </div>
                </div>
              </div>

              <!-- Queue List (CDK Drag-Drop) -->
              <div style="flex:1; overflow-y:auto; padding:10px;">
                @if (queueStore.queueCount() === 0) {
                  <div style="padding:40px 20px; text-align:center;">
                    <div style="font-size:40px; opacity:0.3; margin-bottom:12px;">📭</div>
                    <div style="font-size:13px; color:var(--t3);">No modules enabled</div>
                    <div style="font-size:11px; color:var(--t4); margin-top:4px;">
                      Enable modules in the Execution tab to populate the queue
                    </div>
                  </div>
                } @else {
                  <div
                    cdkDropList
                    id="run-queue-list"
                    (cdkDropListDropped)="onQueueDrop($event)"
                    style="display:flex; flex-direction:column; gap:7px;"
                  >
                    @for (mod of queueStore.queuedModules(); track mod.idx; let i = $index) {
                      <div class="q-item" cdkDrag>
                        <!-- Drag Handle -->
                        <div class="q-handle" cdkDragHandle style="cursor:grab; color:var(--t4); font-size:12px;">⠿</div>

                        <!-- Priority Badge -->
                        <div style="font-family:var(--font-mono); font-size:9px; font-weight:500; color:var(--accent); width:22px; text-align:center;">
                          {{ i + 1 }}
                        </div>

                        <!-- Body -->
                        <div style="min-width:0;">
                          <div style="font-size:13px; font-weight:600; color:var(--t0); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                            {{ mod.icon }} {{ mod.display }}
                          </div>
                          <div style="font-family:var(--font-mono); font-size:9px; color:var(--t4);">
                            {{ mod.session }}
                          </div>
                        </div>

                        <!-- Session chip -->
                        <div style="font-family:var(--font-mono); font-size:8px; padding:3px 8px; border-radius:6px; white-space:nowrap;"
                          [style.background]="mod.session === 'auditor2' ? 'var(--violet-soft)' : 'var(--sky-soft)'"
                          [style.color]="mod.session === 'auditor2' ? 'var(--violet)' : 'var(--sky)'"
                        >
                          {{ mod.session === 'auditor2' ? 'A2' : 'A1' }}
                        </div>
                      </div>
                    }
                  </div>
                }
              </div>

              <!-- Run / Stop Actions -->
              <div style="padding:14px 18px; border-top:1px solid var(--glass-border-dim); background:var(--glass-4);">
                @if (!sessionStore.isRunning()) {
                  <button
                    type="button"
                    class="btn-primary"
                    [disabled]="queueStore.queueCount() === 0"
                    (click)="sessionStore.startRun()"
                    style="width:100%;"
                  >
                    ▶ Start Run ({{ queueStore.queueCount() }} modules)
                  </button>
                } @else {
                  <button
                    type="button"
                    class="btn-primary"
                    style="width:100%; background:linear-gradient(135deg,#fb7185,#f43f5e,#e11d48); box-shadow:0 6px 24px var(--rose-glow);"
                    (click)="sessionStore.stopRun()"
                  >
                    ⏹ Stop Run
                  </button>
                }
              </div>
            </div>

            <!-- Right: Terminal + Progress -->
            <div style="flex:1; display:flex; flex-direction:column; overflow:hidden;">
              <!-- Progress Strip -->
              <div style="padding:16px 24px; border-bottom:1px solid var(--glass-border-dim);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                  <div style="display:flex; align-items:center; gap:12px;">
                    @if (sessionStore.runId()) {
                      <span style="font-family:var(--font-mono); font-size:10px; color:var(--t3);">
                        Run #{{ sessionStore.runId() }}
                      </span>
                    }
                    <span style="font-family:var(--font-mono); font-size:11px; font-weight:600;"
                      [style.color]="sessionStore.status() === 'completed' ? 'var(--emerald)' : sessionStore.status() === 'failed' ? 'var(--rose)' : 'var(--accent)'"
                    >
                      {{ sessionStore.status().toUpperCase() }}
                    </span>
                  </div>
                  <div style="font-family:var(--font-mono); font-size:12px; color:var(--t2);">
                    {{ sessionStore.progress() }}%
                  </div>
                </div>

                <!-- Progress bar -->
                <div style="height:5px; width:100%; background:var(--glass-border-dim); border-radius:3px; overflow:hidden;">
                  <div
                    style="height:100%; border-radius:3px; transition:width 0.4s cubic-bezier(0.4,0,0.2,1);"
                    [style.width.%]="sessionStore.progress()"
                    [style.background]="sessionStore.status() === 'completed' ? 'var(--emerald)' : sessionStore.status() === 'failed' ? 'var(--rose)' : 'var(--accent-btn)'"
                  ></div>
                </div>

                <div style="margin-top:6px; font-size:12px; color:var(--t3);">
                  {{ sessionStore.currentStepText() }}
                </div>
              </div>

              <!-- Terminal Stats Bar -->
              <div style="display:flex; align-items:center; gap:16px; padding:8px 24px; border-bottom:1px solid var(--glass-border-dim); font-family:var(--font-mono); font-size:10px;">
                <span style="color:var(--emerald);">✓ {{ sessionStore.logOkCount() }}</span>
                <span style="color:var(--rose);">✕ {{ sessionStore.logErrCount() }}</span>
                <span style="color:var(--amber);">⚠ {{ sessionStore.logWarnCount() }}</span>
                <span style="color:var(--t4);">⏱ {{ sessionStore.formattedElapsed() }}</span>
                <span style="color:var(--t4); margin-left:auto;">{{ sessionStore.logs().length }} lines</span>

                <div style="display:flex; gap:10px; align-items:center; border-left:1px solid var(--glass-border-dim); padding-left:12px;">
                  <button
                    type="button"
                    class="btn-link"
                    style="font-size:10px; cursor:pointer;"
                    [style.color]="sessionStore.autoScroll() ? 'var(--accent)' : 'var(--t4)'"
                    (click)="sessionStore.toggleAutoScroll()"
                  >
                    ↓ Auto
                  </button>
                  <button
                    type="button"
                    class="btn-link"
                    style="font-size:10px; cursor:pointer;"
                    (click)="copyLogs()"
                  >
                    📋 Copy
                  </button>
                  <button
                    type="button"
                    class="btn-link"
                    style="font-size:10px; cursor:pointer;"
                    (click)="saveLogs()"
                  >
                    ⬇ Save
                  </button>
                  <button
                    type="button"
                    class="btn-link"
                    style="font-size:10px; color:var(--rose); cursor:pointer;"
                    (click)="sessionStore.clearSession()"
                  >
                    ✕ Clear
                  </button>
                </div>
              </div>

              <!-- Terminal Output -->
              <div
                id="run-terminal"
                style="flex:1; overflow-y:auto; background:var(--term-bg); padding:16px; font-family:var(--font-mono); font-size:11px; line-height:1.65;"
              >
                @if (sessionStore.logs().length === 0) {
                  <div style="color:rgba(255,255,255,0.15); text-align:center; padding-top:60px;">
                    <div style="font-size:32px; margin-bottom:10px;">⌨</div>
                    Terminal output will appear here when a run starts
                  </div>
                } @else {
                  @for (entry of sessionStore.logs(); track entry.id) {
                    <span
                      [class]="'log ' + getLogCssClass(entry.level)"
                    >
                      <span class="ts">{{ entry.timestamp }}</span>
                      <span class="msg">{{ entry.message }}</span>
                    </span>
                    <br>
                  }
                }
                @if (sessionStore.isRunning()) {
                  <span class="term-cursor"></span>
                }
              </div>
            </div>
          </div>
        }
      </main>
    </div>
  `
})
export class ShellComponent implements OnInit {
  readonly registryStore = inject(ModuleRegistryStore);
  readonly queueStore = inject(QueueStore);
  readonly sessionStore = inject(RunSessionStore);
  readonly configStore = inject(RunConfigStore);

  readonly activeTab = signal<MainTab>('setup');
  readonly setupStep = signal<number>(0);

  ngOnInit(): void {
    this.registryStore.loadModules();
    window.addEventListener('navigate-tab', (e: Event) => {
      const customEvent = e as CustomEvent<MainTab>;
      if (customEvent.detail) {
        this.activeTab.set(customEvent.detail);
      }
    });
  }

  onQueueDrop(event: CdkDragDrop<unknown>): void {
    this.queueStore.reorder(event.previousIndex, event.currentIndex);
  }

  getLogCssClass(level: string): string {
    switch (level) {
      case 'success': return 'l-ok';
      case 'error': return 'l-err';
      case 'warn': return 'l-warn';
      case 'step': return 'l-info';
      case 'debug': return 'l-plain';
      default: return 'l-plain';
    }
  }

  copyLogs(): void {
    const text = this.sessionStore.logs().map(l => `[${l.timestamp}] ${l.message}`).join('\n');
    navigator.clipboard.writeText(text);
  }

  saveLogs(): void {
    const text = this.sessionStore.logs().map(l => `[${l.timestamp}] ${l.message}`).join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `run-log-${this.sessionStore.runId() || 'output'}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }
}
