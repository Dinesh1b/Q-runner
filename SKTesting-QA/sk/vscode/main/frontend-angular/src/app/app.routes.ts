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
    path: 'login',
    redirectTo: 'auth',
    pathMatch: 'full'
  },
  {
    path: 'signup',
    redirectTo: 'auth',
    pathMatch: 'full'
  },
  {
    path: 'verify',
    redirectTo: 'auth',
    pathMatch: 'full'
  },
  {
    path: 'set-password',
    redirectTo: 'auth',
    pathMatch: 'full'
  },
  {
    path: 'forgot-password',
    redirectTo: 'auth',
    pathMatch: 'full'
  },
  {
    path: 'reset-password',
    redirectTo: 'auth',
    pathMatch: 'full'
  },
  {
    path: '**',
    redirectTo: ''
  }
];
