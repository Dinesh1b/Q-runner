import { Injectable, inject, signal, computed } from '@angular/core';
import { ModuleService } from '../core/services/module.service';
import { ModuleDef, GroupDef } from '../core/models/module-registry.model';

export const DEFAULT_GROUPS: GroupDef[] = [
  { idx: 0, name: 'Q Audit', range: [0, 5] },
  { idx: 1, name: 'Audit Plan', range: [6, 12] },
  { idx: 2, name: 'Inventory', range: [13, 15] }
];

export const DEFAULT_MODULES: ModuleDef[] = [
  { idx: 0, flag: 'run_q_setting', name: 'Q_Setting', display: 'Q_Setting', icon: '⚙️', group: 0, session: 'auditor1', workflow: 'q_setting.Q_setting', cb: 'cb-qs', tgl: 'tgl-qs' },
  { idx: 1, flag: 'run_Q_SA', name: 'Q_SA', display: 'Stock Audit A1', icon: '📦', group: 0, session: 'auditor1', workflow: 'q_sa.Q_SA', cb: 'cb-sa1', tgl: 'tgl-sa1' },
  { idx: 2, flag: 'run_Q_SA1', name: 'Q_SA1', display: 'Stock Audit A2', icon: '📦', group: 0, session: 'auditor2', workflow: 'q_sa1.Q_SA1', cb: 'cb-sa2', tgl: 'tgl-sa2' },
  { idx: 3, flag: 'run_Q_as_table', name: 'Q_as_table', display: 'Summary Table', icon: '📉', group: 0, session: 'auditor1', workflow: 'q_as_table.Q_as_table', cb: 'cb-sum', tgl: 'tgl-sum' },
  { idx: 4, flag: 'run_Q_Recently_Audit', name: 'Q_Recently_Audit', display: 'Recently Audited', icon: '🕐', group: 0, session: 'auditor1', workflow: 'q_recently_audit.Q_Recently_Audit', cb: 'cb-rec', tgl: 'tgl-rec' },
  { idx: 5, flag: 'run_Q_audit_Summary', name: 'Q_audit_Summary', display: 'Q_audit_Summary', icon: '📊', group: 0, session: 'auditor1', workflow: 'q_audit_summary.Q_audit_Summary', cb: 'cb-qsum', tgl: 'tgl-qsum' },
  { idx: 6, flag: 'run_create_audit', name: 'Audit_Plan', display: 'Audit Plan', icon: '📅', group: 1, session: 'auditor1', workflow: 'audit_plan.create_audit', cb: 'cb-ap', tgl: 'tgl-ap', alt_flag: 'run_create_Ad_hoc_Audit' },
  { idx: 7, flag: 'run_setup_Audit', name: 'Ongoing_Audit', display: 'Ongoing Audit', icon: '🔄', group: 1, session: 'auditor1', workflow: 'ongo_audit.Ongo_Audit', cb: 'cb-oa', tgl: 'tgl-oa' },
  { idx: 8, flag: 'run_stock_audit', name: 'stock_audit', display: 'Auditor 1 SA', icon: '👤', group: 1, session: 'auditor1', workflow: 'auditor_1.stock_audit', cb: 'cb-asa', tgl: 'tgl-asa' },
  { idx: 9, flag: 'run_stock_audit2', name: 'stock_audit2', display: 'Auditor 2 SA', icon: '👤', group: 1, session: 'auditor2', workflow: 'auditor_2.stock_audit2', cb: 'cb-asa2', tgl: 'tgl-asa2' },
  { idx: 10, flag: 'run_A_as_table', name: 'A_as_table', display: 'Table', icon: '📉', group: 1, session: 'auditor2', workflow: 'a_as_table.A_as_table', cb: 'cb-atab', tgl: 'tgl-atab' },
  { idx: 11, flag: 'run_A_audit_Summary', name: 'A_audit_Summary', display: 'Summary', icon: '📊', group: 1, session: 'auditor2', workflow: 'a_audit_summary.A_audit_Summary', cb: 'cb-asum', tgl: 'tgl-asum' },
  { idx: 12, flag: 'run_A_Recently_Audit', name: 'A_Recently_Audit', display: 'Recent', icon: '🕐', group: 1, session: 'auditor2', workflow: 'a_recently_audit.A_Recently_Audit', cb: 'cb-arec', tgl: 'tgl-arec' },
  { idx: 13, flag: 'run_create_group', name: 'Create_Group', display: 'Create Group', icon: '📁', group: 2, session: 'auditor1', workflow: 'create_group.create_group', cb: 'cb-cg', tgl: 'tgl-cg' },
  { idx: 14, flag: 'run_location_setup', name: 'Location_Setup', display: 'Location Setup', icon: '📍', group: 2, session: 'auditor1', workflow: 'location_setup.settings', cb: 'cb-ls', tgl: 'tgl-ls' },
  { idx: 15, flag: 'run_import_app', name: 'Import_App', display: 'Import Items', icon: '📥', group: 2, session: 'auditor1', workflow: 'import_app.import_app', cb: 'cb-ii', tgl: 'tgl-ii' }
];

/** Table · Summary · Recent — three separate modules shown together on one page. */
export const A2_REPORT_MODULES = [10, 11, 12];

@Injectable({
  providedIn: 'root'
})
export class ModuleRegistryStore {
  private readonly moduleService = inject(ModuleService);

