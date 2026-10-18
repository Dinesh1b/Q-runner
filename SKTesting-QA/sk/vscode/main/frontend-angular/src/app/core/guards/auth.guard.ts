import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { map, of } from 'rxjs';

export const authGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isInitialized()) {
    if (authService.skipAuth() || authService.isAuthenticated()) {
      return true;
    }
    return router.createUrlTree(['/auth/login']);
  }

  return authService.checkAuthStatus().pipe(
    map(res => {
      if (res.skip_auth || res.authenticated) {
        return true;
      }
      return router.createUrlTree(['/auth/login']);
    })
  );
};
