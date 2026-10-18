import { Injectable, inject, signal } from '@angular/core';
import { ModuleRegistryStore } from './module-registry.store';
import { QueueStore } from './queue.store';
import { RunConfig } from '../core/models/run-config.model';

@Injectable({
  providedIn: 'root'
})
export class RunConfigStore {
  private readonly registryStore = inject(ModuleRegistryStore);
  private readonly queueStore = inject(QueueStore);

  /* Uploaded file paths map (e.g. OA_EXCEL, EXCEL_PATH, IMPORT_EXCEL) */
  readonly uploadedPaths = signal<Record<string, string>>({});

  /* General Settings */
  readonly defaultTimeout = signal<number>(10000);
  readonly shortTimeout = signal<number>(5000);
  readonly waitAfterAction = signal<number>(300);
  readonly browsername = signal<string>('chrome');
  readonly environments = signal<string>('QA');
  readonly branch = signal<string>('gr');

  /* Custom Login Credentials */
  readonly useCustomLogin = signal<boolean>(false);
  readonly email = signal<string>('');
  readonly password = signal<string>('');
  readonly companyName = signal<string>('');

  /* Auditor 2 Credentials */
  readonly email2 = signal<string>('');
  readonly password2 = signal<string>('');

  /* Audit Mode & Sub-flags */
  readonly auditMode = signal<'Audit_plan' | 'Ad_hoc'>('Audit_plan');
  readonly apAuditType = signal<string>('Complete Count');
  readonly ahAuditTypeMain = signal<string>('Complete Audit');
  readonly ahAuditType = signal<string>('Dynamic');
  readonly cbTz = signal<boolean>(false);
  readonly cbCa = signal<boolean>(true);
  readonly cbUa = signal<boolean>(false);
  readonly cbAdhocRun = signal<boolean>(true);
  readonly cbNai2 = signal<boolean>(false);

  /* Q_Setting */
  readonly qsAuditName = signal<string>('Audit_TEST');
  readonly qsA1 = signal<string>('');
  readonly qsA2 = signal<string>('');
  readonly qsA3 = signal<string>('');
  readonly qsCbDamaged = signal<boolean>(false);
  readonly qsCbStock = signal<boolean>(false);
  readonly qsCbGeo = signal<boolean>(false);
  readonly qsCbPhoto = signal<boolean>(false);
  readonly qsSheet = signal<string>('');

  /* Global Excel & Auditor Mapping */
  readonly auditorMappingType = signal<string>('Random');
  readonly excelSheetAuditorMapping = signal<string>('');
  readonly excelAuditorCol = signal<string>('Auditor');
  readonly excelCategoryCol = signal<string>('Category');
  readonly excelStorageCol = signal<string>('Storage');

  /* Stock Audit A1 (Auditor 1) */
  readonly location1 = signal<string>('SA-A1');
  readonly code1 = signal<string>('ABC1123');
  readonly audQty1 = signal<number>(0);
  readonly damQty1 = signal<number>(0);
  readonly cbRunNewAddItem = signal<boolean>(false);
  readonly asaItemCode = signal<string>('ABC1123');
  readonly asaItemName = signal<string>('Test Item');
  readonly asaCategory = signal<string>('Gear');
  readonly asaCp = signal<string>('100');
  readonly asaSp = signal<string>('100');
  readonly asaLocation = signal<string>('SA-A1');
  readonly asaBarcode = signal<string>('123456789');
  readonly asaUom = signal<string>('PCS');
  readonly asaAudQty = signal<number>(10);
  readonly asaDamQty = signal<number>(0);
  readonly asaSheet = signal<string>('auditor_1');
  readonly asaLocCol = signal<string>('locations');
  readonly asaCodeCol = signal<string>('code');
  readonly asaAudCol = signal<string>('audited');
  readonly asaDamCol = signal<string>('damaged');

