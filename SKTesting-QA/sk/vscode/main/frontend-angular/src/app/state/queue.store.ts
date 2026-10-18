import { Injectable, inject, signal, computed, effect } from '@angular/core';
import { moveItemInArray } from '@angular/cdk/drag-drop';
import { ModuleRegistryStore } from './module-registry.store';
import { ModuleDef } from '../core/models/module-registry.model';

@Injectable({
  providedIn: 'root'
})
export class QueueStore {
  private readonly registryStore = inject(ModuleRegistryStore);

  /**
   * The custom ordered list of module indices currently in the queue.
   */
  readonly orderedIndices = signal<number[]>([]);

  /**
   * Complete ordered ModuleDef objects currently in the run queue.
   */
  readonly queuedModules = computed<ModuleDef[]>(() => {
    const activeMods = this.registryStore.activeModules();
    const activeMap = new Map(activeMods.map(m => [m.idx, m]));
    const order = this.orderedIndices();

    // Map ordered indices to their module defs
    const result: ModuleDef[] = [];
    order.forEach(idx => {
      const mod = activeMap.get(idx);
      if (mod) {
        result.push(mod);
      }
    });

    return result;
  });

  readonly queueCount = computed(() => this.queuedModules().length);

  constructor() {
    // Keep orderedIndices in sync with changes to active modules
    effect(() => {
      const activeMods = this.registryStore.activeModules();
      const activeIndices = activeMods.map(m => m.idx);
      const currentOrder = this.orderedIndices();

      // 1. Keep currently ordered indices that remain active
      const nextOrder = currentOrder.filter(idx => activeIndices.includes(idx));

      // 2. Append newly activated indices that were not in currentOrder
      activeIndices.forEach(idx => {
        if (!nextOrder.includes(idx)) {
          nextOrder.push(idx);
        }
      });

      // Update only if order actually changed
      if (
        nextOrder.length !== currentOrder.length ||
        nextOrder.some((val, i) => val !== currentOrder[i])
      ) {
        this.orderedIndices.set(nextOrder);
      }
    });
  }

  /**
   * Move an item in the queue when dragged by CDK drag-drop.
   */
  reorder(previousIndex: number, currentIndex: number): void {
    const list = [...this.orderedIndices()];
    moveItemInArray(list, previousIndex, currentIndex);
    this.orderedIndices.set(list);
  }

  /**
   * Move item to the very top (priority 1).
   */
  moveToTop(index: number): void {
    if (index <= 0) return;
    const list = [...this.orderedIndices()];
    const [item] = list.splice(index, 1);
    list.unshift(item);
    this.orderedIndices.set(list);
  }

  /**
   * Move item to the very bottom.
   */
  moveToBottom(index: number): void {
    const list = [...this.orderedIndices()];
    if (index >= list.length - 1) return;
    const [item] = list.splice(index, 1);
    list.push(item);
    this.orderedIndices.set(list);
  }

  /**
   * Get the queue run order indices for config serialization.
   */
  getRunOrder(): number[] {
    return this.orderedIndices();
  }
}
