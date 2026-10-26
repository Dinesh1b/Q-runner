/**
 * run-config.model.ts
 * Strongly typed interface for runner configuration matching backend config_builder.py
 */

import { UomRow } from './item-group.model';

export interface RunConfig {
  /* Timeouts & Engine */
  DEFAULT_TIMEOUT: number;
  SHORT_TIMEOUT: number;
  WAIT_AFTER_ACTION: number;

  /* Environment & Browser */
  browsername: 'chrome' | 'edge' | 'firefox' | string;
  environments: 'QA' | 'DEV' | 'PROD' | string;
  Branch: string;

  /* Credentials */
  USE_CUSTOM_LOGIN: boolean;
  email: string | null;
  password: string | null;
  company_name: string | null;

  /* Auditor 2 Credentials */
  email2: string | null;
  password2: string | null;

  /* High-Level Group Flags */
  run_Q_audit: boolean;
  run_Audit_plan: boolean;
  run_inventory: boolean;

  /* Dynamic Modules & Queue Order */
  MODULE_RUN_ORDER: number[];
  modules: string[];

  /* Dynamic Module Flags (e.g., run_Q_setting, run_create_audit, run_A_SA_table, etc.) */
  [moduleFlag: string]: unknown;

  /* Audit Mode & Types */
  Audit_mode: 'Audit_plan' | 'Ad_hoc' | string;
  Audit_Type: string;
  SD_audit_type: string;

  /* Q_Setting */
  audit_name: string;
  Auditor_name1: string | null;
  Auditor_name2: string | null;
  Auditor_name3: string | null;
  Checkboxes_Audit_Damaged: boolean;
  Checkboxes_StockItems: boolean;
  Checkboxes_geo: boolean;
  Checkboxes_photo: boolean;
  qs_sheet?: string;

  /* Excel & Mapping */
  EXCEL_PATH: string;
  AUDITOR_MAPPING_TYPE: string;
  AUDIT_MAPPING_TYPE?: string;
  EXCEL_SHEET_AUDITOR_MAPPING: string;
  EXCEL_auditor_col: string;
  EXCEL_category_col: string;
  EXCEL_storage_col: string;

  /* Stock Audit A1 (Auditor 1) */
  location1: string;
  code1: string;
  aud_qty1: number;
  dam_qty1: number;
  ITEM_CODE1: string;
  ITEM_NAME1: string;
  CATEGORY1: string;
  COST_PRICE1: string;
  SELL_PRICE1: string;
  LOCATION1: string;
  BARCODE1: string;
  UOM1: string;
  audited_qty1: number;
  damaged_qty1: number;
  EXCEL_SHEET_auditor_1: string;
  EXCEL_LOCATION_COL1: string;
  EXCEL_CODE_COL1: string;
  EXCEL_AUDITED_COL1: string;
  EXCEL_DAMAGED_COL1: string;

  /* Stock Audit A2 (Auditor 2) */
  location2: string;
  code2: string;
  aud_qty2: number;
  dam_qty2: number;
  ITEM_CODE2: string;
  ITEM_NAME2: string;
  CATEGORY2: string;
  COST_PRICE2: string;
  SELL_PRICE2: string;
  LOCATION2: string;
  BARCODE2: string;
  UOM2: string;
  audited_qty2: number;
  damaged_qty2: number;
  EXCEL_SHEET_auditor_2: string;
  EXCEL_LOCATION_COL2: string;
  EXCEL_CODE_COL2: string;
  EXCEL_AUDITED_COL2: string;
  EXCEL_DAMAGED_COL2: string;

  /* Reports / Summary */
  EXCEL_SHEET_audit_Summary: string;
  FILTER_COLUMN: string;
  EXCEL_SHEET_as_table: string;
  EXCEL_SHEET_Recently_Audit: string;

  /* Audit Plan details */
  Audit_Owner: string;
  Auditor1: string;
  Auditor2: string;
  Group_Name: string;
  Day_s: number;
  Target__Day: string;
  Target_Date: string;
  A_Checkboxes_Audit_Damaged: boolean;
  A_Checkboxes_BlindCount: boolean;
  A_Checkboxes_geo: boolean;
  photo_type: string;
  sample_size: number;
  CROSS_AUDIT_TYPE: string;
  CROSS_Auditor_name: string;

  Auditor1_adhoc: string;
  Auditor2_adhoc: string;
  Group_Name_adhoc: string;
  ap_audit_name_adhoc: string;

  /* Ongoing Audit */
  oa_group_name: string;
  ap_audit_name: string;
  oa_email: string | null;
  oa_password: string | null;
  oa_excel_path: string;
  oa_sheet: string;
  oa_Auditor1: string;
  oa_Auditor2: string;
  oa_A_Checkboxes_Audit_Damaged: boolean;
  oa_A_Checkboxes_StockItems: boolean;
  oa_A_Checkboxes_geo: boolean;
  oa_photo_type: string;
  oa_sample_size: number;
  oa_mapping: Record<string, unknown>;

  /* Inventory */
  inv_group_name: string;
  inventory_type: string;
  inv_fields: string[];
  inv_ids: string[];
  inv_accounting_mode?: string | null;
  inv_costing_method?: string | null;
  inv_accounting_accounts?: Record<string, string>;
  inv_advanced_toggles?: Record<string, boolean>;
  inv_enable_uom_conversions?: boolean | null;
  inv_primary_uom?: string | null;
  inv_uom_value_type?: string | null;
  inv_secondary_uoms?: UomRow[];
  inv_tertiary_uoms?: UomRow[];
  inv_default_uom?: string | null;

  /* Location Setup */
  ls_zones: string;
  ls_aisles: string;
  ls_bays: string;
  ls_levels: string;
  ls_run_setup?: boolean;
  ls_run_tests?: boolean;
  ls_test_groups?: string[];
  ls_test_cases?: string;
  ls_test_prefix?: string;
  ls_test_cleanup?: boolean;

  /* Import Items */
  EXCEL_FILE: string;
  sheet_name: string;
  run_add_item: boolean;
  run_quick_add_items: boolean;
  run_import_items: boolean;
  Item_Name: string;
  Item_Code: string;
  Item_UOM: string;
  Item_Category: string;
  Item_Tag: string;
  Item_CP: number;
  Item_SP: number;
  Item_Barcode: string;
  Item_Description: string;
  Item_TaxHsn: string;
  Item_Tax: string;
  Item_ReorderLimit: string;

  /* Legacy field aliases */
  asa_sheet?: string;
  asa_loc_col?: string;
  asa_code_col?: string;
  asa_aud_col?: string;
  asa_dam_col?: string;
}

export interface ExcelInspectResponse {
  ok: boolean;
  sheets?: string[];
  columns?: Record<string, string[]>;
  filename?: string;
  path?: string;
  error?: string;
}

export interface UploadResponse {
  ok: boolean;
  path?: string;
  filename?: string;
  original_name?: string;
  error?: string;
}
