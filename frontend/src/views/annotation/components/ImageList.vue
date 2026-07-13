<template>
  <div class="image-list">
    <h4>图片列表 ({{ images.length }} / {{ totalCount }})</h4>
    <div
      v-for="image in images"
      :key="image.id"
      class="image-item"
      :class="{ active: image.id === selectedId }"
      @click="emit('select', image)"
    >
      <div class="image-main">
        <div class="image-meta">
          <span class="image-name">{{ image.filename }}</span>
          <span class="image-split">{{ image.split || '--' }}</span>
        </div>
        <div class="image-actions">
          <el-tag size="small" :type="image.draft_status === 'annotated' ? 'success' : 'info'">
            {{ image.draft_status === 'annotated' ? '已标注' : '未标注' }}
          </el-tag>
          <el-button size="small" link type="danger" @click.stop="emit('delete', image)">
            删除
          </el-button>
        </div>
      </div>
    </div>
    <div v-if="hasMore" class="load-more">
      <el-button size="small" :loading="loadingMore" @click="emit('load-more')">
        {{ loadingMore ? '加载中...' : '加载更多' }}
      </el-button>
    </div>
    <p v-if="images.length === 0" class="empty">暂无图片</p>
  </div>
</template>

<script setup lang="ts">
import type { WorkspaceImageListItem } from '@/types/annotation-workspace'

defineProps<{
  images: WorkspaceImageListItem[]
  selectedId: string
  totalCount: number
  hasMore: boolean
  loadingMore: boolean
}>()

const emit = defineEmits<{
  (e: 'select', image: WorkspaceImageListItem): void
  (e: 'delete', image: WorkspaceImageListItem): void
  (e: 'load-more'): void
}>()
</script>

<style scoped>
h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #333;
}

.image-item {
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.image-item:hover {
  background: #f0f2f5;
}

.image-item.active {
  background: #ecf5ff;
  color: #409eff;
}

.image-main,
.image-meta,
.image-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.image-main {
  justify-content: space-between;
}

.image-meta {
  min-width: 0;
  flex: 1;
}

.image-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.image-split {
  color: #909399;
  font-size: 12px;
  text-transform: uppercase;
}

.empty {
  color: #999;
  font-size: 12px;
  text-align: center;
}

.load-more {
  display: flex;
  justify-content: center;
  padding: 8px 0 4px;
}
</style>
