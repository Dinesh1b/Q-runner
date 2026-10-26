import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { RunConfigStore } from './run-config.store';

describe('RunConfigStore — Create Group settings in the run payload', () => {
  let configStore: RunConfigStore;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])]
    });
    configStore = TestBed.inject(RunConfigStore);
  });

  it('sends the Item Group defaults', () => {
    const cfg = configStore.buildRunConfig();
    expect(cfg.inv_accounting_mode).toBe('Basic Accounting Mode');
    expect(cfg.inv_costing_method).toBe('Weighted Average');
    expect(cfg.inv_accounting_accounts).toEqual({ SaleAccountId: 'Sales Revenue', PurchaseAccountId: 'Purchase Expenses' });
    expect(cfg.inv_advanced_toggles).toEqual({ AllowDiscount: true, EditSalePrice: true });
    expect(cfg.inv_enable_uom_conversions).toBeTrue();
    expect(cfg.inv_primary_uom).toBe('Bale');
    expect(cfg.inv_secondary_uoms).toEqual([{ uom: 'Box', quantity: 12, base: '' }]);
    expect(cfg.inv_tertiary_uoms).toEqual([{ uom: 'Pallet', quantity: 25, base: 'Box' }]);
    expect(cfg.inv_default_uom).toBeNull();
  });

  it('leave as is sends null for UOM and drops the toggle', () => {
    configStore.invUomMode.set('leave');
    configStore.invAdvanced.set({ AllowDiscount: 'off', EditSalePrice: 'leave' });

    const cfg = configStore.buildRunConfig();
    expect(cfg.inv_enable_uom_conversions).toBeNull();
    expect(cfg.inv_advanced_toggles).toEqual({ AllowDiscount: false });
  });

  it('only sends the accounts of the chosen mode, and drops incomplete UOM rows', () => {
    configStore.invAccountingMode.set('Inventory Accounting Mode');
    configStore.invAccounts.set({ PurchaseAccountId: 'Purchase Expenses', COGSAccountId: 'Cost of Goods Sold (COGS)' });
    configStore.invSecondaryUoms.set([{ uom: 'Box', quantity: 10, base: '' }, { uom: '', quantity: 5, base: '' }, { uom: 'Case', quantity: null, base: '' }]);

    const cfg = configStore.buildRunConfig();
    expect(cfg.inv_accounting_accounts).toEqual({ COGSAccountId: 'Cost of Goods Sold (COGS)' });
    expect(cfg.inv_secondary_uoms).toEqual([{ uom: 'Box', quantity: 10, base: '' }]);
  });

  it('sends the Location Setup run options, setup on and tests off by default', () => {
    expect(configStore.buildRunConfig()).toEqual(jasmine.objectContaining({
      ls_run_setup: true, ls_run_tests: false, ls_test_groups: ['functional', 'validation', 'ui'],
      ls_test_cases: '', ls_test_prefix: 'QA', ls_test_cleanup: true,
    }));

    configStore.lsRunSetup.set(false);
    configStore.lsRunTests.set(true);
    configStore.lsTestGroups.set(['validation']);
    configStore.lsTestCases.set('WH_021, WH_022');
    configStore.lsTestPrefix.set('');
    expect(configStore.buildRunConfig()).toEqual(jasmine.objectContaining({
      ls_run_setup: false, ls_run_tests: true, ls_test_groups: ['validation'],
      ls_test_cases: 'WH_021, WH_022', ls_test_prefix: 'QA',
    }));
  });
});
