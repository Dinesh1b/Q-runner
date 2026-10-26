import { Component, WritableSignal, computed, inject } from '@angular/core';
import { RunConfigStore } from '../../../state/run-config.store';
import { ModuleRegistryStore } from '../../../state/module-registry.store';
import {
  ACCOUNT_FIELDS, ACCOUNT_NAMES, ACCOUNTING_MODES, ADVANCED_TOGGLES, BARCODE_FIELD_TYPES, COSTING_METHODS,
  INVENTORY_TYPES, Option, ToggleState, UOM_NAMES, UOM_VALUE_TYPES, UomLevel, UomRow,
} from '../../../core/models/item-group.model';

/** Create Group module: Run Create / Run Update, plus every Item Group setting used for this run. */
@Component({
  selector: 'app-m13-create-group',
  standalone: true,
  template: `
    <div class="module-form-container">
      <!-- Run Options -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title emerald-accent">
            <span class="card-icon">⚙️</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Run Options</div>
              <div style="font-size:12px; color:var(--t3);">Choose what this module does</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="tgl-row" (click)="configStore.cbCg.set(!configStore.cbCg())">
            <div class="tgl-info">
              <div class="tgl-icon">📁</div>
              <div>
                <div class="tgl-title">Run Create Group</div>
                <div class="tgl-sub">run_create_group — create a new group named Group Name</div>
              </div>
            </div>
            <label class="toggle-switch" (click)="$event.stopPropagation()">
              <input
                type="checkbox"
                [checked]="configStore.cbCg()"
                (change)="configStore.cbCg.set(!configStore.cbCg())"
              />
              <span class="toggle-slider"></span>
            </label>
          </div>

          <div class="tgl-row" (click)="configStore.cbUg.set(!configStore.cbUg())">
            <div class="tgl-info">
              <div class="tgl-icon">🔄</div>
              <div>
                <div class="tgl-title">Run Update Group</div>
                <div class="tgl-sub">run_update_group — update the saved group named Group Name to these values</div>
              </div>
            </div>
            <label class="toggle-switch" (click)="$event.stopPropagation()">
              <input
                type="checkbox"
                [checked]="configStore.cbUg()"
                (change)="configStore.cbUg.set(!configStore.cbUg())"
              />
              <span class="toggle-slider"></span>
            </label>
          </div>

          <div class="fld-hint" style="margin-top:10px;">
            With both on, Create runs first. Each one verifies every saved value. The values below are used for
            this run only; backend/Config.py → Inventory Setup keeps the defaults for Inventory.py runs.
          </div>
        </div>
      </div>

      <!-- General -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title emerald-accent">
            <span class="card-icon">🗃️</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">General</div>
              <div style="font-size:12px; color:var(--t3);">Group name, inventory type, barcode fields and IDs</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2">
            <div class="fld">
              <label class="fld-lbl">Group Name <span class="req">*</span></label>
              <input
                type="text"
                [value]="configStore.invGroupName()"
                (input)="configStore.invGroupName.set(val($event))"
                placeholder="Group_34"
              />
              <div class="fld-hint">Import Items also uses this group</div>
            </div>
          </div>

          <div class="am-sec-lbl">Inventory Type</div>
          <div class="inv-type-grid">
            @for (t of inventoryTypes; track t.value) {
              <div
                class="inv-type-card"
                [class.selected]="configStore.invType() === t.value"
                (click)="configStore.invType.set(t.value)"
              >
                <div class="am-mode-icon">{{ t.icon }}</div>
                <div class="am-mode-label">{{ t.value }}</div>
                <div class="am-mode-desc">{{ t.desc }}</div>
                <div class="am-mode-badge">{{ t.badge }}</div>
              </div>
            }
          </div>

          <div class="am-sec-lbl" style="margin-top:18px;">Barcode Fields</div>
          <div class="fld-hint">Field 1 is always "Bar Code"; these are added after it, in this order.</div>
          @for (field of configStore.invFields(); track $index; let i = $index) {
            <div style="display:flex; gap:8px; align-items:center; margin-top:8px;">
              <span style="min-width:60px; font-size:12px; color:var(--t3);">Field {{ i + 2 }}</span>
              <select style="flex:1;" (change)="setAt(configStore.invFields, i, val($event))">
                @for (t of barcodeFieldTypes; track t) {
                  <option [value]="t" [selected]="t === field">{{ t }}</option>
                }
              </select>
              <button type="button" class="btn btn-ghost" title="Remove" (click)="removeAt(configStore.invFields, i)">✕</button>
            </div>
          }
          <button type="button" class="btn btn-ghost" style="margin-top:8px;" (click)="append(configStore.invFields, 'Item Code')">
            + Add field
          </button>

          @if (configStore.invType() === 'Serialized') {
            <div class="fld g-last" style="margin-top:18px;">
              <label class="fld-lbl">ID Names <span class="req">*</span></label>
              <textarea
                rows="3"
                [value]="idsText()"
                (input)="setIds($event)"
                placeholder="Serial Number&#10;IMEI&#10;Barcode"
              ></textarea>
              <div class="fld-hint">One ID name per line</div>
            </div>
          }
        </div>
      </div>

      <!-- Accounting -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title emerald-accent">
            <span class="card-icon">🧾</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Accounting</div>
              <div style="font-size:12px; color:var(--t3);">Costing method, accounting mode and accounts (blank = leave as is)</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2">
            <div class="fld">
              <label class="fld-lbl">Costing Method</label>
              <select (change)="configStore.invCostingMethod.set(val($event))">
                <option value="" [selected]="!configStore.invCostingMethod()">Leave as is</option>
                @for (m of costingMethods; track m.value) {
                  <option [value]="m.value" [disabled]="m.disabled" [selected]="m.value === configStore.invCostingMethod()">
                    {{ m.value }}{{ m.disabled ? ' — disabled in Stockount' : '' }}
                  </option>
                }
              </select>
              <div class="fld-hint">FIFO and LIFO can't be chosen: Stockount has them disabled</div>
            </div>
            <div class="fld">
              <label class="fld-lbl">Accounting Mode</label>
              <select (change)="configStore.invAccountingMode.set(val($event))">
                @for (m of accountingModes; track m) {
                  <option [value]="m" [selected]="m === configStore.invAccountingMode()">{{ m }}</option>
                }
              </select>
            </div>
          </div>

          <div class="g g2 g-last">
            @for (f of accountFields(); track f.key) {
              <div class="fld">
                <label class="fld-lbl">{{ f.label }}</label>
                <input
                  type="text"
                  list="ig-accounts"
                  placeholder="Leave as is"
                  [value]="configStore.invAccounts()[f.key] || ''"
                  (input)="setKey(configStore.invAccounts, f.key, val($event))"
                />
                @if (listWarning(configStore.invAccounts()[f.key], accountNames, 'account'); as msg) {
                  <div class="fld-hint" style="color:var(--rose);">{{ msg }}</div>
                }
              </div>
            }
          </div>
          <div class="fld-hint">Pick a standard account or type another exact account name</div>
        </div>
      </div>

      <!-- Advanced -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title emerald-accent">
            <span class="card-icon">🎛️</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">Advanced</div>
              <div style="font-size:12px; color:var(--t3);">Additional configurations</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          @for (t of advancedToggles; track t.key) {
            <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; padding:6px 0;">
              <span style="font-size:13px; color:var(--t0);">{{ t.label }}</span>
              <select style="width:160px;" (change)="setToggle(t.key, val($event))">
                @for (s of toggleStates; track s.key) {
                  <option [value]="s.key" [selected]="s.key === toggleState(t.key)">{{ s.label }}</option>
                }
              </select>
            </div>
          }
        </div>
      </div>

      <!-- UOM Conversions -->
      <div class="card" style="margin-bottom:20px;">
        <div class="card-hd">
          <div class="card-title emerald-accent">
            <span class="card-icon">⚖️</span>
            <div>
              <div style="font-weight:700; font-size:15px; color:var(--t0);">UOM Conversions</div>
              <div style="font-size:12px; color:var(--t3);">Primary, Secondary and Tertiary units</div>
            </div>
          </div>
        </div>

        <div class="card-body">
          <div class="g g2">
            <div class="fld">
              <label class="fld-lbl">Enable UOM Conversions</label>
              <select (change)="configStore.invUomMode.set($any(val($event)))">
                @for (s of toggleStates; track s.key) {
                  <option [value]="s.key" [selected]="s.key === configStore.invUomMode()">{{ s.label }}</option>
                }
              </select>
            </div>
          </div>

          @if (configStore.invUomMode() === 'on') {
            <div class="g g2">
              <div class="fld">
                <label class="fld-lbl">Primary UOM <span class="req">*</span></label>
                <input
                  type="text"
                  list="ig-uoms"
                  [value]="configStore.invPrimaryUom()"
                  (input)="configStore.invPrimaryUom.set(val($event))"
                  placeholder="Bale"
                />
                @if (listWarning(configStore.invPrimaryUom(), uomNames, 'UOM'); as msg) {
                  <div class="fld-hint" style="color:var(--rose);">{{ msg }}</div>
                }
              </div>
              <div class="fld">
                <label class="fld-lbl">Value Type</label>
                <select (change)="configStore.invUomValueType.set(val($event))">
                  <option value="" [selected]="!configStore.invUomValueType()">Leave as is</option>
                  @for (v of uomValueTypes; track v) {
                    <option [value]="v" [selected]="v === configStore.invUomValueType()">{{ v }}</option>
                  }
                </select>
              </div>
            </div>

            @for (level of uomLevels; track level) {
              <div class="am-sec-lbl" style="margin-top:14px;">{{ level }} UOMs — 1 UOM = quantity × base</div>
              @for (row of uomRows(level)(); track $index; let i = $index) {
                <div style="display:flex; gap:8px; align-items:center; margin-top:8px; flex-wrap:wrap;">
                  <span>1</span>
                  <input
                    type="text"
                    list="ig-uoms"
                    style="width:150px;"
                    placeholder="UOM"
                    [value]="row.uom"
                    (input)="patchRow(level, i, { uom: val($event) })"
                  />
                  <span>=</span>
                  <input
                    type="number"
                    min="0"
                    step="any"
                    style="width:110px;"
                    placeholder="Qty"
                    [value]="row.quantity ?? ''"
                    (input)="patchRow(level, i, { quantity: num($event) })"
                  />
                  <select style="width:170px;" (change)="patchRow(level, i, { base: val($event) })">
                    <option value="" [selected]="!row.base">Primary ({{ configStore.invPrimaryUom() || '—' }})</option>
                    @for (b of baseOptions(level, i); track $index) {
                      <option [value]="b" [selected]="b === row.base">{{ b }}</option>
                    }
                  </select>
                  <button type="button" class="btn btn-ghost" title="Remove" (click)="removeAt(uomRows(level), i)">✕</button>
                </div>
                @if (listWarning(row.uom, uomNames, 'UOM'); as msg) {
                  <div class="fld-hint" style="color:var(--rose); margin-left:14px;">{{ msg }}</div>
                }
              }
              <button type="button" class="btn btn-ghost" style="margin-top:8px;" (click)="append(uomRows(level), newRow())">
                + Add {{ level }} UOM
              </button>
            }

            <div class="g g2 g-last" style="margin-top:14px;">
              <div class="fld">
                <label class="fld-lbl">Default UOM</label>
                <select (change)="configStore.invDefaultUom.set(val($event))">
                  <option value="" [selected]="!configStore.invDefaultUom()">Primary ({{ configStore.invPrimaryUom() || '—' }})</option>
                  @for (u of defaultOptions(); track $index) {
                    <option [value]="u" [selected]="u === configStore.invDefaultUom()">{{ u }}</option>
                  }
                </select>
              </div>
            </div>
          }
        </div>
      </div>

      <datalist id="ig-accounts">
        @for (a of accountNames; track a) { <option [value]="a"></option> }
      </datalist>
      <datalist id="ig-uoms">
        @for (u of uomNames; track u) { <option [value]="u"></option> }
      </datalist>

      <!-- Navigation Row -->
      <div class="nav-row">
        <button
          type="button"
          class="btn btn-ghost"
          (click)="registryStore.selectModuleForEditing(10)"
        >
          ← Table · Summary · Recent
        </button>
        <button
          type="button"
          class="btn-primary"
          style="background: linear-gradient(135deg, #10b981, #059669);"
          (click)="registryStore.selectModuleForEditing(14)"
        >
          Location Setup →
        </button>
      </div>
    </div>
  `
})
export class M13CreateGroupComponent {
  readonly configStore = inject(RunConfigStore);
  readonly registryStore = inject(ModuleRegistryStore);

