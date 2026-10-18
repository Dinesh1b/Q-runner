import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { RunConfig } from '../models/run-config.model';

export interface StartRunResponse {
  status: string;
  run_id: string;
  total: number;
  error?: string;
}

export interface StopRunResponse {
  status: string;
}

@Injectable({
  providedIn: 'root'
})
export class RunnerService {
  private readonly http = inject(HttpClient);

  startRun(config: RunConfig): Observable<StartRunResponse> {
    return this.http.post<StartRunResponse>('/run', config);
  }

  stopRun(): Observable<StopRunResponse> {
    return this.http.post<StopRunResponse>('/stop', {});
  }

  getHistory(): Observable<unknown[]> {
    return this.http.get<unknown[]>('/history');
  }

  /**
   * Connect to the Server-Sent Events stream for live runner logs
   */
  getLogStream(): Observable<string> {
    return new Observable<string>(observer => {
      const eventSource = new EventSource('/stream');

      eventSource.onmessage = (event: MessageEvent) => {
        const data = event.data as string;
        observer.next(data);

        if (data === '__DONE__' || data === '__ERROR__') {
          eventSource.close();
          observer.complete();
        }
      };

      eventSource.onerror = (error) => {
        // SSE errors or closing
        if (eventSource.readyState === EventSource.CLOSED) {
          observer.complete();
        } else {
          observer.error(error);
          eventSource.close();
        }
      };

      return () => {
        eventSource.close();
      };
    });
  }
}
