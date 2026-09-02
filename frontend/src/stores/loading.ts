import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/** 全局请求计数，驱动顶部进度条（见 App.vue）。 */
export const useLoadingStore = defineStore('loading', () => {
  const pending = ref(0)

  const isLoading = computed(() => pending.value > 0)

  function start() {
    pending.value += 1
  }

  function finish() {
    pending.value = Math.max(0, pending.value - 1)
  }

  return { isLoading, start, finish }
})
