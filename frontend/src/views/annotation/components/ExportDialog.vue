<template>
  <el-dialog :model-value="visible" title="导出标注数据集" width="450px" @close="emit('update:visible', false)">
    <el-form label-width="100px">
      <el-form-item label="保存方式">
        <el-radio-group v-model="mode">
          <el-radio value="new">保存为新数据集</el-radio>
          <el-radio value="overwrite">覆盖当前数据集</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="标注统计">
        <span>{{ annotatedCount }} 张图片已标注，共 {{ totalBoxCount }} 个标注框</span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="exporting" @click="handleExport">确认导出</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { exportAnnotated } from '@/api/dataset'
import type { Shape } from '@/composables/useCanvas'

function shapeToData(shape: Shape): Record<string, unknown> {
  if (shape.type === 'classify') {
    return {}
  }
  if (shape.type === 'bbox') {
    return { x: shape.x, y: shape.y, width: shape.width, height: shape.height }
  }
  if (shape.type === 'polygon') {
    return { points: shape.points }
  }
  if (shape.type === 'obb') {
    return { cx: shape.cx, cy: shape.cy, w: shape.w, h: shape.h, angle: shape.angle }
  }
  return { bbox: shape.bbox, points: shape.points }
}

const props = defineProps<{
  visible: boolean
  datasetId: string
  draftStore: Map<string, Shape[]>
  annotatedCount: number
  totalBoxCount: number
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  exported: []
}>()

const mode = ref<'new' | 'overwrite'>('new')
const exporting = ref(false)

async function handleExport() {
  if (props.annotatedCount === 0) {
    ElMessage.warning('没有标注数据可导出')
    return
  }

  exporting.value = true
  try {
    const annotations: Record<
      string,
      { label_id: string; annotation_type: string; data: Record<string, unknown> }[]
    > = {}
    for (const [imageId, shapes] of props.draftStore.entries()) {
      annotations[imageId] = shapes.map((shape) => ({
        label_id: shape.labelId,
        annotation_type: shape.type,
        data: shapeToData(shape),
      }))
    }

    await exportAnnotated(props.datasetId, {
      mode: mode.value,
      annotations,
    })

    emit('update:visible', false)
    emit('exported')
    ElMessage.success(mode.value === 'new' ? '已导出为新数据集' : '已覆盖当前数据集')
  } catch {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}
</script>