  readonly inventoryTypes = INVENTORY_TYPES;
  readonly barcodeFieldTypes = BARCODE_FIELD_TYPES;
  readonly costingMethods = COSTING_METHODS;
  readonly accountingModes = ACCOUNTING_MODES;
  readonly advancedToggles = ADVANCED_TOGGLES;
  readonly uomNames = UOM_NAMES;
  readonly uomValueTypes = UOM_VALUE_TYPES;
  readonly uomLevels: UomLevel[] = ['Secondary', 'Tertiary'];
  readonly toggleStates: Option[] = [
    { key: 'leave', label: 'Leave as is' },
    { key: 'on', label: 'On' },
    { key: 'off', label: 'Off' },
  ];

  readonly accountFields = computed(() => ACCOUNT_FIELDS[this.configStore.invAccountingMode()] || []);
  readonly accountNames = ACCOUNT_NAMES;
  readonly idsText = computed(() => this.configStore.invIds().join('\n'));
  readonly defaultOptions = computed(() =>
    [...this.configStore.invSecondaryUoms(), ...this.configStore.invTertiaryUoms()].map(r => r.uom).filter(Boolean)
  );

  /* Common input helpers */
  val(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }

  num(e: Event): number | null {
    const text = this.val(e).trim();
    return text === '' ? null : Number(text);
  }