  /* Stock Audit A2 (Auditor 2) */
  readonly location2 = signal<string>('SA-A1');
  readonly code2 = signal<string>('ABC1123');
  readonly audQty2 = signal<number>(0);
  readonly damQty2 = signal<number>(0);
  readonly asa2ItemCode = signal<string>('ABC1123');
  readonly asa2ItemName = signal<string>('Test Item');
  readonly asa2Category = signal<string>('Gear');
  readonly asa2Cp = signal<string>('100');
  readonly asa2Sp = signal<string>('100');
  readonly asa2Location = signal<string>('SA-A1');
  readonly asa2Barcode = signal<string>('123456789');
  readonly asa2Uom = signal<string>('PCS');
  readonly asa2AudQty = signal<number>(10);
  readonly asa2DamQty = signal<number>(0);
  readonly asa2Sheet = signal<string>('auditor_2');
  readonly asa2LocCol = signal<string>('locations');
  readonly asa2CodeCol = signal<string>('code');
  readonly asa2AudCol = signal<string>('audited');
  readonly asa2DamCol = signal<string>('damaged');

  /* Reports / Summary */
  readonly excelSheetAuditSummary = signal<string>('auditSummary');
  readonly filterColumn = signal<string>('filter');
  readonly excelSheetAsTable = signal<string>('as_table');
  readonly excelSheetRecentlyAudit = signal<string>('Recently_Audit');

  /* Audit Plan details */
  readonly apOwner = signal<string>('Dinesh B');
  readonly apAuditor1 = signal<string>('');
  readonly apAuditor2 = signal<string>('');
  readonly apGroup = signal<string>('');
  readonly apAuditName = signal<string>('Audit_TEST');
  readonly apFrequency = signal<string>('one-time');
  readonly apDays = signal<number>(30);
  readonly apTargetDay = signal<string>('Thursday');
  readonly apTargetDate = signal<string>('05/03/2026');
  readonly apCbDamaged = signal<boolean>(false);
  readonly apCbStock = signal<boolean>(false);
  readonly apCbGeo = signal<boolean>(false);
  readonly apPhotoType = signal<string>('None');
  readonly apSampleSize = signal<number>(0);
  readonly apCrossType = signal<string>('Random Recheck');
  readonly apCrossAuditor = signal<string>('Dinesh');
  readonly ahAuditor1 = signal<string>('');
  readonly ahAuditor2 = signal<string>('');
  readonly ahGroup = signal<string>('');
  readonly ahAuditName = signal<string>('');

  /* Ongoing Audit */
  readonly oaGroupName = signal<string>('');
  readonly oaAuditName = signal<string>('');
  readonly oaEmail = signal<string>('');
  readonly oaPassword = signal<string>('');
  readonly oaSheet = signal<string>('Data');
  readonly oaAuditor1 = signal<string>('');
  readonly oaAuditor2 = signal<string>('');
  readonly oaCbDamaged = signal<boolean>(false);
  readonly oaCbStock = signal<boolean>(false);
  readonly oaCbGeo = signal<boolean>(false);
  readonly oaPhotoType = signal<string>('None');
  readonly oaSampleSize = signal<number>(0);
  readonly oaMapping = signal<string>('{}');
  readonly oaMappingType = signal<string>('');
  readonly oaMappingSheet = signal<string>('');
  readonly oaAuditorCol = signal<string>('');
  readonly oaCategoryCol = signal<string>('');
  readonly oaStorageCol = signal<string>('');

  /* Inventory */
  readonly invGroupName = signal<string>('Group_34');
  readonly invType = signal<string>('Serialized');
  readonly invFields = signal<string[]>(['Item Code', 'Item Name']);
  readonly invIds = signal<string[]>(['Serial Number', 'IMEI', 'Barcode']);

  /* Location Setup */
  readonly lsZones = signal<string>('SA');
  readonly lsAisles = signal<string>('A1');
  readonly lsBays = signal<string>('B1');
  readonly lsLevels = signal<string>('L1');

