/**
 * ComponentRegistry — maps component_type strings to async Vue components.
 *
 * Async loading keeps the bundle small for users that don't trigger UI flows.
 * Adding a new component = drop a .vue file + one line here.
 */
import { defineAsyncComponent, type Component } from 'vue'

export const ComponentRegistry: Record<string, Component> = {
  CardList: defineAsyncComponent(() => import('../components/CardList.vue')),
  DynamicForm: defineAsyncComponent(() => import('../components/DynamicForm.vue')),
  ConfirmDialog: defineAsyncComponent(() => import('../components/ConfirmDialog.vue')),
  DataTable: defineAsyncComponent(() => import('../components/DataTable.vue')),
  StatusTimeline: defineAsyncComponent(() => import('../components/StatusTimeline.vue')),
}

export function getComponent(type: string): Component | null {
  return ComponentRegistry[type] || null
}

export function registerComponent(type: string, comp: Component): void {
  ComponentRegistry[type] = comp
}
