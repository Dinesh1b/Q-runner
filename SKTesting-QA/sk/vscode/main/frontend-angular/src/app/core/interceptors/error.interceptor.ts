import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse) {
        const errorMsg = error.error?.error || error.message || 'Unknown network error';
        console.error(`[API Error] ${req.method} ${req.url}:`, errorMsg, error);
      }
      return throwError(() => error);
    })
  );
};
