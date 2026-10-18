import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { map } from 'rxjs';

export const guestGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isInitialized()) {
    if (!authService.skipAuth() && !authService.isAuthenticated()) {
      return true;
    }
    // If authenticated or skipAuth is active, redirect to home
    return router.createUrlTree(['/']);
  }

  return authService.checkAuthStatus().pipe(
    map(res => {
      if (!res.skip_auth && !res.authenticated) {
        return true;
      }
      return router.createUrlTree(['/']);
    })
  );
};
