<template>
  <div class="log-list">
    <div class="page-header">
      <h3>操作日志</h3>
      <div class="filters">
        <el-select v-model="methodFilter" clearable placeholder="请求方法" style="width: 120px" @change="reload">
          <el-option label="POST" value="POST" />
          <el-option label="PUT" value="PUT" />
          <el-option label="DELETE" value="DELETE" />
        </el-select>
        <el-input
          v-model="usernameFilter"
          clearable
          placeholder="按操作人筛选"
          style="width: 180px"
          @keyup.enter="reload"
          @clear="reload"
        />
        <el-button :icon="Search" @click="reload">查询</el-button>
        <el-button v-if="canManage" type="danger" plain @click="handleClear">清空日志</el-button>
      </div>
    </div>

    <el-table :data="logs" border stripe v-loading="loading">
      <el-table-column prop="username" label="操作人" width="120">
        <template #default="{ row }">{{ row.username || '--' }}</template>
      </el-table-column>
      <el-table-column prop="method" label="方法" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="methodTagType(row.method)">{{ row.method }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="path" label="请求路径" min-width="260" show-overflow-tooltip />
      <el-table-column prop="status_code" label="状态码" width="90">
        <template #default="{ row }">
          <span :class="row.status_code >= 400 ? 'status-error' : 'status-ok'">{{ row.status_code }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="duration_ms" label="耗时" width="100">
        <template #default="{ row }">{{ row.duration_ms }} ms</template>
      </el-table-column>
      <el-table-column prop="ip" label="IP" width="130">
        <template #default="{ row }">{{ row.ip || '--' }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadData"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { clearAuditLogs, getAuditLogs, type AuditLog } from '@/api/audit'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canManage = computed(() => auth.hasPermission('system:manage'))

const logs = ref<AuditLog[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)
const methodFilter = ref('')
const usernameFilter = ref('')

onMounted(loadData)

async function loadData() {
  loading.value = true
  try {
    const result = await getAuditLogs({
      page: page.value,
      page_size: pageSize,
      username: usernameFilter.value || undefined,
      method: methodFilter.value || undefined,
    })
    logs.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  loadData()
}

async function handleClear() {
  try {
    await ElMessageBox.confirm('确定清空全部操作日志吗？该操作不可恢复。', '确认清空', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await clearAuditLogs()
    ElMessage.success('日志已清空')
    reload()
  } catch (error: unknown) {
    ElMessage.error(error instanceof Error ? error.message : '清空失败')
  }
}

function methodTagType(method: string): 'success' | 'warning' | 'danger' | 'info' {
  if (method === 'POST') return 'success'
  if (method === 'PUT') return 'warning'
  if (method === 'DELETE') return 'danger'
  return 'info'
}

function formatTime(value: string): string {
  return value ? new Date(value).toLocaleString() : '--'
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.filters {
  display: flex;
  gap: 8px;
  align-items: center;
}

.pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.status-ok {
  color: #67c23a;
}

.status-error {
  color: #f56c6c;
}
</style>
