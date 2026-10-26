/**
 * Choices for the Create Group page, read from the Stockount Add Item Group page.
 * Accounts and UOMs are offered as suggestions; other names can still be typed.
 */

export type UomLevel = 'Secondary' | 'Tertiary';
export type ToggleState = 'leave' | 'on' | 'off';

/** One conversion row: 1 <uom> = <quantity> <base>; a blank base means the Primary UOM. */
export interface UomRow {
  uom: string;
  quantity: number | null;
  base: string;
}

export interface Option {
  key: string;
  label: string;
}

export const INVENTORY_TYPES = [
  { value: 'Unit', icon: '📦', desc: 'Track items as simple unit quantities', badge: 'Basic' },
  { value: 'Batch', icon: '📑', desc: 'Group items by lot or batch number', badge: 'Lot-based' },
  { value: 'Serialized', icon: '🔖', desc: 'Each item tracked by unique serial / IMEI', badge: 'Per-unit ID' },
];

export const BARCODE_FIELD_TYPES = ['Id1Name', 'Separator', 'Item Code', 'Bar Code', 'Static Value', 'Item Name'];

/** FIFO and LIFO are disabled in Stockount (both accounting modes, DEV and PRODUCTION), so they can't be picked. */
export const COSTING_METHODS = [
  { value: 'Weighted Average', disabled: false },
  { value: 'FIFO', disabled: true },
  { value: 'LIFO', disabled: true },
];

export const ACCOUNTING_MODES = ['Basic Accounting Mode', 'Inventory Accounting Mode'];

/** Account fields shown in each accounting mode (formcontrolname → label on the Stockount page). */
export const ACCOUNT_FIELDS: Record<string, Option[]> = {
  'Basic Accounting Mode': [
    { key: 'SaleAccountId', label: 'Sales Invoice' },
    { key: 'PurchaseAccountId', label: 'Purchase Invoice' },
    { key: 'StockAdjId', label: 'Stock Adjustment' },
    { key: 'StockTransferId', label: 'Stock Transfer' },
  ],
  'Inventory Accounting Mode': [
    { key: 'SaleAccountId', label: 'Sales' },
    { key: 'InventoryAccountId', label: 'Inventory' },
    { key: 'StockAdjId', label: 'Stock Adjustment' },
    { key: 'StockTransferId', label: 'Stock Transfer' },
    { key: 'COGSAccountId', label: 'COGS' },
  ],
};

/** Standard account names, the same for every environment. */
export const ACCOUNT_NAMES = [
  'Accounts Receivable', 'Current Assets', 'Inter Branch Accounts', 'Default', 'Bank Accounts', 'Bank Cheque',
  'Cash Accounts', 'Fixed Assets', 'Equipments', 'Customer Accounts', 'Owner’s Equity', 'Equity',
  'Retained Earnings', 'Advertising', 'Bank Fees', 'Cost of Goods Sold (COGS)', 'Depreciation', 'Freight Charges',
  'Packaging Costs', 'Rent', 'Salaries', 'Utilities', 'Stock Adjustment', 'Purchase Expenses', 'Accounts Payable',
  'Loans Payable', 'Sales Tax Payable', 'Vendors', 'Employees', 'Discounts Received', 'Other Income',
  'Sales Revenue', 'Service Revenue', 'Inventory',
];

/** Advanced tab switches that can be changed (Allow Negative Stock and Low Stock Alert are disabled in Stockount). */
export const ADVANCED_TOGGLES: Option[] = [
  { key: 'AllowDiscount', label: 'Allow discount' },
  { key: 'EditSalePrice', label: 'Edit Sale Price' },
  { key: 'ChangeInvoiceDate', label: 'Change Invoice Date' },
  { key: 'AllowNonTaxable', label: 'Allow Non-taxable' },
  { key: 'DNBeforeInvoice', label: 'DN on Order' },
  { key: 'GRNBeforeInvoice', label: 'GRN on Order' },
  { key: 'DNWithInvoice', label: 'DN With Invoice' },
  { key: 'GRNWithInvoice', label: 'GRN With Invoice' },
];

/** Same on PRODUCTION and DEV. */
export const UOM_NAMES = ['Bale', 'Bottle', 'Box', 'Case', 'Container', 'Crate', 'Meter', 'Pallet', 'Piece', 'Roll', 'Unit'];

export const UOM_VALUE_TYPES = ['Integer only', 'Decimal'];
