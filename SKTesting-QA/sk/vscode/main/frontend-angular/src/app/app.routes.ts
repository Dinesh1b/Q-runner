import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { guestGuard } from './core/guards/guest.guard';

export const routes: Routes = [
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/shell/shell.component').then(m => m.ShellComponent)
  },
  {
    path: 'auth',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/auth.component').then(m => m.AuthComponent)
  },
  {
    path: 'auth/:view',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/auth.component').then(m => m.AuthComponent)
  },
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/auth.component').then(m => m.AuthComponent)
  },
  {
    path: 'signup',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/auth.component').then(m => m.AuthComponent)
  },
  {
    path: 'verify',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/auth.component').then(m => m.AuthComponent)
  },
  {
    path: 'set-password',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/auth.component').then(m => m.AuthComponent)
  },
  {
    path: 'forgot-password',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/auth.component').then(m => m.AuthComponent)
  },
  {
    path: 'reset-password',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/auth.component').then(m => m.AuthComponent)
  },
  {
    path: '**',
    redirectTo: ''
  }
];
