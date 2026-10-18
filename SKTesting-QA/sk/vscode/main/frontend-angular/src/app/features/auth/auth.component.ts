import { Component, inject, signal, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { ThemeService } from '../../core/services/theme.service';

type AuthView = 'login' | 'signup' | 'verify' | 'setpw' | 'forgot' | 'reset' | 'success';

@Component({
  selector: 'app-auth',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `
    <div class="bg-mesh"></div>
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>

    <!-- Topnav -->
    <nav class="nav">
      <div class="logo">
        <div class="logo-gem">QA</div>
        <div class="logo-wrap">
          <div class="logo-name">Q<em>-</em>A Runner</div>
          <div class="logo-sub">Automation Suite</div>
        </div>
      </div>
      <div class="nav-right">
        <div class="theme-btn" (click)="themeService.toggleTheme()">
          <button class="theme-seg" [class.active]="themeService.currentTheme() === 'light'">
            ☀ Light
          </button>
          <button class="theme-seg" [class.active]="themeService.currentTheme() === 'dark'">
            🌙 Dark
          </button>
        </div>
      </div>
    </nav>

    <div class="auth-wrap">
      <!-- ════════════ LOGIN CARD ════════════ -->
      @if (view() === 'login') {
        <div class="auth-card">
          <div class="auth-head">
            <div class="auth-badge">
              <span class="auth-badge-dot"></span>Sign in
            </div>
            <div class="auth-title">Welcome <em>back</em></div>
            <div class="auth-sub">Enter your credentials to access the runner suite</div>
          </div>
          <div class="auth-body">
            @if (alertMsg()) {
              <div class="alert" [ngClass]="alertType() === 'error' ? 'alert-err' : 'alert-ok'">
                <span class="alert-icon">{{ alertType() === 'error' ? '⚠️' : '✓' }}</span>
                <div class="alert-body">{{ alertMsg() }}</div>
              </div>
            }

            <form [formGroup]="loginForm" (ngSubmit)="onLogin()">
              <div class="fld">
                <label class="fld-lbl">Email Address <span class="req">*</span></label>
                <div class="input-wrap">
                  <input type="email" formControlName="email" placeholder="you@example.com" />
                  <span class="input-icon">✉</span>
                </div>
              </div>

              <div class="fld" style="margin-top: 14px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <label class="fld-lbl">Password <span class="req">*</span></label>
                  <button type="button" class="btn-link" (click)="setView('forgot')">Forgot?</button>
                </div>
                <div class="input-wrap">
                  <input [type]="showPassword() ? 'text' : 'password'" formControlName="password" placeholder="••••••••" style="padding-right:56px;" />
                  <span class="input-toggle" (click)="toggleShowPassword()">{{ showPassword() ? 'Hide' : 'Show' }}</span>
                </div>
              </div>

              <button type="submit" class="btn-primary" [disabled]="loginForm.invalid || authService.isLoading()" style="margin-top: 18px;">
                @if (authService.isLoading()) {
                  <span class="spin"></span> Signing in...
                } @else {
                  Sign In →
                }
              </button>
            </form>
          </div>
          <div class="auth-foot">
            Don't have an account? <a (click)="setView('signup')">Sign up</a>
          </div>
        </div>
      }

      <!-- ════════════ SIGNUP CARD ════════════ -->
      @if (view() === 'signup') {
        <div class="auth-card">
          <div class="auth-head">
            <div class="step-row">
              <div class="step-node">
                <div class="step-circle active">1</div>
                <div class="step-label active">Account</div>
              </div>
              <div class="step-line"></div>
              <div class="step-node">
                <div class="step-circle">2</div>
                <div class="step-label">Verify</div>
              </div>
              <div class="step-line"></div>
              <div class="step-node">
                <div class="step-circle">3</div>
                <div class="step-label">Password</div>
              </div>
            </div>
            <div class="auth-badge" style="margin-top:14px;">
              <span class="auth-badge-dot"></span>New Account
            </div>
            <div class="auth-title">Create your <em>account</em></div>
            <div class="auth-sub">Enter your details to get started with Q-A Runner</div>
          </div>
          <div class="auth-body">
            @if (alertMsg()) {
              <div class="alert" [ngClass]="alertType() === 'error' ? 'alert-err' : 'alert-ok'">
                <span class="alert-icon">{{ alertType() === 'error' ? '⚠️' : '✓' }}</span>
                <div class="alert-body">{{ alertMsg() }}</div>
              </div>
            }

            <form [formGroup]="signupForm" (ngSubmit)="onSignup()">
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
                <div class="fld">
                  <label class="fld-lbl">First Name <span class="req">*</span></label>
                  <input type="text" formControlName="first_name" placeholder="John" />
                </div>
                <div class="fld">
                  <label class="fld-lbl">Last Name <span class="req">*</span></label>
                  <input type="text" formControlName="last_name" placeholder="Doe" />
                </div>
              </div>

              <div class="fld" style="margin-top: 14px;">
                <label class="fld-lbl">Work Email <span class="req">*</span></label>
                <div class="input-wrap">
                  <input type="email" formControlName="email" placeholder="you@company.com" />
                  <span class="input-icon">✉</span>
                </div>
              </div>

              <button type="submit" class="btn-primary" [disabled]="signupForm.invalid || authService.isLoading()" style="margin-top: 18px;">
                @if (authService.isLoading()) {
                  <span class="spin"></span> Sending code...
                } @else {
                  Continue →
                }
              </button>
            </form>
          </div>
          <div class="auth-foot">
            Already registered? <a (click)="setView('login')">Sign in</a>
          </div>
        </div>
      }

      <!-- ════════════ VERIFY OTP CARD ════════════ -->
      @if (view() === 'verify') {
        <div class="auth-card">
          <div class="auth-head">
            <div class="step-row">
              <div class="step-node">
                <div class="step-circle done">✓</div>
                <div class="step-label">Account</div>
              </div>
              <div class="step-line done"></div>
              <div class="step-node">
                <div class="step-circle active">2</div>
                <div class="step-label active">Verify</div>
              </div>
              <div class="step-line"></div>
              <div class="step-node">
                <div class="step-circle">3</div>
                <div class="step-label">Password</div>
              </div>
            </div>
            <div class="auth-badge" style="margin-top:14px; background:var(--sky-soft); border-color:rgba(14,165,233,0.22); color:var(--sky);">
              <span class="auth-badge-dot" style="background:var(--sky)"></span>Verification
            </div>
            <div class="auth-title">Verify your <em>email</em></div>
            <div class="auth-sub">Enter the 6-digit code sent to <strong>{{ activeEmail() }}</strong></div>
          </div>
          <div class="auth-body">
            @if (alertMsg()) {
              <div class="alert" [ngClass]="alertType() === 'error' ? 'alert-err' : 'alert-ok'">
                <span class="alert-icon">{{ alertType() === 'error' ? '⚠️' : '✓' }}</span>
                <div class="alert-body">{{ alertMsg() }}</div>
              </div>
            }

            <div class="fld">
              <label class="fld-lbl" style="text-align:center;">6-Digit Verification Code</label>
              <div class="otp-row">
                @for (digit of otpDigits(); track $index) {
                  <input
                    type="text"
                    class="otp-input"
                    maxlength="1"
                    inputmode="numeric"
                    [value]="digit"
                    [class.filled]="digit !== ''"
                    (input)="onOtpInput($index, $event)"
                    (keydown)="onOtpKeydown($index, $event)"
                    id="otp-{{$index}}"
                  />
                  @if ($index === 2) {
                    <span class="otp-sep">—</span>
                  }
                }
              </div>
            </div>

            <button type="button" class="btn-primary" [disabled]="getOtpString().length < 6 || authService.isLoading()" (click)="onVerify()">
              @if (authService.isLoading()) {
                <span class="spin"></span> Verifying...
              } @else {
                Verify Code →
              }
            </button>

            <div class="resend-row">
              @if (resendWait() > 0) {
                Resend code in <span class="resend-count">{{ resendWait() }}s</span>
              } @else {
                Didn't receive it? <button type="button" class="btn-link" (click)="onResend()">Resend Code</button>
              }
            </div>
          </div>
          <div class="auth-foot">
            <a (click)="setView('signup')">← Back to account details</a>
          </div>
        </div>
      }

      <!-- ════════════ SET PASSWORD CARD ════════════ -->
      @if (view() === 'setpw') {
        <div class="auth-card">
          <div class="auth-head">
            <div class="step-row">
              <div class="step-node">
                <div class="step-circle done">✓</div>
                <div class="step-label">Account</div>
              </div>
              <div class="step-line done"></div>
              <div class="step-node">
                <div class="step-circle done">✓</div>
                <div class="step-label">Verify</div>
              </div>
              <div class="step-line done"></div>
              <div class="step-node">
                <div class="step-circle active">3</div>
                <div class="step-label active">Password</div>
              </div>
            </div>
            <div class="auth-badge" style="margin-top:14px; background:var(--emerald-soft); border-color:rgba(16,185,129,0.22); color:var(--emerald);">
              <span class="auth-badge-dot" style="background:var(--emerald)"></span>Almost there
            </div>
            <div class="auth-title">Set your <em>password</em></div>
            <div class="auth-sub">Choose a strong password to secure your account</div>
          </div>
          <div class="auth-body">
            @if (alertMsg()) {
              <div class="alert" [ngClass]="alertType() === 'error' ? 'alert-err' : 'alert-ok'">
                <span class="alert-icon">{{ alertType() === 'error' ? '⚠️' : '✓' }}</span>
                <div class="alert-body">{{ alertMsg() }}</div>
              </div>
            }

            <form [formGroup]="setPasswordForm" (ngSubmit)="onSetPassword()">
              <div class="fld">
                <label class="fld-lbl">New Password <span class="req">*</span></label>
                <div class="input-wrap">
                  <input
                    [type]="showSetPw() ? 'text' : 'password'"
                    formControlName="password"
                    placeholder="••••••••"
                    style="padding-right:56px;"
                    (input)="calculatePwStrength()"
                  />
                  <span class="input-toggle" (click)="showSetPw.set(!showSetPw())">
                    {{ showSetPw() ? 'Hide' : 'Show' }}
                  </span>
                </div>

                <div class="pw-strength">
                  <div class="pw-bar" [class.s1]="pwScore() >= 1"></div>
                  <div class="pw-bar" [class.s2]="pwScore() >= 2"></div>
                  <div class="pw-bar" [class.s3]="pwScore() >= 3"></div>
                  <div class="pw-bar" [class.s4]="pwScore() >= 4"></div>
                </div>
                <div class="pw-label">{{ pwLabel() }}</div>

                <div class="pw-rules">
                  <div class="pw-rule" [class.ok]="hasLength()">
                    <div class="pw-rule-dot">{{ hasLength() ? '✓' : '' }}</div>
                    At least 8 characters
                  </div>
                  <div class="pw-rule" [class.ok]="hasNumber()">
                    <div class="pw-rule-dot">{{ hasNumber() ? '✓' : '' }}</div>
                    Contains a number
                  </div>
                  <div class="pw-rule" [class.ok]="hasSymbol()">
                    <div class="pw-rule-dot">{{ hasSymbol() ? '✓' : '' }}</div>
                    Contains a symbol
                  </div>
                  <div class="pw-rule" [class.ok]="hasMix()">
                    <div class="pw-rule-dot">{{ hasMix() ? '✓' : '' }}</div>
                    Upper & lowercase mix
                  </div>
                </div>
              </div>

              <div class="fld" style="margin-top: 14px;">
                <label class="fld-lbl">Confirm Password <span class="req">*</span></label>
                <div class="input-wrap">
                  <input
                    [type]="showSetPw() ? 'text' : 'password'"
                    formControlName="confirm_password"
                    placeholder="••••••••"
                    style="padding-right:56px;"
                  />
                </div>
              </div>

              <button type="submit" class="btn-primary" [disabled]="setPasswordForm.invalid || !hasLength() || authService.isLoading()" style="margin-top: 18px;">
                @if (authService.isLoading()) {
                  <span class="spin"></span> Creating account...
                } @else {
                  Create Account →
                }
              </button>
            </form>
          </div>
          <div class="auth-foot">
            <a (click)="setView('verify')">← Back to verification</a>
          </div>
        </div>
      }

      <!-- ════════════ FORGOT PASSWORD CARD ════════════ -->
      @if (view() === 'forgot') {
        <div class="auth-card">
          <div class="auth-head">
            <a class="back-link" (click)="setView('login')">
              ← Back to Login
            </a>
            <div class="auth-badge" style="margin-top:12px; background:var(--amber-soft); border-color:rgba(245,158,11,0.22); color:var(--amber);">
              <span class="auth-badge-dot" style="background:var(--amber)"></span>Password Recovery
            </div>
            <div class="auth-title">Reset your <em style="color:var(--amber)">password</em></div>
            <div class="auth-sub">Enter your email and we'll send a reset code</div>
          </div>
          <div class="auth-body">
            @if (alertMsg()) {
              <div class="alert" [ngClass]="alertType() === 'error' ? 'alert-err' : 'alert-ok'">
                <span class="alert-icon">{{ alertType() === 'error' ? '⚠️' : '✓' }}</span>
                <div class="alert-body">{{ alertMsg() }}</div>
              </div>
            }

            <form [formGroup]="forgotForm" (ngSubmit)="onForgot()">
              <div class="fld">
                <label class="fld-lbl">Email Address <span class="req">*</span></label>
                <div class="input-wrap">
                  <input type="email" formControlName="email" placeholder="you@example.com" />
                  <span class="input-icon">✉</span>
                </div>
              </div>

              <button
                type="submit"
                class="btn-primary"
                [disabled]="forgotForm.invalid || authService.isLoading()"
                style="margin-top: 18px; background:linear-gradient(135deg,#fcd34d 0%,#f59e0b 60%,#d97706 100%); box-shadow:0 6px 24px rgba(245,158,11,0.3);"
              >
                @if (authService.isLoading()) {
                  <span class="spin"></span> Sending reset code...
                } @else {
                  Send Reset Code →
                }
              </button>
            </form>
          </div>
          <div class="auth-foot">
            Remember it? <a (click)="setView('login')">Sign in</a>
          </div>
        </div>
      }

      <!-- ════════════ RESET PASSWORD CARD ════════════ -->
      @if (view() === 'reset') {
        <div class="auth-card">
          <div class="auth-head">
            <div class="auth-badge" style="background:var(--amber-soft); border-color:rgba(245,158,11,0.22); color:var(--amber);">
              <span class="auth-badge-dot" style="background:var(--amber)"></span>Code Sent
            </div>
            <div class="auth-title">Enter reset <em style="color:var(--amber)">code</em></div>
            <div class="auth-sub">Check <strong>{{ activeEmail() }}</strong> for your 6-digit code, then choose a new password.</div>
          </div>
          <div class="auth-body">
            @if (alertMsg()) {
              <div class="alert" [ngClass]="alertType() === 'error' ? 'alert-err' : 'alert-ok'">
                <span class="alert-icon">{{ alertType() === 'error' ? '⚠️' : '✓' }}</span>
                <div class="alert-body">{{ alertMsg() }}</div>
              </div>
            }

            <form [formGroup]="resetForm" (ngSubmit)="onReset()">
              <div class="fld">
                <label class="fld-lbl" style="text-align:center;">Reset Code</label>
                <div class="otp-row">
                  @for (digit of resetOtpDigits(); track $index) {
                    <input
                      type="text"
                      class="otp-input"
                      maxlength="1"
                      inputmode="numeric"
                      [value]="digit"
                      [class.filled]="digit !== ''"
                      (input)="onResetOtpInput($index, $event)"
                      (keydown)="onResetOtpKeydown($index, $event)"
                      id="rotp-{{$index}}"
                    />
                    @if ($index === 2) {
                      <span class="otp-sep">—</span>
                    }
                  }
                </div>
              </div>

              <div class="fld" style="margin-top: 14px;">
                <label class="fld-lbl">New Password <span class="req">*</span></label>
                <input type="password" formControlName="password" placeholder="••••••••" />
              </div>

              <div class="fld" style="margin-top: 14px;">
                <label class="fld-lbl">Confirm Password <span class="req">*</span></label>
                <input type="password" formControlName="confirm_password" placeholder="••••••••" />
              </div>

              <button
                type="submit"
                class="btn-primary"
                [disabled]="resetForm.invalid || getResetOtpString().length < 6 || authService.isLoading()"
                style="margin-top: 18px; background:linear-gradient(135deg,#fcd34d 0%,#f59e0b 60%,#d97706 100%); box-shadow:0 6px 24px rgba(245,158,11,0.3);"
              >
                @if (authService.isLoading()) {
                  <span class="spin"></span> Resetting...
                } @else {
                  Reset Password →
                }
              </button>
            </form>
          </div>
          <div class="auth-foot">
            <a (click)="setView('forgot')">← Re-enter email</a>
          </div>
        </div>
      }

      <!-- ════════════ SUCCESS CARD ════════════ -->
      @if (view() === 'success') {
        <div class="auth-card">
          <div class="auth-head">
            <div class="success-ring">🎉</div>
            <div class="auth-title" style="text-align:center;">You're all <em>set!</em></div>
            <div class="auth-sub" style="text-align:center;">Your Q-A Runner account has been verified.<br>Redirecting to dashboard...</div>
          </div>
          <div class="auth-body">
            <div class="alert alert-ok">
              <span class="alert-icon">✓</span>
              <div class="alert-body">Account verified & password set. Signing you in automatically.</div>
            </div>
            <button type="button" class="btn-primary" (click)="enterDashboard()">Open Dashboard →</button>
          </div>
        </div>
      }
    </div>

    <!-- Dev OTP Toast -->
    @if (showDevToast()) {
      <div class="dev-toast">
        <button class="dev-toast-close" (click)="showDevToast.set(false)">✕</button>
        <div class="dev-toast-tag">Dev — OTP Notification</div>
        <div class="dev-toast-email">{{ devEmail() }}</div>
        <div class="dev-toast-code" (click)="autoFillDevOtp()" title="Click to auto-fill code">{{ devCode() }}</div>
        <div class="dev-toast-hint">Click code to auto-fill · Click ✕ to dismiss</div>
      </div>
    }
  `
})
export class AuthComponent implements OnInit, OnDestroy {
  readonly authService = inject(AuthService);
  readonly themeService = inject(ThemeService);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder);

  readonly view = signal<AuthView>('login');
  readonly alertMsg = signal<string | null>(null);
  readonly alertType = signal<'error' | 'ok'>('error');
  readonly activeEmail = signal<string>('');

  /* Toggles */
  readonly showPassword = signal<boolean>(false);
  readonly showSetPw = signal<boolean>(false);

  /* OTP */
  readonly otpDigits = signal<string[]>(['', '', '', '', '', '']);
  readonly resetOtpDigits = signal<string[]>(['', '', '', '', '', '']);
  readonly resendWait = signal<number>(0);
  private resendTimer: ReturnType<typeof setInterval> | null = null;

  /* Dev Toast */
  readonly showDevToast = signal<boolean>(false);
  readonly devCode = signal<string>('');
  readonly devEmail = signal<string>('');
  private devPollTimer: ReturnType<typeof setInterval> | null = null;

  /* Password strength */
  readonly pwScore = signal<number>(0);
  readonly pwLabel = signal<string>('—');
  readonly hasLength = signal<boolean>(false);
  readonly hasNumber = signal<boolean>(false);
  readonly hasSymbol = signal<boolean>(false);
  readonly hasMix = signal<boolean>(false);

  /* Forms */
  readonly loginForm = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]]
  });

  readonly signupForm = this.fb.group({
    first_name: ['', [Validators.required]],
    last_name: ['', [Validators.required]],
    email: ['', [Validators.required, Validators.email]]
  });

  readonly setPasswordForm = this.fb.group({
    password: ['', [Validators.required, Validators.minLength(8)]],
    confirm_password: ['', [Validators.required]]
  });

  readonly forgotForm = this.fb.group({
    email: ['', [Validators.required, Validators.email]]
  });

  readonly resetForm = this.fb.group({
    password: ['', [Validators.required, Validators.minLength(8)]],
    confirm_password: ['', [Validators.required]]
  });

  ngOnInit(): void {
    // Check if initial route path dictates view
    const path = window.location.pathname;
    if (path.includes('signup')) this.setView('signup');
    else if (path.includes('forgot')) this.setView('forgot');
    else if (path.includes('reset')) this.setView('reset');
    else if (path.includes('verify')) this.setView('verify');
    else if (path.includes('set-password')) this.setView('setpw');

    this.startDevOtpPolling();
  }

  ngOnDestroy(): void {
    if (this.resendTimer) clearInterval(this.resendTimer);
    if (this.devPollTimer) clearInterval(this.devPollTimer);
  }

  setView(view: AuthView): void {
    this.view.set(view);
    this.alertMsg.set(null);
  }

  toggleShowPassword(): void {
    this.showPassword.update(v => !v);
  }

  onLogin(): void {
    if (this.loginForm.invalid) return;
    const { email, password } = this.loginForm.value;
    if (!email || !password) return;

    this.alertMsg.set(null);
    this.authService.login({ email, password }).subscribe({
      next: (res) => {
        if (res.ok) {
          this.router.navigate(['/']);
        } else {
          this.alertType.set('error');
          this.alertMsg.set(res.error || 'Invalid credentials');
        }
      },
      error: (err) => {
        this.alertType.set('error');
        this.alertMsg.set(err.error?.error || 'Login failed. Please check credentials.');
      }
    });
  }

  onSignup(): void {
    if (this.signupForm.invalid) return;
    const { first_name, last_name, email } = this.signupForm.value;
    if (!first_name || !last_name || !email) return;

    this.alertMsg.set(null);
    this.activeEmail.set(email);

    this.authService.signup({ first_name, last_name, email }).subscribe({
      next: (res) => {
        if (res.ok) {
          this.setView('verify');
          this.startResendCountdown(60);
          this.triggerDevOtpCheck();
        } else {
          this.alertType.set('error');
          this.alertMsg.set(res.error || 'Failed to send verification code');
        }
      },
      error: (err) => {
        this.alertType.set('error');
        this.alertMsg.set(err.error?.error || 'Signup failed');
      }
    });
  }

  onOtpInput(index: number, event: Event): void {
    const input = event.target as HTMLInputElement;
    const val = input.value.replace(/\D/g, '');
    const current = [...this.otpDigits()];
    current[index] = val ? val[val.length - 1] : '';
    this.otpDigits.set(current);

    if (val && index < 5) {
      const nextInput = document.getElementById(`otp-${index + 1}`);
      nextInput?.focus();
    }
  }

  onOtpKeydown(index: number, event: KeyboardEvent): void {
    if (event.key === 'Backspace' && !this.otpDigits()[index] && index > 0) {
      const prevInput = document.getElementById(`otp-${index - 1}`);
      prevInput?.focus();
    }
  }

  getOtpString(): string {
    return this.otpDigits().join('');
  }

  onVerify(): void {
    const code = this.getOtpString();
    if (code.length < 6) return;

    this.alertMsg.set(null);
    this.authService.verifyOtp({ email: this.activeEmail(), code }).subscribe({
      next: (res) => {
        if (res.ok) {
          this.setView('setpw');
        } else {
          this.alertType.set('error');
          this.alertMsg.set(res.error || 'Invalid or expired verification code');
        }
      },
      error: (err) => {
        this.alertType.set('error');
        this.alertMsg.set(err.error?.error || 'Verification failed');
      }
    });
  }

  onResend(): void {
    if (this.resendWait() > 0) return;
    this.alertMsg.set(null);

    this.authService.resendOtp(this.activeEmail()).subscribe({
      next: (res) => {
        if (res.ok) {
          this.alertType.set('ok');
          this.alertMsg.set('Verification code resent successfully.');
          this.startResendCountdown(60);
          this.triggerDevOtpCheck();
        } else {
          this.alertType.set('error');
          this.alertMsg.set(res.error || 'Failed to resend code');
        }
      },
      error: (err) => {
        this.alertType.set('error');
        this.alertMsg.set(err.error?.error || 'Failed to resend code');
      }
    });
  }

  calculatePwStrength(): void {
    const pw = this.setPasswordForm.get('password')?.value || '';
    const len = pw.length >= 8;
    const num = /[0-9]/.test(pw);
    const sym = /[^A-Za-z0-9]/.test(pw);
    const mix = /[a-z]/.test(pw) && /[A-Z]/.test(pw);

    this.hasLength.set(len);
    this.hasNumber.set(num);
    this.hasSymbol.set(sym);
    this.hasMix.set(mix);

    let score = 0;
    if (len) score++;
    if (num) score++;
    if (sym) score++;
    if (mix) score++;
    this.pwScore.set(score);

    const labels = ['—', 'Weak', 'Fair', 'Good', 'Strong'];
    this.pwLabel.set(labels[score] || '—');
  }

  onSetPassword(): void {
    if (this.setPasswordForm.invalid) return;
    const { password, confirm_password } = this.setPasswordForm.value;
    if (!password || password !== confirm_password) {
      this.alertType.set('error');
      this.alertMsg.set('Passwords do not match');
      return;
    }

    this.alertMsg.set(null);
    this.authService.setPassword({ email: this.activeEmail(), password }).subscribe({
      next: (res) => {
        if (res.ok) {
          this.setView('success');
          setTimeout(() => {
            this.enterDashboard();
          }, 2000);
        } else {
          this.alertType.set('error');
          this.alertMsg.set(res.error || 'Failed to set password');
        }
      },
      error: (err) => {
        this.alertType.set('error');
        this.alertMsg.set(err.error?.error || 'Failed to set password');
      }
    });
  }

  onForgot(): void {
    if (this.forgotForm.invalid) return;
    const email = this.forgotForm.get('email')?.value;
    if (!email) return;

    this.alertMsg.set(null);
    this.activeEmail.set(email);

    this.authService.forgotPassword({ email }).subscribe({
      next: (res) => {
        this.setView('reset');
        this.triggerDevOtpCheck();
      },
      error: (err) => {
        this.alertType.set('error');
        this.alertMsg.set(err.error?.error || 'Error sending reset code');
      }
    });
  }

  onResetOtpInput(index: number, event: Event): void {
    const input = event.target as HTMLInputElement;
    const val = input.value.replace(/\D/g, '');
    const current = [...this.resetOtpDigits()];
    current[index] = val ? val[val.length - 1] : '';
    this.resetOtpDigits.set(current);

    if (val && index < 5) {
      const nextInput = document.getElementById(`rotp-${index + 1}`);
      nextInput?.focus();
    }
  }

  onResetOtpKeydown(index: number, event: KeyboardEvent): void {
    if (event.key === 'Backspace' && !this.resetOtpDigits()[index] && index > 0) {
      const prevInput = document.getElementById(`rotp-${index - 1}`);
      prevInput?.focus();
    }
  }

  getResetOtpString(): string {
    return this.resetOtpDigits().join('');
  }

  onReset(): void {
    const code = this.getResetOtpString();
    const { password, confirm_password } = this.resetForm.value;
    if (code.length < 6 || !password || password !== confirm_password) {
      this.alertType.set('error');
      this.alertMsg.set('Please check your code and confirm matching passwords.');
      return;
    }

    this.alertMsg.set(null);
    this.authService.resetPassword({ email: this.activeEmail(), code, password }).subscribe({
      next: (res) => {
        if (res.ok) {
          this.setView('login');
          this.alertType.set('ok');
          this.alertMsg.set('Password successfully reset. Please sign in.');
        } else {
          this.alertType.set('error');
          this.alertMsg.set(res.error || 'Failed to reset password');
        }
      },
      error: (err) => {
        this.alertType.set('error');
        this.alertMsg.set(err.error?.error || 'Failed to reset password');
      }
    });
  }

  enterDashboard(): void {
    this.router.navigate(['/']);
  }

  autoFillDevOtp(): void {
    const code = this.devCode();
    if (!code || code.length < 6) return;

    if (this.view() === 'verify') {
      const digits = code.split('').slice(0, 6);
      this.otpDigits.set(digits);
    } else if (this.view() === 'reset') {
      const digits = code.split('').slice(0, 6);
      this.resetOtpDigits.set(digits);
    }
  }

  private startResendCountdown(seconds: number): void {
    if (this.resendTimer) clearInterval(this.resendTimer);
    this.resendWait.set(seconds);
    this.resendTimer = setInterval(() => {
      this.resendWait.update(w => {
        if (w <= 1) {
          if (this.resendTimer) clearInterval(this.resendTimer);
          return 0;
        }
        return w - 1;
      });
    }, 1000);
  }

  private startDevOtpPolling(): void {
    this.devPollTimer = setInterval(() => {
      this.triggerDevOtpCheck();
    }, 4000);
  }

  private triggerDevOtpCheck(): void {
    this.authService.fetchDevOtp().subscribe({
      next: (res) => {
        if (res.ok && res.code) {
          this.devCode.set(res.code);
          this.devEmail.set(res.email || '');
          this.showDevToast.set(true);
        }
      },
      error: () => {}
    });
  }
}
