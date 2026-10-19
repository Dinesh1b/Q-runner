import { Injectable, inject, signal, computed, OnDestroy } from '@angular/core';
import { Subscription } from 'rxjs';
import { RunnerService } from '../core/services/runner.service';
import { RunConfigStore } from './run-config.store';
import { LogEntry, LogLevel, RunStatus } from '../core/models/run-session.model';

@Injectable({
  providedIn: 'root'
})
export class RunSessionStore implements OnDestroy {
  private readonly runnerService = inject(RunnerService);
  private readonly configStore = inject(RunConfigStore);

  readonly status = signal<RunStatus>('idle');
  readonly runId = signal<string | null>(null);
  readonly logs = signal<LogEntry[]>([]);
  readonly logOkCount = signal<number>(0);
  readonly logErrCount = signal<number>(0);
  readonly logWarnCount = signal<number>(0);
  readonly progress = signal<number>(0);
  readonly currentStepText = signal<string>('Ready');
  readonly elapsedSeconds = signal<number>(0);
  readonly autoScroll = signal<boolean>(true);
  readonly errorMessage = signal<string | null>(null);

  private timerInterval: ReturnType<typeof setInterval> | null = null;
  private streamSub: Subscription | null = null;

  readonly formattedElapsed = computed(() => {
    const s = this.elapsedSeconds();
    const hrs = Math.floor(s / 3600);
    const mins = Math.floor((s % 3600) / 60);
    const secs = s % 60;
    return [hrs, mins, secs].map(v => String(v).padStart(2, '0')).join(':');
  });

  readonly isRunning = computed(() => this.status() === 'running');
  /** Running or still stopping — a run is in flight and a new one must not start. */
  readonly isActive = computed(() => this.status() === 'running' || this.status() === 'stopping');

  startRun(): void {
    if (this.isActive()) return;

    this.resetSession();
    this.status.set('running');
    this.currentStepText.set('Initializing...');
    this.startTimer();

    const cfg = this.configStore.buildRunConfig();

    this.runnerService.startRun(cfg).subscribe({
      next: (res) => {
        this.runId.set(res.run_id);
        this.appendLog(`[INFO] Run started with ID #${res.run_id} (${res.total} modules queued)`, 'info');
        this.connectStream();
      },
      error: (err) => {
        this.status.set('failed');
        this.stopTimer();
        const msg = err.error?.error || err.message || 'Failed to start run';
        this.errorMessage.set(msg);
        this.appendLog(`[ERROR] ${msg}`, 'error');
      }
    });
  }

  stopRun(): void {
    if (!this.isRunning()) return;
    this.status.set('stopping');
    this.appendLog('[WARN] Stop requested by user...', 'warn');

    this.runnerService.stopRun().subscribe({
      next: () => this.finishRun('stopped'),
      error: () => this.finishRun('stopped')
    });
  }

  private connectStream(): void {
    this.streamSub?.unsubscribe();

    this.streamSub = this.runnerService.getLogStream().subscribe({
      next: (line) => {
        this.handleStreamLine(line);
      },
      error: () => this.handleStreamLost(),
      // The stream ends normally only after __DONE__/__ERROR__, which finish the run first.
      complete: () => this.handleStreamLost()
    });
  }

  private handleStreamLost(): void {
    if (this.status() === 'stopping') {
      this.finishRun('stopped');
    } else if (this.isRunning()) {
      this.errorMessage.set('Lost connection to the run log stream');
      this.appendLog('[ERROR] Lost connection to the run log stream — check that the backend is still running', 'error');
      this.finishRun('failed');
    }
  }

