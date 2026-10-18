import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface UploadResult {
  path?: string;
  error?: string;
}

export interface InspectExcelResult {
  ok: boolean;
  sheet_names: string[];
  default_sheet?: string;
  headers_by_sheet: Record<string, string[]>;
  warnings?: string[];
  errors?: string[];
}

@Injectable({
  providedIn: 'root'
})
export class UploadService {
  private readonly http = inject(HttpClient);

  uploadFile(file: File): Observable<UploadResult> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<UploadResult>('/upload', formData);
  }

  inspectAuditExcel(file: File): Observable<InspectExcelResult> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<InspectExcelResult>('/inspect_audit_excel', formData);
  }

  getSampleExcelUrl(): string {
    return '/sample_excel';
  }

  getSampleItemImportExcelUrl(): string {
    return '/sample_excel_item_import';
  }
}
