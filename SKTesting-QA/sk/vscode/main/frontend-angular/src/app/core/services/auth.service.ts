import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap, catchError, of, map } from 'rxjs';
import {
  User,
  AuthApiResponse,
  AuthStatusResponse,
  DevOtpResponse,
  LoginPayload,
  SignupPayload,
  VerifyOtpPayload,
  SetPasswordPayload,
  ForgotPasswordPayload,
  ResetPasswordPayload
} from '../models/auth.model';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  readonly user = signal<User | null>(null);
  readonly isAuthenticated = signal<boolean>(false);
  readonly skipAuth = signal<boolean>(false);
  readonly isInitialized = signal<boolean>(false);
  readonly isLoading = signal<boolean>(false);

  checkAuthStatus(): Observable<AuthStatusResponse> {
    this.isLoading.set(true);
    return this.http.get<AuthStatusResponse>('/auth/me').pipe(
      tap(res => {
        this.isLoading.set(false);
        this.isInitialized.set(true);
        if (res.ok) {
          this.skipAuth.set(res.skip_auth);
          this.isAuthenticated.set(res.authenticated);
          this.user.set(res.user ?? null);
        }
      }),
      catchError(() => {
        this.isLoading.set(false);
        this.isInitialized.set(true);
        // Default to safe state if backend doesn't respond
        return of({ ok: true, authenticated: true, skip_auth: true });
      })
    );
  }

  signup(payload: SignupPayload): Observable<AuthApiResponse> {
    return this.http.post<AuthApiResponse>('/auth/signup', payload);
  }

  verifyOtp(payload: VerifyOtpPayload): Observable<AuthApiResponse> {
    return this.http.post<AuthApiResponse>('/auth/verify', payload);
  }

  resendOtp(email: string): Observable<AuthApiResponse> {
    return this.http.post<AuthApiResponse>('/auth/resend', { email });
  }

  setPassword(payload: SetPasswordPayload): Observable<AuthApiResponse> {
    return this.http.post<AuthApiResponse>('/auth/set-password', payload).pipe(
      tap(res => {
        if (res.ok) {
          this.isAuthenticated.set(true);
        }
      })
    );
  }

  login(payload: LoginPayload): Observable<AuthApiResponse> {
    return this.http.post<AuthApiResponse>('/auth/login', payload).pipe(
      tap(res => {
        if (res.ok) {
          this.isAuthenticated.set(true);
          this.user.set({ id: 1, email: payload.email });
        }
      })
    );
  }

  forgotPassword(payload: ForgotPasswordPayload): Observable<AuthApiResponse> {
    return this.http.post<AuthApiResponse>('/auth/forgot-password', payload);
  }

  resetPassword(payload: ResetPasswordPayload): Observable<AuthApiResponse> {
    return this.http.post<AuthApiResponse>('/auth/reset-password', payload);
  }

  logout(): Observable<AuthApiResponse> {
    return this.http.post<AuthApiResponse>('/auth/logout', {}).pipe(
      tap(() => {
        this.user.set(null);
        this.isAuthenticated.set(false);
        this.router.navigate(['/login']);
      })
    );
  }

  fetchDevOtp(): Observable<DevOtpResponse> {
    return this.http.get<DevOtpResponse>('/dev/otp');
  }
}
