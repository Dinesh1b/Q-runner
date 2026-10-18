/* ═══════════════════════════════════════════════════════════════
   Q-ARunner — json_import.js
   JSON Configuration Import module.
   Validates JSON configs against a schema, maps nested properties
   to existing UI controls, and applies values atomically.

   Script load order: Load AFTER utils.js, config.js, app.js.

   SECURITY:
     • Passwords & secrets are never logged or shown in summaries.
     • JSON is parsed only as data — never eval'd or executed.
     • Parsing is fully separate from Playwright test execution.
═══════════════════════════════════════════════════════════════ */
'use strict';

if (window.__QA_JSON_IMPORT_LOADED__) {
  console.warn('[QA] json_import.js already loaded — skipping.');
} else {
  window.__QA_JSON_IMPORT_LOADED__ = true;

  const $ = id => document.getElementById(id);

  /* ─────────────────────────────────────────────
     SUPPORTED CONFIG VERSION
  ───────────────────────────────────────────── */
  const SUPPORTED_VERSIONS = ['1.0'];

  /* ─────────────────────────────────────────────
     SECRET FIELDS — never logged/displayed
  ───────────────────────────────────────────── */
  const SECRET_PATHS = new Set([
    'test_data.password',
    'test_data.password2',
    'test_data.oa_password',
    'test_data.asa2_password',
  ]);

  /* ─────────────────────────────────────────────
     JSON SCHEMA DEFINITION
     Validates structure, types, required fields,
     and permitted values before any UI binding.
  ───────────────────────────────────────────── */
  const SCHEMA = {
    type: 'object',
    required: ['config_version'],
    additionalProperties: false,
    properties: {
      config_version: { type: 'string', enum: SUPPORTED_VERSIONS },
      project: {
        type: 'object',
        additionalProperties: false,
        properties: {
          name: { type: 'string' },
          environment: { type: 'string', enum: ['PRODUCTION', 'STAGING', 'QA', 'DEV'] },
          base_url: { type: 'string' },
        },
      },
      execution: {
        type: 'object',
        additionalProperties: false,
        properties: {
          browser: { type: 'string', enum: ['chrome', 'chromium', 'firefox', 'webkit'] },
          headless: { type: 'boolean' },
          timeout: { type: 'number', minimum: 0 },
          short_timeout: { type: 'number', minimum: 0 },
          wait_after_action: { type: 'number', minimum: 0 },
          retry_count: { type: 'number', minimum: 0 },
          branch: { type: 'string' },
          company_name: { type: 'string' },
        },
      },
      modules: {
        type: 'object',
        additionalProperties: true,
        patternProperties: {
          '.*': { type: 'boolean' },
        },
      },
      test_data: {
        type: 'object',
        additionalProperties: true,
        properties: {
          username: { type: 'string' },
          password: { type: 'string' },
          password2: { type: 'string' },
          email: { type: 'string' },
          email2: { type: 'string' },
          company_name: { type: 'string' },
          branch: { type: 'string' },
          location: { type: 'string' },
          location1: { type: 'string' },
          location2: { type: 'string' },
          item_name: { type: 'string' },
          item_code: { type: 'string' },
          quantity: { type: 'number' },
          unit: { type: 'string' },
          audit_name: { type: 'string' },
          auditor1: { type: 'string' },
          auditor2: { type: 'string' },
          auditor3: { type: 'string' },
          group_name: { type: 'string' },
          oa_group_name: { type: 'string' },
          oa_audit_name: { type: 'string' },
          oa_email: { type: 'string' },
          oa_password: { type: 'string' },
          inv_group_name: { type: 'string' },
          zones: { type: 'string' },
          aisles: { type: 'string' },
          bays: { type: 'string' },
          levels: { type: 'string' },
        },
      },
      field_mappings: {
        type: 'object',
        additionalProperties: true,
      },
      audit_config: {
        type: 'object',
        additionalProperties: true,
        properties: {
          audit_mode: { type: 'string', enum: ['Audit_plan', 'Ad_hoc'] },
          audit_type: { type: 'string' },
          audit_damaged: { type: 'boolean' },
          stock_count: { type: 'boolean' },
          geo_location: { type: 'boolean' },
          photo_capture: { type: 'boolean' },
          mapping_type: { type: 'string', enum: ['Random', 'By Category', 'By Storage'] },
          mapping_sheet: { type: 'string' },
          auditor_col: { type: 'string' },
          category_col: { type: 'string' },
          storage_col: { type: 'string' },
          frequency: { type: 'string' },
          days: { type: 'number' },
          target_day: { type: 'string' },
          target_date: { type: 'string' },
          cross_audit_type: { type: 'string' },
          cross_auditor: { type: 'string' },
          photo_type: { type: 'string', enum: ['None', 'Random', 'Damaged'] },
          sample_size: { type: 'number', minimum: 0 },
        },
      },
    },
  };

  /* ─────────────────────────────────────────────
     PATH → UI CONTROL MAPPING REGISTRY
     Maps JSON dot-paths to actual HTML element IDs
     and their control types.
     
     Control types:
       'input'    — text/number/password input
       'select'   — <select> dropdown
       'checkbox' — <input type="checkbox">
       'hidden'   — <input type="hidden">
       'env-btn'  — special: env button row
       'mode-card'— special: mode card selector
  ───────────────────────────────────────────── */
  const FIELD_MAP = {
    // ── Project ──
    'project.environment':     { id: 'environments',          type: 'select',   also: 'env-btn' },

    // ── Execution ──
    'execution.browser':       { id: 'browsername',           type: 'select'   },
    'execution.timeout':       { id: 'DEFAULT_TIMEOUT',       type: 'input'    },
    'execution.short_timeout': { id: 'SHORT_TIMEOUT',         type: 'input'    },
    'execution.wait_after_action': { id: 'WAIT_AFTER_ACTION', type: 'input'    },
    'execution.branch':        { id: 'branch',                type: 'input'    },
    'execution.company_name':  { id: 'company_name',          type: 'input'    },
    'execution.login':         { id: 'use_custom_login',     type: 'checkbox' },

    // ── Modules: Group Switches ──
    'modules.q_audit':         { id: 'grp-sw-0',             type: 'group-switch', group: 0 },
    'modules.run_q_audit':     { id: 'grp-sw-0',             type: 'group-switch', group: 0 },
    'modules.audit_plan':      { id: 'grp-sw-1',             type: 'group-switch', group: 1 },
    'modules.run_audit_plan':  { id: 'grp-sw-1',             type: 'group-switch', group: 1 },
    'modules.inventory':       { id: 'grp-sw-2',             type: 'group-switch', group: 2 },
    'modules.run_inventory':   { id: 'grp-sw-2',             type: 'group-switch', group: 2 },

    // ── Modules: Group 0 (Q Audit) ──
    'modules.q_setting':       { id: 'cb-qs',                type: 'module-cb', idx: 0 },
    'modules.run_q_setting':   { id: 'cb-qs',                type: 'module-cb', idx: 0 },
    'modules.stock_audit_a1':  { id: 'cb-sa1',               type: 'module-cb', idx: 1 },
    'modules.q_sa':            { id: 'cb-sa1',               type: 'module-cb', idx: 1 },
    'modules.run_q_sa':        { id: 'cb-sa1',               type: 'module-cb', idx: 1 },
    'modules.stock_audit_a2':  { id: 'cb-sa2',               type: 'module-cb', idx: 2 },
    'modules.q_sa1':           { id: 'cb-sa2',               type: 'module-cb', idx: 2 },
    'modules.run_q_sa1':       { id: 'cb-sa2',               type: 'module-cb', idx: 2 },
    'modules.summary_table':   { id: 'cb-sum',               type: 'module-cb', idx: 3 },
    'modules.q_as_table':      { id: 'cb-sum',               type: 'module-cb', idx: 3 },
    'modules.run_q_as_table':  { id: 'cb-sum',               type: 'module-cb', idx: 3 },
    'modules.recently_audited':{ id: 'cb-rec',               type: 'module-cb', idx: 4 },
    'modules.q_recently_audit':{ id: 'cb-rec',               type: 'module-cb', idx: 4 },
    'modules.run_q_recently_audit': { id: 'cb-rec',          type: 'module-cb', idx: 4 },
    'modules.q_audit_summary': { id: 'cb-qsum',              type: 'module-cb', idx: 5 },
    'modules.run_q_audit_summary': { id: 'cb-qsum',          type: 'module-cb', idx: 5 },

    // ── Modules: Group 1 (Audit Plan) ──
    'modules.audit':           { id: 'cb-ap',                type: 'module-cb', idx: 6 },
    'modules.audit_plan_module':{ id: 'cb-ap',               type: 'module-cb', idx: 6 },
    'modules.run_create_audit':{ id: 'cb-ap',                type: 'module-cb', idx: 6 },
    'modules.ongoing_audit':   { id: 'cb-oa',                type: 'module-cb', idx: 7 },
    'modules.run_setup_audit': { id: 'cb-oa',                type: 'module-cb', idx: 7 },
    'modules.auditor_1_sa':    { id: 'cb-asa',               type: 'module-cb', idx: 8 },
    'modules.stock_audit':     { id: 'cb-asa',               type: 'module-cb', idx: 8 },
    'modules.run_stock_audit': { id: 'cb-asa',               type: 'module-cb', idx: 8 },
    'modules.auditor_2_sa':    { id: 'cb-asa2',              type: 'module-cb', idx: 9 },
    'modules.stock_audit2':    { id: 'cb-asa2',              type: 'module-cb', idx: 9 },
    'modules.run_stock_audit2':{ id: 'cb-asa2',              type: 'module-cb', idx: 9 },
    'modules.a_as_table':      { id: 'cb-atab',              type: 'module-cb', idx: 10 },
    'modules.run_a_as_table':  { id: 'cb-atab',              type: 'module-cb', idx: 10 },
    'modules.a_audit_summary': { id: 'cb-asum',              type: 'module-cb', idx: 11 },
    'modules.run_a_audit_summary': { id: 'cb-asum',          type: 'module-cb', idx: 11 },
    'modules.a_recently_audit':{ id: 'cb-arec',              type: 'module-cb', idx: 12 },
    'modules.run_a_recently_audit': { id: 'cb-arec',         type: 'module-cb', idx: 12 },

    // ── Modules: Group 2 (Inventory) ──
    'modules.create_group':    { id: 'cb-cg',                type: 'module-cb', idx: 13 },
    'modules.run_create_group':{ id: 'cb-cg',                type: 'module-cb', idx: 13 },
    'modules.location_setup':  { id: 'cb-ls',                type: 'module-cb', idx: 14 },
    'modules.run_location_setup': { id: 'cb-ls',             type: 'module-cb', idx: 14 },
    'modules.import_items':    { id: 'cb-ii',                type: 'module-cb', idx: 15 },
    'modules.import_app':      { id: 'cb-ii',                type: 'module-cb', idx: 15 },
    'modules.run_import_app':  { id: 'cb-ii',                type: 'module-cb', idx: 15 },

    // ── Modules: Sub-features & Checkboxes ──
    'modules.login':           { id: 'use_custom_login',     type: 'checkbox'  },
    'modules.item_import':     { id: 'cb-import-excel',      type: 'checkbox'  },
    'modules.run_add_item':    { id: 'cb-run-add-item',      type: 'checkbox'  },
    'modules.quick_add':       { id: 'cb-quick-add',         type: 'checkbox'  },
    'modules.new_item':        { id: 'cb-new-item',          type: 'checkbox'  },
    'modules.nai2':            { id: 'cb-nai2',              type: 'checkbox'  },
    'modules.tz':              { id: 'cb-tz',                type: 'checkbox'  },
    'modules.ca':              { id: 'cb-ca',                type: 'checkbox'  },
    'modules.ua':              { id: 'cb-ua',                type: 'checkbox'  },
    'modules.adhoc_run':       { id: 'cb-adhoc-run',         type: 'checkbox'  },

    // ── Test Data: Credentials & General ──
    'test_data.email':         { id: 'email',                type: 'input'    },
    'test_data.username':      { id: 'email',                type: 'input'    },
    'test_data.password':      { id: 'password',             type: 'input',   secret: true },
    'test_data.email2':        { id: 'email2',               type: 'input'    },
    'test_data.password2':     { id: 'password2',            type: 'input',   secret: true },
    'test_data.company_name':  { id: 'company_name',         type: 'input'    },
    'test_data.branch':        { id: 'branch',               type: 'input'    },

    // ── Test Data: Q_Setting ──
    'test_data.audit_name':    { id: 'qs-audit-name',        type: 'input'    },
    'test_data.qs_branch':     { id: 'qs-branch',            type: 'input'    },
    'test_data.auditor1':      { id: 'qs-a1',                type: 'input'    },
    'test_data.auditor2':      { id: 'qs-a2',                type: 'input'    },
    'test_data.auditor3':      { id: 'qs-a3',                type: 'input'    },

    // ── Test Data: Stock Audit A1 & A2 ──
    'test_data.location':      { id: 'location1',            type: 'input'    },
    'test_data.location1':     { id: 'location1',            type: 'input'    },
    'test_data.code1':         { id: 'code1',                type: 'input'    },
    'test_data.quantity':      { id: 'aud_qty1',             type: 'input'    },
    'test_data.aud_qty1':      { id: 'aud_qty1',             type: 'input'    },
    'test_data.dam_qty1':      { id: 'dam_qty1',             type: 'input'    },
    'test_data.location2':     { id: 'location2',            type: 'input'    },
    'test_data.code2':         { id: 'code2',                type: 'input'    },
    'test_data.aud_qty2':      { id: 'aud_qty2',             type: 'input'    },
    'test_data.dam_qty2':      { id: 'dam_qty2',             type: 'input'    },

    // ── Test Data: Auditor 1 SA ──
    'test_data.item_name':     { id: 'asa-item-name',        type: 'input'    },
    'test_data.item_code':     { id: 'asa-item-code',        type: 'input'    },
    'test_data.unit':          { id: 'asa-uom',              type: 'input'    },
    'test_data.asa_category':  { id: 'asa-category',         type: 'input'    },
    'test_data.asa_cp':        { id: 'asa-cp',               type: 'input'    },
    'test_data.asa_sp':        { id: 'asa-sp',               type: 'input'    },
    'test_data.asa_location':  { id: 'asa-location',         type: 'input'    },
    'test_data.asa_barcode':   { id: 'asa-barcode',          type: 'input'    },
    'test_data.asa_aud_qty':   { id: 'asa-aud-qty',          type: 'input'    },
    'test_data.asa_dam_qty':   { id: 'asa-dam-qty',          type: 'input'    },

    // ── Test Data: Auditor 2 SA ──
    'test_data.asa2_email':    { id: 'asa2-email',           type: 'input'    },
    'test_data.asa2_password': { id: 'asa2-password',        type: 'input',   secret: true },
    'test_data.asa2_item_name':{ id: 'asa2-item-name',       type: 'input'    },
    'test_data.asa2_item_code':{ id: 'asa2-item-code',       type: 'input'    },
    'test_data.asa2_category': { id: 'asa2-category',        type: 'input'    },
    'test_data.asa2_cp':       { id: 'asa2-cp',              type: 'input'    },
    'test_data.asa2_sp':       { id: 'asa2-sp',              type: 'input'    },
    'test_data.asa2_uom':      { id: 'asa2-uom',             type: 'input'    },
    'test_data.asa2_location': { id: 'asa2-location',        type: 'input'    },
    'test_data.asa2_barcode':  { id: 'asa2-barcode',         type: 'input'    },
    'test_data.asa2_aud_qty':  { id: 'asa2-aud-qty',         type: 'input'    },
    'test_data.asa2_dam_qty':  { id: 'asa2-dam-qty',         type: 'input'    },

    // ── Test Data: Ongoing Audit ──
    'test_data.group_name':    { id: 'ap-group',             type: 'input'    },
    'test_data.oa_group_name': { id: 'oa-group-name',        type: 'input'    },
    'test_data.oa_audit_name': { id: 'oa-audit-name',        type: 'input'    },
    'test_data.oa_auditor1':   { id: 'oa-auditor1',          type: 'input'    },
    'test_data.oa_auditor2':   { id: 'oa-auditor2',          type: 'input'    },
    'test_data.oa_email':      { id: 'oa-email',             type: 'input'    },
    'test_data.oa_password':   { id: 'oa-password',          type: 'input',   secret: true },

    // ── Test Data: Inventory & Setup ──
    'test_data.inv_group_name':{ id: 'inv-group-name',       type: 'input'    },
    'test_data.zones':         { id: 'ls-zones',             type: 'input'    },
    'test_data.aisles':        { id: 'ls-aisles',            type: 'input'    },
    'test_data.bays':          { id: 'ls-bays',              type: 'input'    },
    'test_data.levels':        { id: 'ls-levels',            type: 'input'    },

    // ── Test Data: Import Items ──
    'test_data.ii_item_name':  { id: 'ii-item-name',         type: 'input'    },
    'test_data.ii_item_code':  { id: 'ii-item-code',         type: 'input'    },
    'test_data.ii_item_uom':   { id: 'ii-item-uom',          type: 'input'    },
    'test_data.ii_category':   { id: 'ii-category',          type: 'input'    },
    'test_data.ii_tag':        { id: 'ii-tag',               type: 'input'    },
    'test_data.ii_barcode':    { id: 'ii-barcode',           type: 'input'    },
    'test_data.ii_cp':         { id: 'ii-cp',                type: 'input'    },
    'test_data.ii_sp':         { id: 'ii-sp',                type: 'input'    },
    'test_data.ii_description':{ id: 'ii-description',        type: 'input'    },
    'test_data.ii_tax_hsn':    { id: 'ii-tax-hsn',           type: 'input'    },
    'test_data.ii_tax':        { id: 'ii-tax',               type: 'input'    },
    'test_data.ii_reorder_limit': { id: 'ii-reorder-limit',  type: 'input'    },

    // ── Audit Config ──
    'audit_config.audit_mode':      { id: 'Audit_mode',           type: 'hidden',    handler: 'selectAType' },
    'audit_config.audit_type':      { id: 'ap-audit-type',        type: 'select'   },
    'audit_config.audit_damaged':   { id: 'cb-damaged',           type: 'checkbox' },
    'audit_config.stock_count':     { id: 'cb-stock',             type: 'checkbox' },
    'audit_config.geo_location':    { id: 'cb-geo',               type: 'checkbox' },
    'audit_config.photo_capture':   { id: 'cb-photo',             type: 'checkbox' },
    'audit_config.mapping_type':    { id: 'AUDITOR_MAPPING_TYPE', type: 'hidden',    handler: 'selectAMMode' },
    'audit_config.mapping_sheet':   { id: 'EXCEL_SHEET_AUDITOR_MAPPING', type: 'input' },
    'audit_config.auditor_col':     { id: 'EXCEL_auditor_col',    type: 'input'    },
    'audit_config.category_col':    { id: 'EXCEL_category_col',   type: 'input'    },
    'audit_config.storage_col':     { id: 'EXCEL_storage_col',    type: 'input'    },
    'audit_config.frequency':       { id: 'ap-frequency',         type: 'select'   },
    'audit_config.days':            { id: 'ap-days',              type: 'input'    },
    'audit_config.target_day':      { id: 'ap-target-day',        type: 'select'   },
    'audit_config.target_date':     { id: 'ap-target-date',       type: 'input'    },
    'audit_config.cross_audit_type':{ id: 'ap-cross-type',        type: 'select'   },
    'audit_config.cross_auditor':   { id: 'ap-cross-auditor',     type: 'input'    },
    'audit_config.photo_type':      { id: 'ap-photo-type',        type: 'select'   },
    'audit_config.sample_size':     { id: 'ap-sample-size',       type: 'input'    },

    // ── Ongoing Audit Config ──
    'audit_config.oa_cb_damaged':   { id: 'oa-cb-damaged',        type: 'checkbox' },
    'audit_config.oa_cb_stock':     { id: 'oa-cb-stock',          type: 'checkbox' },
    'audit_config.oa_cb_geo':       { id: 'oa-cb-geo',            type: 'checkbox' },
    'audit_config.oa_photo_type':   { id: 'oa-photo-type',        type: 'select'   },
    'audit_config.oa_sample_size':  { id: 'oa-sample-size',       type: 'input'    },
    'audit_config.oa_mapping_type': { id: 'oa-mapping-type',      type: 'select'   },
    'audit_config.oa_mapping_sheet':{ id: 'oa-mapping-sheet',     type: 'input'    },
    'audit_config.oa_auditor_col':  { id: 'oa-auditor-col',       type: 'input'    },
    'audit_config.oa_category_col': { id: 'oa-category-col',      type: 'input'    },
    'audit_config.oa_storage_col':  { id: 'oa-storage-col',       type: 'input'    },

    // ── Audit Plan Details ──
    'audit_config.ap_owner':        { id: 'ap-owner',             type: 'input'    },
    'audit_config.ap_group':        { id: 'ap-group',             type: 'input'    },
    'audit_config.ap_audit_name':   { id: 'ap-audit-name',        type: 'input'    },
    'audit_config.ap_auditor1':     { id: 'ap-auditor1',          type: 'input'    },
    'audit_config.ap_auditor2':     { id: 'ap-auditor2',          type: 'input'    },
    'audit_config.ap_cb_damaged':   { id: 'ap-cb-damaged',        type: 'checkbox' },
    'audit_config.ap_cb_stock':     { id: 'ap-cb-stock',          type: 'checkbox' },
    'audit_config.ap_cb_geo':       { id: 'ap-cb-geo',            type: 'checkbox' },

    // ── Ad-hoc Audit Details ──
    'audit_config.ah_auditor1':     { id: 'ah-auditor1',          type: 'input'    },
    'audit_config.ah_auditor2':     { id: 'ah-auditor2',          type: 'input'    },
    'audit_config.ah_group':        { id: 'ah-group',             type: 'input'    },
    'audit_config.ah_audit_name':   { id: 'ah-audit-name',        type: 'input'    },
    'audit_config.ah_audit_type_main': { id: 'ah-audit-type-main', type: 'select'  },
    'audit_config.ah_audit_type':   { id: 'ah-audit-type',        type: 'select'   },

    // ── Excel Reports / Sheets ──
    'audit_config.excel_sheet_as_table':      { id: 'EXCEL_SHEET_as_table',       type: 'input' },
    'audit_config.excel_sheet_recently_audit':{ id: 'EXCEL_SHEET_Recently_Audit', type: 'input' },
    'audit_config.excel_sheet_audit_summary': { id: 'EXCEL_SHEET_audit_Summary',  type: 'input' },
    'audit_config.filter_column':             { id: 'FILTER_COLUMN',              type: 'input' },
    'audit_config.a2_audit_summary_sheet':    { id: 'A2-audit-summary-sheet',     type: 'input' },
    'audit_config.a2_recently_audit_sheet':   { id: 'A2-recently-audit-sheet',    type: 'input' },
  };

  /* ─────────────────────────────────────────────
     SCHEMA VALIDATOR
     Returns { valid: boolean, errors: string[] }
  ───────────────────────────────────────────── */
  function validateSchema(data) {
    const errors = [];
    if (data === null || typeof data !== 'object' || Array.isArray(data)) {
      return { valid: false, errors: ['Root must be a JSON object.'] };
    }

    // config_version required
    if (!('config_version' in data)) {
      errors.push('Missing required field: config_version');
    } else if (typeof data.config_version !== 'string') {
      errors.push('config_version must be a string.');
    } else if (!SUPPORTED_VERSIONS.includes(data.config_version)) {
      errors.push(`Unsupported config_version "${data.config_version}". Supported: ${SUPPORTED_VERSIONS.join(', ')}`);
    }

    // Validate each section
    const schemaDef = SCHEMA.properties;
    for (const key of Object.keys(data)) {
      if (key === 'config_version') continue;
      if (!(key in schemaDef)) {
        errors.push(`Unknown top-level section: "${key}". Allowed: ${Object.keys(schemaDef).filter(k => k !== 'config_version').join(', ')}`);
        continue;
      }
      const sectionSchema = schemaDef[key];
      const sectionData = data[key];
      if (sectionSchema.type === 'object') {
        if (sectionData === null || typeof sectionData !== 'object' || Array.isArray(sectionData)) {
          errors.push(`"${key}" must be an object.`);
          continue;
        }
        // Validate properties
        if (sectionSchema.properties || sectionSchema.patternProperties) {
          for (const [prop, propSchema] of Object.entries(sectionData)) {
            const propDef = sectionSchema.properties ? sectionSchema.properties[prop] : null;

            // Unknown property check
            if (!propDef && !sectionSchema.additionalProperties && !sectionSchema.patternProperties) {
              errors.push(`Unknown property "${key}.${prop}".`);
              continue;
            }

            const schemaToUse = propDef || (sectionSchema.patternProperties ? Object.values(sectionSchema.patternProperties)[0] : null);

            if (schemaToUse) {
              // Type check
              if (schemaToUse.type === 'number') {
                if (typeof propSchema !== 'number' || isNaN(propSchema)) {
                  errors.push(`"${key}.${prop}" must be a number, got ${typeof propSchema}.`);
                } else if (schemaToUse.minimum !== undefined && propSchema < schemaToUse.minimum) {
                  errors.push(`"${key}.${prop}" must be >= ${schemaToUse.minimum}.`);
                }
              } else if (schemaToUse.type === 'string') {
                if (typeof propSchema !== 'string') {
                  errors.push(`"${key}.${prop}" must be a string, got ${typeof propSchema}.`);
                } else if (schemaToUse.enum && !schemaToUse.enum.includes(propSchema)) {
                  errors.push(`"${key}.${prop}" must be one of: ${schemaToUse.enum.join(', ')}. Got "${propSchema}".`);
                }
              } else if (schemaToUse.type === 'boolean') {
                if (typeof propSchema !== 'boolean') {
                  errors.push(`"${key}.${prop}" must be a boolean, got ${typeof propSchema}.`);
                }
              }
            }
          }
        }
      }
    }
    return { valid: errors.length === 0, errors };
  }

  /* ─────────────────────────────────────────────
     FLATTEN NESTED OBJECT → dot-path entries
     e.g. { a: { b: 1 } } → [['a.b', 1]]
  ───────────────────────────────────────────── */
  function flattenObj(obj, prefix) {
    const out = [];
    for (const [key, val] of Object.entries(obj)) {
      const path = prefix ? `${prefix}.${key}` : key;
      if (val !== null && typeof val === 'object' && !Array.isArray(val)) {
        out.push(...flattenObj(val, path));
      } else {
        out.push([path, val]);
      }
    }
    return out;
  }

  /* ─────────────────────────────────────────────
     APPLY VALUE TO UI CONTROL
     Returns { status: 'ok'|'skipped'|'error', reason?: string }
  ───────────────────────────────────────────── */
  function applyToControl(mapping, value) {
    const el = $(mapping.id);
    if (!el) {
      return { status: 'skipped', reason: `Element #${mapping.id} not found in DOM` };
    }

    try {
      switch (mapping.type) {
        case 'input': {
          const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
          )?.set;
          if (nativeInputValueSetter) {
            nativeInputValueSetter.call(el, String(value));
          } else {
            el.value = String(value);
          }
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
          return { status: 'ok' };
        }

        case 'select': {
          let strVal = String(value);
          if (mapping.id === 'browsername' && strVal.toLowerCase() === 'chromium') {
            strVal = 'chrome';
          }
          const optionExists = Array.from(el.options).some(
            o => o.value.toLowerCase() === strVal.toLowerCase()
          );
          if (!optionExists) {
            return { status: 'error', reason: `Value "${strVal}" not found in dropdown #${mapping.id}. Available: ${Array.from(el.options).map(o => o.value).join(', ')}` };
          }
          // Case-insensitive match
          const match = Array.from(el.options).find(
            o => o.value.toLowerCase() === strVal.toLowerCase()
          );
          el.value = match.value;
          el.dispatchEvent(new Event('change', { bubbles: true }));

          // Special sync for environment dropdown
          if (mapping.also === 'env-btn') {
            window.setEnv?.(null, match.value);
          }
          return { status: 'ok' };
        }

        case 'checkbox': {
          const newState = !!value;
          if (el.checked !== newState) {
            el.checked = newState;
            el.dispatchEvent(new Event('change', { bubbles: true }));
            // Sync visual toggle row
            const row = el.closest('.tgl-row') || el.closest('.chk-card');
            if (row) row.classList.toggle('on', newState);
            const box = row?.querySelector('.chk-box');
            if (box) box.textContent = newState ? ' ' : '';
          }
          return { status: 'ok' };
        }

        case 'hidden': {
          el.value = String(value);
          // Trigger handler if defined
          if (mapping.handler && typeof window[mapping.handler] === 'function') {
            window[mapping.handler](String(value));
          }
          return { status: 'ok' };
        }

        case 'group-switch': {
          const newState = !!value;
          const grpIdx = mapping.group;
          if (el.checked !== newState) {
            el.checked = newState;
            window.grpEnabled[grpIdx] = newState;
            if (typeof window.togGroupSwitch === 'function') {
              // togGroupSwitch reads from el.checked already
            }
            el.dispatchEvent(new Event('change', { bubbles: true }));
          }
          return { status: 'ok' };
        }

        case 'module-cb': {
          const newState = !!value;
          if (el.checked !== newState) {
            el.checked = newState;
            window.modEnabled[mapping.idx] = newState;
            el.dispatchEvent(new Event('change', { bubbles: true }));
            // Sync toggle row visual
            const tgl = el.closest('.tgl-row');
            if (tgl) tgl.classList.toggle('on', newState);
          }
          return { status: 'ok' };
        }

        default:
          return { status: 'skipped', reason: `Unknown control type: ${mapping.type}` };
      }
    } catch (err) {
      return { status: 'error', reason: err.message };
    }
  }

  /* ─────────────────────────────────────────────
     SNAPSHOT + ROLLBACK
     Before applying, snapshot all target controls.
     On error, restore from snapshot.
  ───────────────────────────────────────────── */
  function snapshotControls(paths) {
    const snap = {};
    for (const path of paths) {
      const mapping = FIELD_MAP[path];
      if (!mapping) continue;
      const el = $(mapping.id);
      if (!el) continue;
      if (mapping.type === 'checkbox' || mapping.type === 'group-switch' || mapping.type === 'module-cb') {
        snap[path] = { id: mapping.id, type: mapping.type, value: el.checked, mapping };
      } else {
        snap[path] = { id: mapping.id, type: mapping.type, value: el.value, mapping };
      }
    }
    return snap;
  }

  function rollbackFromSnapshot(snapshot) {
    for (const [, entry] of Object.entries(snapshot)) {
      const el = $(entry.id);
      if (!el) continue;
      if (entry.type === 'checkbox' || entry.type === 'group-switch' || entry.type === 'module-cb') {
        el.checked = entry.value;
        if (entry.type === 'group-switch') {
          window.grpEnabled[entry.mapping.group] = entry.value;
        }
        if (entry.type === 'module-cb') {
          window.modEnabled[entry.mapping.idx] = entry.value;
        }
      } else {
        el.value = entry.value;
      }
    }
    // Re-sync UI
    if (typeof window.syncModCount === 'function') window.syncModCount();
    if (typeof window.syncRunQueue === 'function') window.syncRunQueue();
  }

  /* ─────────────────────────────────────────────
     DISPLAY LABEL FOR PATHS (hide secrets)
  ───────────────────────────────────────────── */
  function displayValue(path, value) {
    if (SECRET_PATHS.has(path) || (FIELD_MAP[path] && FIELD_MAP[path].secret)) {
      return '••••••••';
    }
    if (typeof value === 'boolean') return value ? 'Enabled' : 'Disabled';
    if (typeof value === 'number') return String(value);
    if (typeof value === 'string' && value === '') return '(empty)';
    return String(value);
  }

  /* ─────────────────────────────────────────────
     MAIN IMPORT FUNCTION
     Returns { success, populated, skipped, errors, summary }
  ───────────────────────────────────────────── */
  function importJsonConfig(jsonString) {
    const result = {
      success: false,
      populated: [],
      skipped: [],
      errors: [],
      summary: '',
    };

    // 1. Parse JSON safely with reviver to detect prototype pollution
    let data;
    let hasUnsafeKey = false;
    try {
      data = JSON.parse(jsonString, (key, value) => {
        if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
          hasUnsafeKey = true;
        }
        return value;
      });
    } catch (e) {
      result.errors.push(`Invalid JSON: ${e.message}`);
      return result;
    }

    // Security: Prevent prototype pollution
    if (hasUnsafeKey) {
      result.errors.push('JSON contains unsafe keys (__proto__, constructor, prototype).');
      return result;
    }

    // 2. Schema validation
    const validation = validateSchema(data);
    if (!validation.valid) {
      result.errors = validation.errors;
      return result;
    }

    // 3. Flatten to dot-paths
    const flat = flattenObj(data, '');

    // 4. Resolve mappings
    const mappedPaths = [];
    const mappedValues = {};

    for (const [path, value] of flat) {
      if (path === 'config_version') continue;
      if (path === 'project.name') continue; // Informational only
      if (path === 'execution.retry_count') continue; // No UI for this
      if (path === 'execution.headless') continue; // No UI for this
      if (path === 'project.base_url') continue; // No UI base_url input

      // field_mappings section: lookup by value as ID
      if (path.startsWith('field_mappings.')) continue; // Used as reference only

      const mapping = FIELD_MAP[path];
      if (mapping) {
        mappedPaths.push(path);
        mappedValues[path] = value;
      } else {
        result.skipped.push({
          path,
          value: displayValue(path, value),
          reason: 'No matching UI control found',
        });
      }
    }

    // 5. Snapshot for atomic rollback
    const snapshot = snapshotControls(mappedPaths);

    // 6. Apply all values
    const applyErrors = [];
    for (const path of mappedPaths) {
      const mapping = FIELD_MAP[path];
      const value = mappedValues[path];
      const res = applyToControl(mapping, value);

      if (res.status === 'ok') {
        result.populated.push({
          path,
          controlId: mapping.id,
          value: displayValue(path, value),
        });
      } else if (res.status === 'error') {
        applyErrors.push({ path, reason: res.reason });
      } else {
        result.skipped.push({
          path,
          value: displayValue(path, value),
          reason: res.reason,
        });
      }
    }

    // 7. If any apply errors, rollback
    if (applyErrors.length > 0) {
      rollbackFromSnapshot(snapshot);
      result.errors = applyErrors.map(e => `${e.path}: ${e.reason}`);
      result.success = false;
      return result;
    }

    // 8. Sync framework state
    if (typeof window.syncModCount === 'function') window.syncModCount();
    if (typeof window.syncRunQueue === 'function') window.syncRunQueue();

    result.success = true;

    // 9. Build summary
    const lines = [];
    if (result.populated.length) {
      lines.push(`✅ ${result.populated.length} field(s) populated successfully.`);
    }
    if (result.skipped.length) {
      lines.push(`⏭️ ${result.skipped.length} field(s) skipped.`);
    }
    if (result.errors.length) {
      lines.push(`❌ ${result.errors.length} error(s).`);
    }
    result.summary = lines.join(' ');

    return result;
  }

  /* ─────────────────────────────────────────────
     RENDER IMPORT SUMMARY MODAL
  ───────────────────────────────────────────── */
  function renderImportSummary(result) {
    const modal = $('json-import-modal');
    const body = $('json-import-modal-body');
    if (!body) return;

    let html = '';

    // Status banner
    if (result.success) {
      html += `<div class="ji-banner ji-banner-ok">
        <span class="ji-banner-icon">✅</span>
        <div>
          <div class="ji-banner-title">Import Successful</div>
          <div class="ji-banner-sub">${result.summary}</div>
        </div>
      </div>`;
    } else {
      html += `<div class="ji-banner ji-banner-err">
        <span class="ji-banner-icon">⛔</span>
        <div>
          <div class="ji-banner-title">Import Failed</div>
          <div class="ji-banner-sub">Configuration was not applied. No fields were changed.</div>
        </div>
      </div>`;
    }

    // Errors
    if (result.errors.length) {
      html += `<div class="ji-section">
        <div class="ji-section-hd ji-section-err">❌ Errors (${result.errors.length})</div>
        <div class="ji-list">`;
      for (const err of result.errors) {
        html += `<div class="ji-row ji-row-err">
          <span class="ji-row-icon">✕</span>
          <span class="ji-row-text">${window.escHtml(err)}</span>
        </div>`;
      }
      html += `</div></div>`;
    }

    // Populated
    if (result.populated.length) {
      html += `<div class="ji-section">
        <div class="ji-section-hd ji-section-ok">✅ Populated (${result.populated.length})</div>
        <div class="ji-list">`;
      for (const item of result.populated) {
        html += `<div class="ji-row ji-row-ok">
          <span class="ji-row-icon">✓</span>
          <span class="ji-row-path">${window.escHtml(item.path)}</span>
          <span class="ji-row-arrow">→</span>
          <span class="ji-row-val">${window.escHtml(item.value)}</span>
          <span class="ji-row-ctrl">#${window.escHtml(item.controlId)}</span>
        </div>`;
      }
      html += `</div></div>`;
    }

    // Skipped
    if (result.skipped.length) {
      html += `<div class="ji-section">
        <div class="ji-section-hd ji-section-skip">⏭️ Skipped (${result.skipped.length})</div>
        <div class="ji-list">`;
      for (const item of result.skipped) {
        html += `<div class="ji-row ji-row-skip">
          <span class="ji-row-icon">–</span>
          <span class="ji-row-path">${window.escHtml(item.path)}</span>
          <span class="ji-row-reason">${window.escHtml(item.reason)}</span>
        </div>`;
      }
      html += `</div></div>`;
    }

    body.innerHTML = html;

    // Show modal
    if (modal) {
      modal.classList.add('show');
      modal.style.display = 'flex';
    }
  }

  /* ─────────────────────────────────────────────
     FILE INPUT HANDLER
  ───────────────────────────────────────────── */
  window.onJsonFileImport = function onJsonFileImport(input) {
    if (!input.files || !input.files.length) return;
    const file = input.files[0];

    if (!file.name.toLowerCase().endsWith('.json')) {
      renderImportSummary({
        success: false,
        populated: [],
        skipped: [],
        errors: ['File must be a .json file.'],
        summary: '',
      });
      input.value = '';
      return;
    }

    if (file.size > 1_048_576) { // 1MB limit
      renderImportSummary({
        success: false,
        populated: [],
        skipped: [],
        errors: ['File too large (max 1 MB).'],
        summary: '',
      });
      input.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = function(e) {
      const result = importJsonConfig(e.target.result);
      renderImportSummary(result);
      input.value = ''; // Reset for repeat import
    };
    reader.onerror = function() {
      renderImportSummary({
        success: false,
        populated: [],
        skipped: [],
        errors: ['Failed to read file.'],
        summary: '',
      });
      input.value = '';
    };
    reader.readAsText(file);
  };

  /* ─────────────────────────────────────────────
     CLOSE MODAL
  ───────────────────────────────────────────── */
  window.closeJsonImportModal = function closeJsonImportModal() {
    const modal = $('json-import-modal');
    if (modal) {
      modal.classList.remove('show');
      setTimeout(() => { modal.style.display = 'none'; }, 280);
    }
  };

  /* ─────────────────────────────────────────────
     EXPORT CURRENT CONFIG AS JSON
  ───────────────────────────────────────────── */
  window.exportJsonConfig = function exportJsonConfig() {
    const cfg = typeof window.buildCfg === 'function' ? window.buildCfg() : {};

    const exported = {
      config_version: '1.0',
      project: {
        name: 'QA Configuration',
        environment: cfg.environments || 'PRODUCTION',
      },
      execution: {
        browser: cfg.browsername || 'chrome',
        timeout: cfg.DEFAULT_TIMEOUT || 10000,
        short_timeout: cfg.SHORT_TIMEOUT || 5000,
        wait_after_action: cfg.WAIT_AFTER_ACTION || 300,
        branch: cfg.Branch || '',
        company_name: cfg.company_name || '',
      },
      modules: {
        q_audit: !!(window.grpEnabled && window.grpEnabled[0]),
        audit_plan: !!(window.grpEnabled && window.grpEnabled[1]),
        inventory: !!(window.grpEnabled && window.grpEnabled[2]),
      },
      test_data: {
        email: cfg.email || '',
        audit_name: cfg.audit_name || '',
        auditor1: cfg.Auditor_name1 || '',
        auditor2: cfg.Auditor_name2 || '',
        location1: cfg.location1 || '',
        location2: cfg.location2 || '',
      },
      audit_config: {
        audit_mode: cfg.Audit_mode || 'Audit_plan',
        mapping_type: cfg.AUDITOR_MAPPING_TYPE || 'Random',
      },
    };

    const jsonStr = JSON.stringify(exported, null, 2);
    const a = document.createElement('a');
    const ts = new Date().toISOString().slice(0, 10);
    a.href = URL.createObjectURL(new Blob([jsonStr], { type: 'application/json' }));
    a.download = `qa_config_${ts}.json`;
    a.click();
  };

  /* ─────────────────────────────────────────────
     PUBLIC API (for testing)
  ───────────────────────────────────────────── */
  window.QA_JSON_IMPORT = {
    validateSchema,
    flattenObj,
    importJsonConfig,
    FIELD_MAP,
    SUPPORTED_VERSIONS,
    SCHEMA,
  };

  console.info('[QA] json_import.js loaded');
}
