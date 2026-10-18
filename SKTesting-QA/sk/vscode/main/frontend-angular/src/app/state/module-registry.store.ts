import { Injectable, inject, signal, computed } from '@angular/core';
import { ModuleService } from '../core/services/module.service';
import { ModuleDef, GroupDef } from '../core/models/module-registry.model';

@Injectable({
  providedIn: 'root'
})
export class ModuleRegistryStore {
  private readonly moduleService = inject(ModuleService);

  readonly modules = signal<ModuleDef[]>([]);
  readonly groups = signal<GroupDef[]>([]);
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
        this.modules.set(res.modules || []);
        this.groups.set(res.groups || []);
        this.isLoading.set(false);

        // Initialize groupEnabled and moduleEnabled if empty
        if (this.groupEnabled().every(v => !v)) {
          this.groupEnabled.set(new Array(res.groups?.length || 3).fill(false));
        }

        const me = { ...this.moduleEnabled() };
        res.modules?.forEach(m => {
          if (me[m.idx] === undefined) {
            me[m.idx] = false;
          }
        });
        this.moduleEnabled.set(me);
      },
      error: (err) => {
        this.error.set(err.message || 'Failed to load module registry');
        this.isLoading.set(false);
      }
    });
  }

  toggleGroup(groupIdx: number, forcedState?: boolean): void {
    const current = [...this.groupEnabled()];
    const nextState = forcedState !== undefined ? forcedState : !current[groupIdx];
    current[groupIdx] = nextState;
    this.groupEnabled.set(current);

    // Auto-expand group when enabled
    if (nextState) {
      this.setGroupExpanded(groupIdx, true);
    }
  }

  toggleGroupExpand(groupIdx: number): void {
    const current = [...this.groupExpanded()];
    current[groupIdx] = !current[groupIdx];
    this.groupExpanded.set(current);
  }

  setGroupExpanded(groupIdx: number, expanded: boolean): void {
    const current = [...this.groupExpanded()];
    current[groupIdx] = expanded;
    this.groupExpanded.set(current);
  }

  toggleModule(moduleIdx: number, forcedState?: boolean): void {
    const current = { ...this.moduleEnabled() };
    const nextState = forcedState !== undefined ? forcedState : !current[moduleIdx];
    current[moduleIdx] = nextState;
    this.moduleEnabled.set(current);
  }

  selectModuleForEditing(idx: number): void {
    this.selectedModuleIdx.set(idx);
  }

  selectAll(): void {
    this.groupEnabled.set([true, true, true]);
    const me: Record<number, boolean> = {};
    this.modules().forEach(m => {
      me[m.idx] = true;
    });
    this.moduleEnabled.set(me);
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