  private handleStreamLine(line: string): void {
    if (!line) return;

    if (line === '__DONE__') {
      this.finishRun('completed');
      return;
    }
    if (line === '__ERROR__') {
      this.finishRun(this.status() === 'stopping' ? 'stopped' : 'failed');
      return;
    }

    // Check for JSON progress message
    if (line.startsWith('{') && line.endsWith('}')) {
      try {
        const obj = JSON.parse(line);
        if (obj.type === 'progress') {
          if (obj.progress !== undefined) this.progress.set(obj.progress);
          if (obj.step) this.currentStepText.set(obj.step);
          return;
        }
        if (obj.type === 'init') {
          const names: string[] = Array.isArray(obj.modules) ? obj.modules : [];
          this.appendLog(`[INFO] Modules to run (${names.length}): ${names.join(', ')}`, 'info');
          return;
        }
      } catch {
        // Not a JSON progress packet, proceed to plain log
      }
    }

    // Classify log line
    const level = this.classifyLogLevel(line);
    this.appendLog(line, level);

    // Single-process runs report the current module as "Running module index: N (Name)"
    const moduleMatch = line.match(/^Running module index: \d+ \((.*)\)/);
    if (moduleMatch) {
      this.currentStepText.set(moduleMatch[1]);
    }

    // If step is indicated in text, e.g. [STEP] Running Module 2...
    if (line.includes('[STEP]')) {
      const stepMatch = line.match(/\[STEP\]\s*(.*)/i);
      if (stepMatch && stepMatch[1]) {
        this.currentStepText.set(stepMatch[1].trim());
      }
    }
  }

  private classifyLogLevel(text: string): LogLevel {
    const l = text.toLowerCase();
    if (l.includes('[success]') || l.includes('[pass]') || l.includes('[ok]')) return 'success';
    if (l.includes('[error]') || l.includes('[fail]') || l.includes('exception') || l.includes('traceback')) return 'error';
    if (l.includes('[warn]') || l.includes('warning')) return 'warn';
    if (l.includes('[step]')) return 'step';
    if (l.includes('[debug]')) return 'debug';
    return 'info';
  }

  appendLog(message: string, level: LogLevel = 'info'): void {
    const now = new Date();
    const timestamp = now.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });

    const entry: LogEntry = {
      id: Math.random().toString(36).substring(2, 9),
      timestamp,
      level,
      message
    };

    if (level === 'success') this.logOkCount.update(c => c + 1);
    else if (level === 'error') this.logErrCount.update(c => c + 1);
    else if (level === 'warn') this.logWarnCount.update(c => c + 1);

    this.logs.update(list => [...list, entry]);
  }

  private finishRun(finalStatus: RunStatus): void {
    // A run finishes exactly once (stream marker, stream loss and /stop response can all race).
    if (!this.isActive()) return;
    this.stopTimer();
    this.streamSub?.unsubscribe();
    this.streamSub = null;
    this.status.set(finalStatus);

    if (finalStatus === 'completed') {
      this.progress.set(100);
      this.currentStepText.set('All modules completed');
      this.appendLog('[SUCCESS] Run completed successfully', 'success');
    } else if (finalStatus === 'failed') {
      this.currentStepText.set('Run failed');
      this.appendLog('[ERROR] Run execution finished with errors', 'error');
    } else if (finalStatus === 'stopped') {
      this.currentStepText.set('Run stopped');
      this.appendLog('[WARN] Run stopped by user', 'warn');
    }
  }

  private startTimer(): void {
    this.stopTimer();
    this.elapsedSeconds.set(0);
    this.timerInterval = setInterval(() => {
      this.elapsedSeconds.update(s => s + 1);
    }, 1000);
  }

  private stopTimer(): void {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
  }

  /**
   * "Clear" button: always clears the terminal. While a run is in flight the stream,
   * timer and status are kept so the run can still finish and be stopped.
   */
  clearSession(): void {
    if (this.isActive()) {
      this.clearLogs();
      return;
    }
    this.resetSession();
  }

  private resetSession(): void {
    this.stopTimer();
    this.streamSub?.unsubscribe();
    this.streamSub = null;
    this.clearLogs();
    this.progress.set(0);
    this.elapsedSeconds.set(0);
    this.errorMessage.set(null);
  }

  private clearLogs(): void {
    this.logs.set([]);
    this.logOkCount.set(0);
    this.logErrCount.set(0);
    this.logWarnCount.set(0);
    this.progress.set(0);
    this.elapsedSeconds.set(0);
    this.errorMessage.set(null);
  }

  toggleAutoScroll(): void {
    this.autoScroll.update(v => !v);
  }

  ngOnDestroy(): void {
    this.stopTimer();
    this.streamSub?.unsubscribe();
  }
}