  readonly modules = signal<ModuleDef[]>(DEFAULT_MODULES);
  readonly groups = signal<GroupDef[]>(DEFAULT_GROUPS);
  readonly groupEnabled = signal<boolean[]>([false, false, false]);
  readonly moduleEnabled = signal<Record<number, boolean>>({});
  readonly groupExpanded = signal<boolean[]>([false, false, false]);
  readonly selectedModuleIdx = signal<number | null>(null);
  readonly isLoading = signal<boolean>(false);
  readonly error = signal<string | null>(null);

  /**
   * List of modules that are enabled by virtue of both their parent group AND their individual checkbox being enabled.
   */
  readonly activeModules = computed(() => {
    const mods = this.modules();
    const ge = this.groupEnabled();
    const me = this.moduleEnabled();

    return mods.filter(m => !!(ge[m.group] && me[m.idx]));
  });

  readonly activeCount = computed(() => this.activeModules().length);
  readonly totalCount = computed(() => this.modules().length || 16);

  loadModules(): void {
    this.isLoading.set(true);
    this.moduleService.getModules().subscribe({
      next: (res) => {
        if (res.modules && res.modules.length > 0) {
          const normalized = res.modules.map(m => {
            if (!m.icon || m.icon === '??') {
              const def = DEFAULT_MODULES.find(d => d.idx === m.idx);
              return { ...m, icon: def?.icon || '📦' };
            }
            return m;
          });
          this.modules.set(normalized);
        }
        if (res.groups && res.groups.length > 0) {
          this.groups.set(res.groups);
        }
        this.isLoading.set(false);

        // Keep existing moduleEnabled states or default
        const me = { ...this.moduleEnabled() };
        this.modules().forEach(m => {
          if (me[m.idx] === undefined) {
            me[m.idx] = false;
          }
        });
        this.moduleEnabled.set(me);
      },
      error: () => {
        // Fallback already in place with DEFAULT_MODULES & DEFAULT_GROUPS
        this.isLoading.set(false);
      }
    });
  }

  toggleGroup(groupIdx: number, forcedState?: boolean): void {
    const current = [...this.groupEnabled()];
    const nextState = forcedState !== undefined ? forcedState : !current[groupIdx];
    current[groupIdx] = nextState;
    this.groupEnabled.set(current);

    if (nextState) {
      // Auto-expand group when enabled
      this.setGroupExpanded(groupIdx, true);

      // Modules stay OFF — the user enables the ones they need individually.
      const groupMods = this.modules().filter(m => m.group === groupIdx);

      // Automatically select first module in this group so main content is never blank!
      const currentSelected = this.selectedModuleIdx();
      const currentMod = currentSelected !== null ? this.modules().find(m => m.idx === currentSelected) : null;
      if (!currentMod || currentMod.group !== groupIdx) {
        if (groupMods.length > 0) {
          this.selectModuleForEditing(groupMods[0].idx);
        }
      }
    } else {
      // When group is turned off, also uncheck its modules
      const me = { ...this.moduleEnabled() };
      const groupMods = this.modules().filter(m => m.group === groupIdx);
      groupMods.forEach(m => {
        me[m.idx] = false;
      });
      this.moduleEnabled.set(me);
    }
  }

  toggleGroupExpand(groupIdx: number): void {
    const current = [...this.groupExpanded()];
    const next = !current[groupIdx];
    current[groupIdx] = next;
    this.groupExpanded.set(current);
  }

  setGroupExpanded(groupIdx: number, expanded: boolean): void {
    const current = [...this.groupExpanded()];
    current[groupIdx] = expanded;
    this.groupExpanded.set(current);
  }

  isModuleGroupEnabled(moduleIdx: number): boolean {
    const mod = this.modules().find(m => m.idx === moduleIdx);
    return !!mod && !!this.groupEnabled()[mod.group];
  }

  toggleModule(moduleIdx: number, forcedState?: boolean): void {
    const nextState = forcedState !== undefined ? forcedState : !this.moduleEnabled()[moduleIdx];
    this.setModuleEnabled(moduleIdx, nextState);
  }

  /**
   * Modules can only be enabled while their group is ON. Returns false when the change was blocked.
   */
  setModuleEnabled(moduleIdx: number, enabled: boolean): boolean {
    if (enabled && !this.isModuleGroupEnabled(moduleIdx)) {
      return false;
    }
    const current = { ...this.moduleEnabled() };
    current[moduleIdx] = enabled;
    this.moduleEnabled.set(current);
    return true;
  }

  selectModuleForEditing(idx: number): void {
    this.selectedModuleIdx.set(idx);
    const mod = this.modules().find(m => m.idx === idx);
    if (mod) {
      this.setGroupExpanded(mod.group, true);
    }
    window.dispatchEvent(new CustomEvent('navigate-tab', { detail: 'execution' }));
  }

  selectAll(): void {
    this.groupEnabled.set([true, true, true]);
    this.groupExpanded.set([true, true, true]);
    // Modules stay OFF — the user enables the ones they need individually.
    if (this.selectedModuleIdx() === null) {
      this.selectedModuleIdx.set(0);
    }
  }

  deselectAll(): void {
    this.groupEnabled.set([false, false, false]);
    const me: Record<number, boolean> = {};
    this.modules().forEach(m => {
      me[m.idx] = false;
    });
    this.moduleEnabled.set(me);
  }
}
