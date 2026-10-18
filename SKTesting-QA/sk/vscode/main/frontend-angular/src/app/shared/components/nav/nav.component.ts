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
        @for (env of environments; track env.value) {
          <button
            type="button"
            class="env-btn"
            [id]="'envbtn-' + env.value"
            [class.active]="configStore.environments() === env.value"
            (click)="configStore.environments.set(env.value)"
          >
            {{ env.label }}
          </button>
        }
      </div>

      <!-- Right Cluster -->
      <div class="nav-right">
        <!-- Theme Toggle -->
        <div class="theme-btn">
          <button
            type="button"
            class="theme-seg"
            id="tt-light"
            [class.active]="themeService.currentTheme() === 'light'"
            (click)="themeService.setTheme('light')"
          >
            <span class="theme-icon">☀️</span> Light
          </button>
          <button
            type="button"
            class="theme-seg"
            id="tt-dark"
            [class.active]="themeService.currentTheme() === 'dark'"
            (click)="themeService.setTheme('dark')"
          >
            <span class="theme-icon">🌙</span> Dark
          </button>
        </div>

        <!-- Elapsed Badge -->
        <div class="elapsed-badge" id="elapsedBadge" [class.running]="sessionStore.isRunning()">
          {{ sessionStore.formattedElapsed() }}
        </div>

        <!-- Status Pill -->
        <div
          class="status-pill"
          id="statusPill"
          [class.running]="sessionStore.status() === 'running'"
          [class.done]="sessionStore.status() === 'completed'"
          [class.err]="sessionStore.status() === 'failed'"
        >
          <span class="s-dot"></span>
          <span class="s-lbl" id="statusTxt">{{ sessionStore.status().toUpperCase() }}</span>
        </div>

        <!-- Logout Button -->
        <button
          type="button"
          id="logout-btn"
          (click)="authService.logout().subscribe()"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          Logout
        </button>
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

  readonly environments = [
    { value: 'DEV', label: 'DEV' },
    { value: 'QA', label: 'QA' },
    { value: 'STAGING', label: 'STG' },
    { value: 'PRODUCTION', label: 'PROD' }
  ];
}