  /* Import Items */
  readonly iiSheetName = signal<string>('Data');
  readonly cbRunAddItem = signal<boolean>(false);
  readonly cbQuickAdd = signal<boolean>(false);
  readonly cbImportExcel = signal<boolean>(false);
  readonly iiItemName = signal<string>('');
  readonly iiItemCode = signal<string>('');
  readonly iiItemUom = signal<string>('PCS');
  readonly iiCategory = signal<string>('');
  readonly iiTag = signal<string>('');
  readonly iiCp = signal<number>(0);
  readonly iiSp = signal<number>(0);
  readonly iiBarcode = signal<string>('');
  readonly iiDescription = signal<string>('');
  readonly iiTaxHsn = signal<string>('');
  readonly iiTax = signal<string>('');
  readonly iiReorderLimit = signal<string>('');

  setUploadedPath(key: string, path: string): void {
    const updated = { ...this.uploadedPaths(), [key]: path };
    this.uploadedPaths.set(updated);
  }

  private normalizeMappingType(val: string): string {
    const mapped = (val || '').trim();
    if (mapped === 'By Storage') return 'By Location';
    return mapped || 'Random';
  }

  /**
   * Serializes current state into RunConfig matching config.js exactly.
   */
  buildRunConfig(): RunConfig {
    const grp = this.registryStore.groupEnabled();
    const mod = this.registryStore.moduleEnabled();
    const up = this.uploadedPaths();
    const modules = this.registryStore.modules();

    const auditMode = this.auditMode();
    const apOn = !!grp[1];
    const tzOn = apOn && auditMode === 'Audit_plan' && this.cbTz();
    const caOn = apOn && auditMode === 'Audit_plan' && this.cbCa();
    const uaOn = apOn && auditMode === 'Audit_plan' && this.cbUa();
    const ahOn = apOn && auditMode === 'Ad_hoc' && this.cbAdhocRun();

    const idxToName: Record<number, string> = {};
    const runFlags: Record<string, boolean> = {};

    modules.forEach(m => {
      idxToName[m.idx] = m.flag;
      const isEnabled = !!(grp[m.group] && mod[m.idx]);
      runFlags[m.flag] = isEnabled;

      if (m.idx === 6) {
        runFlags[m.flag] = isEnabled && caOn;
        runFlags['run_timezone'] = isEnabled && tzOn;
        runFlags['run_create_Ad_hoc_Audit'] = isEnabled && ahOn;
        runFlags['run_update_audit'] = isEnabled && uaOn;
      }
    });

    const order = this.queueStore.getRunOrder();
    const activeModuleFlags = order.map(i => idxToName[i]).filter(Boolean);

    const runNewAddItem = !!(grp[1] && mod[8] && this.cbRunNewAddItem());
    const runNewAddItem2 = !!(grp[1] && mod[9] && this.cbNai2());

    let parsedOaMapping = {};
    try {
      parsedOaMapping = JSON.parse(this.oaMapping() || '{}');
    } catch {
      parsedOaMapping = {};
    }

    const mappingType = this.normalizeMappingType(
      this.oaMappingType() || this.auditorMappingType()
    );

    return {
      DEFAULT_TIMEOUT: this.defaultTimeout() || 10000,
      SHORT_TIMEOUT: this.shortTimeout() || 5000,
      WAIT_AFTER_ACTION: this.waitAfterAction() || 300,

      browsername: this.browsername() || 'chrome',
      environments: this.environments() || 'QA',
      Branch: this.branch() || 'gr',

      USE_CUSTOM_LOGIN: this.useCustomLogin(),
      email: this.email() || null,
      password: this.password() || null,
      company_name: this.companyName() || null,

      run_Q_audit: !!grp[0],
      run_Audit_plan: !!grp[1],
      run_inventory: !!grp[2],

      MODULE_RUN_ORDER: order,
      modules: activeModuleFlags,

      ...runFlags,
      run_new_add_item: runNewAddItem,
      run_new_add_item2: runNewAddItem2,

      Audit_mode: auditMode,
      Audit_Type:
        auditMode === 'Ad_hoc'
          ? this.ahAuditTypeMain() || 'Complete Audit'
          : this.apAuditType() || 'Complete Count',
      SD_audit_type: this.ahAuditType() || 'Dynamic',

      /* Q_Setting */
      audit_name: this.qsAuditName() || 'Audit_TEST',
      Auditor_name1: this.qsA1() || null,
      Auditor_name2: this.qsA2() || null,
      Auditor_name3: this.qsA3() || null,
      Checkboxes_Audit_Damaged: this.qsCbDamaged(),
      Checkboxes_StockItems: this.qsCbStock(),
      Checkboxes_geo: this.qsCbGeo(),
      Checkboxes_photo: this.qsCbPhoto(),
      qs_sheet: this.qsSheet(),

      /* Global Excel / Mapping */
      EXCEL_PATH: up['OA_EXCEL'] || up['EXCEL_PATH'] || '',
      AUDITOR_MAPPING_TYPE: mappingType,
      AUDIT_MAPPING_TYPE: mappingType,
      EXCEL_SHEET_AUDITOR_MAPPING:
        this.oaMappingSheet() || this.excelSheetAuditorMapping() || '',
      EXCEL_auditor_col:
        this.oaAuditorCol() || this.excelAuditorCol() || 'Auditor',
      EXCEL_category_col:
        this.oaCategoryCol() || this.excelCategoryCol() || 'Category',
      EXCEL_storage_col:
        this.oaStorageCol() || this.excelStorageCol() || 'Storage',

      /* Stock Audit A1 */
      location1: this.location1() || 'SA-A1',
      code1: this.code1() || 'ABC1123',
      aud_qty1: this.audQty1() || 0,
      dam_qty1: this.damQty1() || 0,
      ITEM_CODE1: this.asaItemCode() || 'ABC1123',
      ITEM_NAME1: this.asaItemName() || 'Test Item',
      CATEGORY1: this.asaCategory() || 'Gear',
      COST_PRICE1: this.asaCp() || '100',
      SELL_PRICE1: this.asaSp() || '100',
      LOCATION1: this.asaLocation() || 'SA-A1',
      BARCODE1: this.asaBarcode() || '123456789',
      UOM1: this.asaUom() || 'PCS',
      audited_qty1: this.asaAudQty() || 10,
      damaged_qty1: this.asaDamQty() || 0,
      EXCEL_SHEET_auditor_1: this.asaSheet() || 'auditor_1',
      EXCEL_LOCATION_COL1: this.asaLocCol() || 'locations',
      EXCEL_CODE_COL1: this.asaCodeCol() || 'code',
      EXCEL_AUDITED_COL1: this.asaAudCol() || 'audited',
      EXCEL_DAMAGED_COL1: this.asaDamCol() || 'damaged',

      /* Stock Audit A2 */
      location2: this.location2() || 'SA-A1',
      code2: this.code2() || 'ABC1123',
      aud_qty2: this.audQty2() || 0,
      dam_qty2: this.damQty2() || 0,
      ITEM_CODE2: this.asa2ItemCode() || 'ABC1123',
      ITEM_NAME2: this.asa2ItemName() || 'Test Item',
      CATEGORY2: this.asa2Category() || 'Gear',
      COST_PRICE2: this.asa2Cp() || '100',
      SELL_PRICE2: this.asa2Sp() || '100',
      LOCATION2: this.asa2Location() || 'SA-A1',
      BARCODE2: this.asa2Barcode() || '123456789',
      UOM2: this.asa2Uom() || 'PCS',
      audited_qty2: this.asa2AudQty() || 10,
      damaged_qty2: this.asa2DamQty() || 0,
      EXCEL_SHEET_auditor_2: this.asa2Sheet() || 'auditor_2',
      EXCEL_LOCATION_COL2: this.asa2LocCol() || 'locations',
      EXCEL_CODE_COL2: this.asa2CodeCol() || 'code',
      EXCEL_AUDITED_COL2: this.asa2AudCol() || 'audited',
      EXCEL_DAMAGED_COL2: this.asa2DamCol() || 'damaged',
      email2: this.email2() || null,
      password2: this.password2() || null,

      /* Reports / Summary */
      EXCEL_SHEET_audit_Summary:
        this.excelSheetAuditSummary() || 'auditSummary',
      FILTER_COLUMN: this.filterColumn() || 'filter',
      EXCEL_SHEET_as_table: this.excelSheetAsTable() || 'as_table',
      EXCEL_SHEET_Recently_Audit:
        this.excelSheetRecentlyAudit() || 'Recently_Audit',

      /* Audit Plan */
      Audit_Owner: this.apOwner() || 'Dinesh B',
      Auditor1: this.apAuditor1() || '',
      Auditor2: this.apAuditor2() || '',
      Group_Name: this.apGroup() || '',
      Day_s: this.apDays() || 30,
      Target__Day: this.apTargetDay() || 'Thursday',
      Target_Date: this.apTargetDate() || '05/03/2026',
      A_Checkboxes_Audit_Damaged: this.apCbDamaged(),
      A_Checkboxes_BlindCount: this.apCbStock(),
      A_Checkboxes_geo: this.apCbGeo(),
      photo_type: this.apPhotoType() || 'None',
      sample_size: this.apSampleSize() || 0,
      CROSS_AUDIT_TYPE: this.apCrossType() || 'Random Recheck',
      CROSS_Auditor_name: this.apCrossAuditor() || 'Dinesh',
      Auditor1_adhoc: this.ahAuditor1() || '',
      Auditor2_adhoc: this.ahAuditor2() || '',
      Group_Name_adhoc: this.ahGroup() || '',
      ap_audit_name_adhoc: this.ahAuditName() || '',

      /* Ongoing Audit */
      oa_group_name: this.oaGroupName() || '',
      ap_audit_name: this.oaAuditName() || this.apAuditName() || '',
      Frequency: this.apFrequency() || 'one-time',
      oa_email: this.oaEmail() || null,
      oa_password: this.oaPassword() || null,
      oa_excel_path: up['OA_EXCEL'] || up['EXCEL_PATH'] || '',
      oa_sheet: this.oaSheet() || 'Data',
      oa_Auditor1: this.oaAuditor1() || '',
      oa_Auditor2: this.oaAuditor2() || '',
      oa_A_Checkboxes_Audit_Damaged: this.oaCbDamaged(),
      oa_A_Checkboxes_StockItems: this.oaCbStock(),
      oa_A_Checkboxes_geo: this.oaCbGeo(),
      oa_photo_type: this.oaPhotoType() || 'None',
      oa_sample_size: this.oaSampleSize() || 0,
      oa_mapping: parsedOaMapping,

      /* Inventory */
      inv_group_name: this.invGroupName() || 'Group_34',
      inventory_type: this.invType() || 'Serialized',
      inv_fields: this.invFields(),
      inv_ids: this.invIds(),

      /* Location Setup */
      ls_zones: this.lsZones() || 'SA',
      ls_aisles: this.lsAisles() || 'A1',
      ls_bays: this.lsBays() || 'B1',
      ls_levels: this.lsLevels() || 'L1',

      /* Import Items */
      EXCEL_FILE: up['IMPORT_EXCEL'] || '',
      sheet_name: this.iiSheetName() || 'Data',
      run_add_item: this.cbRunAddItem(),
      run_quick_add_items: this.cbQuickAdd(),
      run_import_items: this.cbImportExcel(),
      Item_Name: this.iiItemName() || '',
      Item_Code: this.iiItemCode() || '',
      Item_UOM: this.iiItemUom() || 'PCS',
      Item_Category: this.iiCategory() || '',
      Item_Tag: this.iiTag() || '',
      Item_CP: this.iiCp() || 0,
      Item_SP: this.iiSp() || 0,
      Item_Barcode: this.iiBarcode() || '',
      Item_Description: this.iiDescription() || '',
      Item_TaxHsn: this.iiTaxHsn() || '',
      Item_Tax: this.iiTax() || '',
      Item_ReorderLimit: this.iiReorderLimit() || '',

      /* Legacy aliases */
      asa_sheet: this.asaSheet() || 'auditor_1',
      asa_loc_col: this.asaLocCol() || 'locations',
      asa_code_col: this.asaCodeCol() || 'code',
      asa_aud_col: this.asaAudCol() || 'audited',
      asa_dam_col: this.asaDamCol() || 'damaged',
    };
  }
}
