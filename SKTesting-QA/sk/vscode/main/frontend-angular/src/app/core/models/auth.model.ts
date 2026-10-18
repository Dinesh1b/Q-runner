/**
 * auth.model.ts
 * Type definitions for authentication requests, responses, and session status.
 */

export interface User {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  is_verified?: boolean;
}

export interface AuthApiResponse {
  ok: boolean;
  message?: string;
  error?: string;
  redirect?: string;
}

export interface AuthStatusResponse {
  ok: boolean;
  authenticated: boolean;
  skip_auth: boolean;
  user?: User;
  error?: string;
}

export interface DevOtpResponse {
  ok: boolean;
  code?: string;
  email?: string;
  purpose?: string;
  expires_at?: number;
}

export interface SignupPayload {
  email: string;
  first_name: string;
  last_name: string;
}

export interface VerifyOtpPayload {
  email: string;
  code: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface SetPasswordPayload {
  email: string;
  password: string;
}

export interface ForgotPasswordPayload {
  email: string;
}

export interface ResetPasswordPayload {
  email: string;
  code: string;
  password: string;
}
