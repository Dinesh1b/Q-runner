import { Component, inject, input, output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { UploadService, InspectExcelResult } from '../../../../core/services/upload.service';
import { RunConfigStore } from '../../../../state/run-config.store';

@Component({
  selector: 'app-excel-uploader',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="card">
      <div class="card-hd">
        <div class="card-title">
          <span class="card-icon">📊</span>
          <div>
            <div style="font-weight:700; font-size:15px; color:var(--t0);">Excel Import</div>
            <div style="font-size:12px; color:var(--t3);">Upload Excel file and configure target sheet</div>
          </div>
        </div>
      </div>

      <div class="card-body">
        <!-- Drag & Drop Zone -->
        <div
          class="upload-zone"
          [class.drag]="isDragging()"
          [class.has-file]="!!fileName()"
          (dragover)="onDragOver($event)"
          (dragleave)="isDragging.set(false)"
          (drop)="onDrop($event)"
        >
          <input
            type="file"
            accept=".xlsx,.xls"
            (change)="onFileSelected($event)"
          />
          <div class="uz-inner">
            <div class="uz-icon">☁️</div>
            <div class="uz-meta">
              <div class="uz-title" [class.chosen]="!!fileName()">
                {{ fileName() ? fileName() : (label() || "Drag & Drop Excel File") }}
              </div>
              <div class="uz-hint">Accepts .xlsx · .xls &nbsp;|&nbsp; Click to browse</div>
            </div>
            <div class="uz-actions">
              <span class="btn btn-ghost">Browse</span>
            </div>
          </div>
        </div>

        <!-- Sample Download Link -->
        @if (sampleUrl()) {
          <div style="margin-top:10px; display:flex; justify-content:flex-end;">
            <a [href]="sampleUrl()" [download]="sampleFilename() || 'sample.xlsx'" class="sample-dl-btn">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="12" y1="11" x2="12" y2="17" />
                <polyline points="9 14 12 17 15 14" />
              </svg>
              SAMPLE .XLSX
            </a>
          </div>
        }

        <!-- Uploaded File Metadata Pill -->
        @if (fileName()) {
          <div class="file-meta show">
            <span class="file-meta-icon">📊</span>
            <span class="file-meta-name">{{ fileName() }}</span>
            <span class="file-meta-size">({{ fileSize() }})</span>
            <span class="file-meta-ok">✓ UPLOADED</span>
          </div>
        }

        @if (errorMessage()) {
          <div style="margin-top:8px; font-size:12px; color:var(--rose);">
            {{ errorMessage() }}
          </div>
        }

        <!-- Sheet Selector Dropdown -->
        <div class="g g1" style="margin-top:14px;">
          <div class="fld">
            <label class="fld-lbl">{{ sheetLabel() || 'Sheet Name' }}</label>
            <select
              [disabled]="sheets().length === 0"
              [value]="selectedSheet()"
              (change)="onSheetChanged($event)"
            >
              @if (sheets().length === 0) {
                <option value="">Upload Excel first...</option>
              } @else {
                @for (sheet of sheets(); track sheet) {
                  <option [value]="sheet">{{ sheet }}</option>
                }
              }
            </select>
            <div class="fld-hint">{{ sheetHint() || 'Select sheet to read configuration and records from' }}</div>
          </div>
        </div>
      </div>
    </div>
  `
})
export class ExcelUploaderComponent {
  private readonly uploadService = inject(UploadService);
  private readonly configStore = inject(RunConfigStore);

  readonly label = input<string>("Drag & Drop 'main_qexcel.xlsx'");
  readonly storageKey = input<string>('OA_EXCEL');
  readonly sampleUrl = input<string>('/sample_excel');
  readonly sampleFilename = input<string>('main_qexcel.xlsx');
  readonly sheetLabel = input<string>('Sheet Name');
  readonly sheetHint = input<string>('Configures which sheet to use');

  readonly selectedSheet = input<string>('');
  readonly sheetChange = output<string>();
  readonly sheetsLoaded = output<string[]>();

  readonly isDragging = signal<boolean>(false);
  readonly isUploading = signal<boolean>(false);
  readonly fileName = signal<string>('');
  readonly fileSize = signal<string>('');
  readonly sheets = signal<string[]>([]);
  readonly errorMessage = signal<string | null>(null);

  onDragOver(e: DragEvent): void {
    e.preventDefault();
    this.isDragging.set(true);
  }

  onDrop(e: DragEvent): void {
    e.preventDefault();
    this.isDragging.set(false);
    if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
      this.handleFile(e.dataTransfer.files[0]);
    }
  }

  onFileSelected(e: Event): void {
    const input = e.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFile(input.files[0]);
    }
  }

  private handleFile(file: File): void {
    this.fileName.set(file.name);
    this.fileSize.set(this.formatBytes(file.size));
    this.isUploading.set(true);
    this.errorMessage.set(null);

    // Call inspect API
    this.uploadService.inspectAuditExcel(file).subscribe({
      next: (res: InspectExcelResult) => {
        this.isUploading.set(false);
        if (res.ok && res.sheet_names?.length) {
          this.sheets.set(res.sheet_names);
          this.sheetsLoaded.emit(res.sheet_names);

          const defaultSheet = res.default_sheet || res.sheet_names[0];
          if (!this.selectedSheet() || !res.sheet_names.includes(this.selectedSheet())) {
            this.sheetChange.emit(defaultSheet);
          }
        }
      },
      error: () => {
        // Fallback: regular upload
        this.uploadService.uploadFile(file).subscribe({
          next: (res) => {
            this.isUploading.set(false);
            if (res.path) {
              this.configStore.setUploadedPath(this.storageKey(), res.path);
            }
          },
          error: (err) => {
            this.isUploading.set(false);
            this.errorMessage.set(err.message || 'File upload failed');
          }
        });
      }
    });

    // Also persist uploaded path
    this.uploadService.uploadFile(file).subscribe({
      next: (res) => {
        if (res.path) {
          this.configStore.setUploadedPath(this.storageKey(), res.path);
        }
      }
    });
  }

  onSheetChanged(e: Event): void {
    const val = (e.target as HTMLSelectElement).value;
    this.sheetChange.emit(val);
  }

  private formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }
}
