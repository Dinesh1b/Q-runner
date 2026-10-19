import { Component, inject, signal, OnInit, OnDestroy } from '@angular/core';
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
        [style.display]="activeTab() === 'run' ? 'none' : ''"
        [activeTab]="activeTab()"
        [selectedSetupStep]="setupStep()"
        (setupStepChange)="setupStep.set($event)"
      />

      <!-- ══ MAIN ══ -->
      <div class="main">
        <!-- Context Bar (matching index.html .ctx-bar) -->
        <div class="ctx-bar">
          <div class="ctx-crumb">
            <span id="ctx-mode-lbl">
              {{ activeTab() === 'setup' ? 'Setup' : activeTab() === 'execution' ? 'Execution' : 'Run' }}
            </span>
            <span class="ctx-sep">›</span>
            <span class="ctx-cur" id="ctx-step-lbl">
              @if (activeTab() === 'setup') {
                Environment &amp; Login
              } @else if (activeTab() === 'execution') {
                {{ getExecStepLabel() }}
              } @else {
                Launch &amp; Monitor
              }
            </span>
          </div>
          <div class="ctx-right" id="ctx-actions">
            @if (activeTab() === 'setup') {
              <button type="button" class="btn btn-ghost" (click)="activeTab.set('execution')">
                Execution →
              </button>
            } @else if (activeTab() === 'execution') {
              <button type="button" class="btn btn-ghost" (click)="activeTab.set('run')">
                Go to Run →
              </button>
            }
          </div>
        </div>

        <!-- ════════ SETUP TAB ════════ -->
        @if (activeTab() === 'setup') {
          <app-setup (navigateTab)="activeTab.set($event)" />
        }

        <!-- ════════ EXECUTION TAB ════════ -->
        @if (activeTab() === 'execution') {
          <app-execution />
        }

        <!-- ════════ RUN TAB ════════ -->
        @if (activeTab() === 'run') {
          <div id="content-run" style="display:flex; flex-direction:column; flex:1; overflow-y:auto;">
            <!-- Run Strip (Status bar) -->
            <div
              class="run-strip"
              id="run-strip"
              [style.display]="sessionStore.isRunning() || sessionStore.runId() ? 'flex' : 'none'"
            >
              <div class="run-meta">
                <div class="run-meta-lbl">Run ID</div>
                <div class="run-meta-val" id="run-id-disp">{{ sessionStore.runId() || '—' }}</div>
              </div>
              <div class="run-sep"></div>
              <div class="run-meta">
                <div class="run-meta-lbl">Environment</div>
                <div class="run-meta-val" id="run-env-disp">{{ configStore.environments() }}</div>
              </div>
              <div class="run-sep"></div>
              <div class="run-meta">
                <div class="run-meta-lbl">Elapsed</div>
                <div class="run-meta-val" id="run-elapsed-inner">{{ sessionStore.formattedElapsed() }}</div>
              </div>
              <div class="run-ctrl">
                @if (sessionStore.isRunning()) {
                  <button type="button" class="btn btn-rose" id="run-stop-btn" (click)="sessionStore.stopRun()">
                    ◼ Stop
                  </button>
                }
                @if (!sessionStore.isActive() && sessionStore.runId()) {
                  <button type="button" class="btn btn-violet" id="run-rerun-btn" [disabled]="queueStore.queueCount() === 0" (click)="sessionStore.startRun()">
                    ↺ Re-run
                  </button>
                }
              </div>
            </div>

            <!-- Run Main Area -->
            <div class="run-area">
              <!-- Run Queue Card -->
              <div class="card" style="margin-bottom:14px;">
                <div class="card-head">
                  <div class="card-title">Run Queue</div>
                  <span class="queue-hint"><span class="queue-hint-dot"></span>Drag ⠿ to reorder priority</span>
                </div>
                <div class="card-body" style="padding-bottom:14px;">
                  <div id="run-queue-list">
                    @if (queueStore.queueCount() === 0) {
                      <div id="rqempty-all" class="rq-empty">
                        <div class="rq-empty-icon">🔬</div>
                        <div class="rq-empty-title">No modules enabled</div>
                        <div class="rq-empty-hint">Enable modules in <strong>Execution</strong> to queue them here</div>
                      </div>
                    } @else {
                      <div
                        cdkDropList
                        (cdkDropListDropped)="onQueueDrop($event)"
                        style="display:flex; flex-direction:column; gap:7px;"
                      >
                        @for (mod of queueStore.queuedModules(); track mod.idx; let i = $index) {
                          <div class="q-item" cdkDrag>
                            <div class="q-handle" cdkDragHandle style="cursor:grab; color:var(--t4); font-size:12px;">⠿</div>
                            <div style="font-family:var(--font-mono); font-size:9px; font-weight:500; color:var(--accent); width:22px; text-align:center;">
                              {{ i + 1 }}
                            </div>
                            <div style="min-width:0; flex:1;">
                              <div style="font-size:13px; font-weight:600; color:var(--t0); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                                {{ mod.icon }} {{ mod.display }}
                              </div>
                              <div style="font-family:var(--font-mono); font-size:9px; color:var(--t4);">
                                {{ mod.session }}
                              </div>
                            </div>
                            <div
                              style="font-family:var(--font-mono); font-size:8px; padding:3px 8px; border-radius:6px; white-space:nowrap;"
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
                </div>
              </div>

              <!-- Big Run / Stop Action Button -->
              @if (!sessionStore.isRunning()) {
                <button
                  type="button"
                  class="run-big-btn"
                  id="run-now-btn"
                  [disabled]="queueStore.queueCount() === 0 || sessionStore.isActive()"
                  (click)="sessionStore.startRun()"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                    <polygon points="5 3 19 12 5 21" />
                  </svg>
                  RUN NOW
                </button>
              } @else {
                <button
                  type="button"
                  class="run-big-btn"
                  style="background:linear-gradient(135deg,#fb7185,#f43f5e,#e11d48); box-shadow:0 6px 24px var(--rose-glow);"
                  (click)="sessionStore.stopRun()"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="4" y="4" width="16" height="16" rx="2" />
                  </svg>
                  STOP RUN
                </button>
              }

              <!-- Progress Card -->
              @if (sessionStore.isRunning() || sessionStore.runId()) {
                <div class="prog-card" id="run-prog-card">
                  <div class="prog-row">
                    <div class="prog-label" id="run-prog-label">{{ sessionStore.currentStepText() }}</div>
                    <div class="prog-pct" id="run-pct-big">{{ sessionStore.progress() }}%</div>
                  </div>
                  <div class="prog-track">
                    <div
                      class="prog-fill"
                      id="run-fill"
                      [style.width.%]="sessionStore.progress()"
                      [style.background]="sessionStore.status() === 'completed' ? 'var(--emerald)' : sessionStore.status() === 'failed' ? 'var(--rose)' : 'var(--accent-btn)'"
                    ></div>
                  </div>
                  <div class="prog-sub">
                    <div class="prog-sub-dot" id="run-sub-dot" [style.opacity]="sessionStore.isRunning() ? '1' : '0'"></div>
                    <span id="run-sub-text">
                      {{ sessionStore.status().toUpperCase() }} · {{ sessionStore.formattedElapsed() }}
                    </span>
                  </div>
                </div>
              }

              <!-- Terminal Window (Mac style) -->
              <div class="terminal">
                <div class="term-bar">
                  <div class="term-dots">
                    <div class="tdot td-r"></div>
                    <div class="tdot td-y"></div>
                    <div class="tdot td-g"></div>
                  </div>
                  <div class="term-title">
                    <span class="term-live-dot" id="run-live-dot" [class.live]="sessionStore.isRunning()"></span>
                    <span id="run-term-lbl">Output Log</span>
                  </div>
                  <div class="term-actions">
                    <button
                      type="button"
                      class="tbtn"
                      id="run-as-btn"
                      [class.active]="sessionStore.autoScroll()"
                      (click)="sessionStore.toggleAutoScroll()"
                    >
                      {{ sessionStore.autoScroll() ? '↓ Auto ON' : '↓ Auto' }}
                    </button>
                    <button type="button" class="tbtn" (click)="copyLogs()">📋 Copy</button>
                    <button type="button" class="tbtn" (click)="saveLogs()">⬇ Save</button>
                    <button type="button" class="tbtn" (click)="sessionStore.clearSession()">✕ Clear</button>
                  </div>
                </div>

                <div class="term-body tall" id="run-terminal">
                  @if (sessionStore.logs().length === 0) {
                    <span class="log l-skip">
                      <span class="msg">// Ready — press RUN NOW to start</span>
                    </span>
                  } @else {
                    @for (entry of sessionStore.logs(); track entry.id) {
                      <span [class]="'log ' + getLogCssClass(entry.level)">
                        <span class="ts">{{ entry.timestamp }}</span>
                        <span class="msg">{{ entry.message }}</span>
                      </span>
                      <br />
                    }
                  }
                  @if (sessionStore.isRunning()) {
                    <span class="term-cursor"></span>
                  }
                </div>

                <div class="term-stats-bar">
                  <span class="ts-item"><span class="ts-ok">●</span>&nbsp;<span id="ts-ok-count">{{ sessionStore.logOkCount() }}</span>&nbsp;ok</span>
                  <span class="ts-item"><span class="ts-err">●</span>&nbsp;<span id="ts-err-count">{{ sessionStore.logErrCount() }}</span>&nbsp;err</span>
                  <span class="ts-item"><span class="ts-warn">●</span>&nbsp;<span id="ts-warn-count">{{ sessionStore.logWarnCount() }}</span>&nbsp;warn</span>
                  <span class="ts-lines" id="ts-lines">{{ sessionStore.logs().length }} lines</span>
                </div>

                @if (sessionStore.errorMessage()) {
                  <div class="err-surface" id="run-err-surface" style="display:flex;">
                    <div class="err-icon">⛔</div>
                    <div class="err-msg" id="run-err-msg">{{ sessionStore.errorMessage() }}</div>
                    <div class="err-acts">
                      @if (sessionStore.isRunning()) {
                        <button type="button" class="btn btn-rose" style="font-size:8.5px; padding:5px 12px;" (click)="sessionStore.stopRun()">
                          ✕ Stop
                        </button>
                      }
                      <button type="button" class="btn btn-ghost" style="font-size:8.5px; padding:5px 12px;" [disabled]="queueStore.queueCount() === 0 || sessionStore.isActive()" (click)="sessionStore.startRun()">
                        ↺ Re-run
                      </button>
                    </div>
                  </div>
                }
              </div>

              <!-- Bottom Return Button -->
              <div style="margin-top:12px; margin-bottom: 24px;">
                <button type="button" class="btn btn-back" (click)="activeTab.set('execution')">
                   Back to Execution
                </button>
              </div>
            </div>
          </div>
        }
      </div>
    </div>
  `
})
export class ShellComponent implements OnInit, OnDestroy {
  readonly registryStore = inject(ModuleRegistryStore);
  readonly queueStore = inject(QueueStore);
  readonly sessionStore = inject(RunSessionStore);
  readonly configStore = inject(RunConfigStore);

  readonly activeTab = signal<MainTab>('setup');
  readonly setupStep = signal<number>(0);

  private readonly onNavigateTab = (e: Event): void => {
    const customEvent = e as CustomEvent<MainTab>;
    if (customEvent.detail) {
      this.activeTab.set(customEvent.detail);
    }
  };

  ngOnInit(): void {
    this.registryStore.loadModules();
    window.addEventListener('navigate-tab', this.onNavigateTab);
  }

  ngOnDestroy(): void {
    window.removeEventListener('navigate-tab', this.onNavigateTab);
  }

  getExecStepLabel(): string {
    const idx = this.registryStore.selectedModuleIdx();
    if (idx === null) return 'Select a module';
    const mod = this.registryStore.modules().find(m => m.idx === idx);
    return mod ? mod.display : 'Module';
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
