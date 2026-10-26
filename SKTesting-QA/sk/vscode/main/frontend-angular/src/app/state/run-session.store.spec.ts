import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { RunSessionStore } from './run-session.store';

describe('RunSessionStore — log line colours', () => {
  let level: (line: string) => string;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])]
    });
    const store = TestBed.inject(RunSessionStore) as any;
    level = (line: string) => store.classifyLogLevel(line);
  });

  it('highlights app error messages in red and validation messages in amber', () => {
    expect(level('21:11:42 → [Alert] Internal Server Error')).toBe('error');
    expect(level('21:08:51 → [Alert] Short code is mandatory')).toBe('warn');
    expect(level('21:09:13 → [Alert] Duplicate short codes found')).toBe('warn');
  });

  it('keeps success messages and test results as they were', () => {
    expect(level('21:06:21 → [Alert] Advanced Configuration Saved Successfully')).toBe('info');
    expect(level('21:05:24 → [Toast] Success')).toBe('info');
    expect(level('[PASS] WH_030 Verify save failure handling — simulated HTTP 500, the app showed: [Alert] Internal Server Error')).toBe('success');
    expect(level('[FAIL] WH_007 Save new Location — QA2105L missing after save + reload')).toBe('error');
  });
});
