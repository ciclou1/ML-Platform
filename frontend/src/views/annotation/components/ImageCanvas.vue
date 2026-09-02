<template>
  <div class="image-canvas">
    <div class="toolbar">
      <el-radio-group v-if="canvas.shapeType.value !== 'classify'" v-model="canvas.mode.value" size="small">
        <el-radio-button value="draw">绘制</el-radio-button>
        <el-radio-button value="select">选择</el-radio-button>
      </el-radio-group>

      <el-radio-group v-model="canvas.shapeType.value" size="small">
        <el-radio-button value="bbox">框</el-radio-button>
        <el-radio-button value="polygon">多边形</el-radio-button>
        <el-radio-button value="obb">旋转框</el-radio-button>
        <el-radio-button value="keypoint">关键点</el-radio-button>
        <el-radio-button value="classify">分类</el-radio-button>
      </el-radio-group>

      <el-button size="small" type="danger" :disabled="!canvas.selectedId.value" @click="handleDelete">
        删除标注
      </el-button>
      <el-button size="small" type="success" @click="handleSave">暂存当前图片</el-button>
    </div>

    <div class="canvas-wrap">
      <canvas
        ref="canvasEl"
        :width="800"
        :height="600"
        class="annotation-canvas"
        tabindex="0"
        @mousedown="handleMouseDown"
        @mousemove="canvas.onMouseMove"
        @mouseup="canvas.onMouseUp"
        @dblclick="canvas.onDoubleClick"
        @keydown="handleKeyDown"
      />
      <div v-if="!canDraw" class="canvas-mask">
        请先在右侧新增并选择类别，再开始标注。
      </div>
    </div>

    <div class="tool-hint">
      {{
        canvas.shapeType.value === 'classify'
          ? '分类：点击右侧类别或单击画布，为整张图片打分类标签'
          : canvas.shapeType.value === 'polygon'
          ? '多边形：单击加点，双击或 Enter 闭合'
          : canvas.shapeType.value === 'keypoint'
            ? '关键点：先拖出包围框，再逐次单击放置关键点，Enter/双击结束'
            : canvas.shapeType.value === 'obb'
              ? '旋转框：拖拽创建，选中后拖动上方圆点旋转'
              : '框：拖拽创建，选中后整体拖动'
      }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useCanvas, type Shape } from '@/composables/useCanvas'
import type { AnnotationViewData } from '@/types/annotation-workspace'

const props = defineProps<{
  imageSrc: string | null
  annotations: AnnotationViewData[]
  currentLabel: { id: string; name: string; color: string } | null
  canDraw: boolean
}>()

const emit = defineEmits<{
  save: [shapes: Shape[]]
  delete: [annotationId: string]
}>()

const canvasEl = ref<HTMLCanvasElement | null>(null)
const canvas = useCanvas(canvasEl)

defineExpose({
  updateSelectedLabel: (labelId: string, labelName: string, color: string) => {
    if (canvas.shapeType.value === 'classify') {
      // 分类模式：选择类别即为整图打标
      canvas.setClassifyLabel(labelId, labelName, color)
      return
    }
    canvas.updateSelectedLabel(labelId, labelName, color)
  },
  selectMode: () => {
    canvas.mode.value = 'select'
  },
  drawMode: () => {
    canvas.mode.value = props.canDraw ? 'draw' : 'select'
  },
})

watch(
  () => props.imageSrc,
  async (src) => {
    if (src) {
      await canvas.loadImage(src)
      canvas.mode.value = props.canDraw ? 'draw' : 'select'
      loadAnnotations()
    }
  },
)

watch(
  () => props.currentLabel,
  (label) => {
    if (label) {
      canvas.setLabel(label.id, label.name, label.color)
    }
  },
)

watch(
  () => props.canDraw,
  (enabled) => {
    if (!enabled && canvas.mode.value === 'draw') {
      canvas.mode.value = 'select'
    }
  },
)

watch(() => props.annotations, loadAnnotations)

function loadAnnotations() {
  const shapes: Shape[] = []
  for (const annotation of props.annotations) {
    const shape = annotationToShape(annotation)
    if (shape) {
      shapes.push(shape)
    }
  }
  canvas.setShapes(shapes)
}

function annotationToShape(annotation: AnnotationViewData): Shape | null {
  const base = {
    id: annotation.id,
    labelId: annotation.label_id,
    labelName: annotation.label_name,
    color: annotation.color,
  }
  const data = annotation.data

  if (annotation.annotation_type === 'classify') {
    return { ...base, type: 'classify' }
  }
  if (annotation.annotation_type === 'polygon') {
    if (!Array.isArray(data.points)) return null
    return { ...base, type: 'polygon', points: data.points as [number, number][] }
  }
  if (annotation.annotation_type === 'obb') {
    if (typeof data.cx !== 'number') return null
    return {
      ...base,
      type: 'obb',
      cx: data.cx,
      cy: data.cy as number,
      w: data.w as number,
      h: data.h as number,
      angle: typeof data.angle === 'number' ? data.angle : 0,
    }
  }
  if (annotation.annotation_type === 'keypoint') {
    const bbox = data.bbox as { x: number; y: number; width: number; height: number } | undefined
    if (!bbox || !Array.isArray(data.points)) return null
    return {
      ...base,
      type: 'keypoint',
      bbox,
      points: data.points as [number, number, number][],
    }
  }
  return {
    ...base,
    type: 'bbox',
    x: annotation.bbox.x,
    y: annotation.bbox.y,
    width: annotation.bbox.width,
    height: annotation.bbox.height,
  }
}

function handleMouseDown(event: MouseEvent) {
  if (canvas.mode.value === 'draw' && !props.canDraw) {
    ElMessage.warning('请先新增并选择类别')
    return
  }
  canvas.onMouseDown(event)
}

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === 'Delete' || event.key === 'Backspace') {
    event.preventDefault()
    handleDelete()
    return
  }
  canvas.onKeyDown(event)
}

function handleDelete() {
  const id = canvas.selectedId.value
  if (id) {
    canvas.deleteSelected()
    emit('delete', id)
  }
}

function handleSave() {
  emit('save', canvas.shapes.value)
}
</script>

<style scoped>
.image-canvas {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.canvas-wrap {
  position: relative;
}

.annotation-canvas {
  border: 1px solid #ddd;
  cursor: crosshair;
  background: #f0f0f0;
}

.canvas-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.52);
  color: #fff;
  font-size: 14px;
  text-align: center;
  padding: 24px;
  pointer-events: none;
}

.tool-hint {
  color: #64748b;
  font-size: 12px;
  text-align: center;
}
</style>
