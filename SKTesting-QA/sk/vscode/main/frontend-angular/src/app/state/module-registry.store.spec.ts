import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { ModuleRegistryStore } from './module-registry.store';
import { RunConfigStore } from './run-config.store';

describe('ModuleRegistryStore — group / module enablement rules', () => {
  let store: ModuleRegistryStore;
  let configStore: RunConfigStore;

  const enabledInGroup = (group: number) =>
    store.modules().filter(m => m.group === group && store.moduleEnabled()[m.idx]);

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])]
    });
    store = TestBed.inject(ModuleRegistryStore);
    configStore = TestBed.inject(RunConfigStore);
  });

  it('starts with every group and module OFF', () => {
    expect(store.groupEnabled().every(g => !g)).toBeTrue();
    expect(store.activeCount()).toBe(0);
  });

  it('turning a group ON leaves its modules OFF', () => {
    store.toggleGroup(0, true);
    expect(store.groupEnabled()[0]).toBeTrue();
    expect(enabledInGroup(0).length).toBe(0);
  });

  it('blocks enabling a module while its group is OFF', () => {
    expect(store.setModuleEnabled(0, true)).toBeFalse();
    store.toggleModule(0);
    expect(store.moduleEnabled()[0]).toBeFalsy();
    expect(store.groupEnabled()[0]).toBeFalse();
  });

  it('lets the user enable and disable individual modules in an ON group', () => {
    store.toggleGroup(0, true);
    store.toggleModule(1);
    expect(store.activeModules().map(m => m.idx)).toEqual([1]);
    store.toggleModule(1);
    expect(store.activeCount()).toBe(0);
  });

  it('turning a group OFF clears its modules, and turning it back ON keeps them OFF', () => {
    store.toggleGroup(0, true);
    store.toggleModule(0);
    store.toggleModule(2);
    store.toggleGroup(0, false);
    expect(enabledInGroup(0).length).toBe(0);
    store.toggleGroup(0, true);
    expect(enabledInGroup(0).length).toBe(0);
  });

  it('expanding a group does not enable it', () => {
    store.toggleGroupExpand(1);
    expect(store.groupExpanded()[1]).toBeTrue();
    expect(store.groupEnabled()[1]).toBeFalse();
  });

  it('Select All turns groups ON but no modules', () => {
    store.selectAll();
    expect(store.groupEnabled().every(g => g)).toBeTrue();
    expect(store.activeCount()).toBe(0);
  });

  it('Table · Summary · Recent share a page but still run independently', () => {
    store.toggleGroup(1, true);
    store.toggleModule(10);
    store.toggleModule(12);

    const cfg = configStore.buildRunConfig() as unknown as Record<string, unknown>;
    expect(cfg['run_A_as_table']).toBeTrue();
    expect(cfg['run_A_audit_Summary']).toBeFalse();
    expect(cfg['run_A_Recently_Audit']).toBeTrue();
  });

  it('run payload only enables modules whose group is ON', () => {
    store.toggleGroup(0, true);
    store.toggleModule(0);
    store.toggleGroup(2, true);
    store.toggleModule(13);
    store.toggleGroup(2, false);

    const cfg = configStore.buildRunConfig() as unknown as Record<string, unknown>;
    expect(cfg['run_q_setting']).toBeTrue();
    expect(cfg['run_create_group']).toBeFalse();
    expect(cfg['run_inventory']).toBeFalse();
    expect(cfg['frequency']).toBe('one-time');
  });

  it('create group runs create only by default', () => {
    store.toggleGroup(2, true);
    store.toggleModule(13);

    const cfg = configStore.buildRunConfig() as unknown as Record<string, unknown>;
    expect(cfg['run_create_group']).toBeTrue();
    expect(cfg['run_update_group']).toBeFalse();
  });

  it('create group can run update only', () => {
    store.toggleGroup(2, true);
    store.toggleModule(13);
    configStore.cbCg.set(false);
    configStore.cbUg.set(true);
    TestBed.flushEffects();  // the Run Queue follows the enabled modules through an effect

    const cfg = configStore.buildRunConfig() as unknown as Record<string, unknown>;
    expect(cfg['run_create_group']).toBeFalse();
    expect(cfg['run_update_group']).toBeTrue();
    expect(cfg['run_inventory']).toBeTrue();
    expect(cfg['MODULE_RUN_ORDER'] as number[]).toContain(13);
  });
});
