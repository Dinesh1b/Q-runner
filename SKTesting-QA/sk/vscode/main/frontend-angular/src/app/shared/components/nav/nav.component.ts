import { Component, inject, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ThemeService } from '../../../core/services/theme.service';
import { AuthService } from '../../../core/services/auth.service';
import { RunConfigStore } from '../../../state/run-config.store';
import { RunSessionStore } from '../../../state/run-session.store';

export type MainTab = 'setup' | 'execution' | 'run';

@Component({
  selector: 'app-nav',
  standalone: true,
  imports: [CommonModule],
  template: `
    <nav class="nav">
      <!-- Logo -->
      <div class="logo">
        <div class="logo-gem">QA</div>
        <div class="logo-wrap">
          <div class="logo-name">Q<em>-</em>A Runner</div>
          <div class="logo-sub">Automation Suite</div>
        </div>
      </div>

      <!-- Main Navigation Tabs -->
      <div class="nav-tabs">
        <button
          type="button"
          class="nav-tab"
          [class.active]="activeTab() === 'setup'"
          (click)="tabChange.emit('setup')"
        >
          Setup
        </button>
        <button
          type="button"
          class="nav-tab"
          [class.active]="activeTab() === 'execution'"
          (click)="tabChange.emit('execution')"
        >
          Execution
        </button>
        <button
          type="button"
          class="nav-tab"
          [class.active]="activeTab() === 'run'"
          (click)="tabChange.emit('run')"
        >
          Run
        </button>
      </div>

      <div class="nav-div"></div>

      <!-- Environment Selector -->
      <div class="env-row">
        @for (env of environments; track env) {
          <button
            type="button"
            class="env-btn"
            [class.active]="configStore.environments() === env"
            (click)="configStore.environments.set(env)"
          >
            {{ env }}
          </button>
        }
      </div>

      <!-- Right Cluster -->
      <div class="nav-right">
        <!-- Theme Toggle -->
        <div class="theme-btn" (click)="themeService.toggleTheme()">
          <button
            type="button"
            class="theme-seg"
            [class.active]="themeService.currentTheme() === 'light'"
          >
            <span>☀️</span> Light
          </button>
          <button
            type="button"
            class="theme-seg"
            [class.active]="themeService.currentTheme() === 'dark'"
          >
            <span>🌙</span> Dark
          </button>
        </div>

        <!-- Elapsed Badge -->
        <div class="elapsed-badge" [class.running]="sessionStore.isRunning()">
          {{ sessionStore.formattedElapsed() }}
        </div>

        <!-- Status Pill -->
        <div
          class="status-pill"
          [class.running]="sessionStore.status() === 'running'"
          [class.done]="sessionStore.status() === 'completed'"
          [class.err]="sessionStore.status() === 'failed'"
        >
          <span class="s-dot"></span>
          <span class="s-lbl">{{ sessionStore.status().toUpperCase() }}</span>
        </div>

        <!-- Logout Button -->
        @if (!authService.skipAuth()) {
          <button
            type="button"
            id="logout-btn"
            style="display:flex; align-items:center; gap:6px; background:var(--glass-2); border:1px solid var(--glass-border-dim); padding:6px 14px; border-radius:10px; cursor:pointer; font-family:var(--font-mono); font-size:10px; color:var(--t2); font-weight:500;"
            (click)="authService.logout().subscribe()"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            Logout
          </button>
        }
      </div>
    </nav>
  `
})
export class NavComponent {
  readonly themeService = inject(ThemeService);
  readonly authService = inject(AuthService);
  readonly configStore = inject(RunConfigStore);
  readonly sessionStore = inject(RunSessionStore);

  readonly activeTab = input<MainTab>('setup');
  readonly tabChange = output<MainTab>();

  readonly environments = ['DEV', 'QA', 'STAGING', 'PRODUCTION'];
}