  /** Warning for a typed value that isn't one of the list's choices; null when it is (or when blank). */
  listWarning(value: string | null | undefined, list: readonly string[], what: string): string | null {
    return value && !list.includes(value) ? `⚠ "${value}" is not in the ${what} list` : null;
  }

  /** Set one key of a map signal; a blank value removes the key (leave as is). */
  setKey<T>(sig: WritableSignal<Record<string, T>>, key: string, value: T | ''): void {
    sig.update(map => {
      const next = { ...map };
      if (value === '') {
        delete next[key];
      } else {
        next[key] = value;
      }
      return next;
    });
  }

  setAt<T>(sig: WritableSignal<T[]>, i: number, value: T): void {
    sig.update(list => list.map((x, j) => (j === i ? value : x)));
  }

  removeAt<T>(sig: WritableSignal<T[]>, i: number): void {
    sig.update(list => list.filter((_, j) => j !== i));
  }

  append<T>(sig: WritableSignal<T[]>, item: T): void {
    sig.update(list => [...list, item]);
  }

  /* Field-specific wiring on top of the common helpers */
  setIds(e: Event): void {
    this.configStore.invIds.set(this.val(e).split('\n').map(l => l.trim()).filter(Boolean));
  }

  toggleState(key: string): ToggleState {
    return this.configStore.invAdvanced()[key] ?? 'leave';
  }

  setToggle(key: string, state: string): void {
    this.setKey(this.configStore.invAdvanced, key, state === 'leave' ? '' : (state as ToggleState));
  }

  uomRows(level: UomLevel): WritableSignal<UomRow[]> {
    return level === 'Secondary' ? this.configStore.invSecondaryUoms : this.configStore.invTertiaryUoms;
  }

  patchRow(level: UomLevel, i: number, patch: Partial<UomRow>): void {
    const rows = this.uomRows(level);
    this.setAt(rows, i, { ...rows()[i], ...patch });
  }

  newRow(): UomRow {
    return { uom: '', quantity: null, base: '' };
  }

  /** UOMs a row can convert to besides the Primary: the ones configured before it. */
  baseOptions(level: UomLevel, i: number): string[] {
    const secondary = this.configStore.invSecondaryUoms().map(r => r.uom);
    const earlier = level === 'Secondary'
      ? secondary.slice(0, i)
      : [...secondary, ...this.configStore.invTertiaryUoms().slice(0, i).map(r => r.uom)];
    return earlier.filter(Boolean);
  }
}
