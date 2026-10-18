import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ModulesApiResponse } from '../models/module-registry.model';

@Injectable({
  providedIn: 'root'
})
export class ModuleService {
  private readonly http = inject(HttpClient);

  getModules(): Observable<ModulesApiResponse> {
    return this.http.get<ModulesApiResponse>('/api/modules');
  }
}
