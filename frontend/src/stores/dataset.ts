import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createDataset, deleteDataset, getDatasets } from '@/api/dataset'
import type { Dataset } from '@/types/dataset'

/** 数据集列表共享状态：供数据集管理页与其它需要数据集下拉的页面复用。 */
export const useDatasetStore = defineStore('dataset', () => {
  const datasets = ref<Dataset[]>([])
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      datasets.value = await getDatasets()
    } finally {
      loading.value = false
    }
  }

  async function create(data: {
    name: string
    description?: string
    data_type?: string
    annotation_types?: string[]
  }) {
    const created = await createDataset(data)
    await load()
    return created
  }

  async function remove(id: string) {
    await deleteDataset(id)
    await load()
  }

  return { datasets, loading, load, create, remove }
})
