/**
 * run-session.model.ts
 * Type definitions for execution lifecycle, SSE stream events, and terminal output.
 */

export type RunStatus = 'idle' | 'running' | 'stopping' | 'completed' | 'failed' | 'stopped';

export type LogLevel = 'info' | 'warn' | 'error' | 'success' | 'debug' | 'step';

export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  module?: string;
  message: string;
  raw?: string;
}

export interface ProgressState {
  currentStep: number;
  totalSteps: number;
  percentage: number;
  currentModule?: string;
  elapsedSeconds: number;
  statusText?: string;
}

export interface RunHistoryItem {
  id: string;
  timestamp: string;
  status: RunStatus;
  durationSeconds: number;
  modulesCount: number;
  passedCount: number;
  failedCount: number;
}
