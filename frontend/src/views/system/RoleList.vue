<template>
  <div class="role-list">
    <div class="page-header">
      <h3>角色权限</h3>
      <el-button type="primary" :disabled="!canManage" @click="openCreate">新建角色</el-button>
    </div>

    <el-table :data="roles" border stripe v-loading="loading">
      <el-table-column prop="name" label="角色名称" width="160" />
      <el-table-column prop="description" label="描述" min-width="200">
        <template #default="{ row }">{{ row.description || '--' }}</template>
      </el-table-column>
      <el-table-column label="权限点" min-width="320">
        <template #default="{ row }">
          <el-tag
            v-for="permission in row.permissions"
            :key="permission"
            size="small"
            :type="permission === '*' ? 'danger' : 'info'"
            effect="plain"
            class="permission-tag"
          >
            {{ permission === '*' ? '全部权限' : permissionLabel(permission) }}
          </el-tag>
          <span v-if="!row.permissions.length" class="no-permission">无权限</span>
        </template>
      </el-table-column>
      <el-table-column prop="user_count" label="用户数" width="90" />
      <el-table-column prop="created_at" label="创建时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140" v-if="canManage">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" link :disabled="row.is_builtin" @click="handleDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showDialog" :title="editingRole ? '编辑角色' : '新建角色'" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="角色名" prop="name">
          <el-input v-model="form.name" :disabled="!!editingRole?.is_builtin" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="权限点" prop="permissions">
          <el-checkbox-group v-model="form.permissions">
            <el-checkbox
              v-for="(label, permission) in PERMISSION_LABELS"
              :key="permission"
              :value="permission"
            >
              {{ label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  createRole,
  deleteRole,
  getRoles,
  updateRole,
  type RoleResponse,
} from '@/api/user'
import { PERMISSION_LABELS } from '@/config/auth'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canManage = computed(() => auth.hasPermission('system:manage'))

const roles = ref<RoleResponse[]>([])
const loading = ref(false)
const saving = ref(false)
const showDialog = ref(false)
const editingRole = ref<RoleResponse | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({ name: '', description: '', permissions: [] as string[] })

const rules: FormRules = {
  name: [
    { required: true, message: '请输入角色名', trigger: 'blur' },
    { max: 50, message: '角色名最长 50 个字符', trigger: 'blur' },
  ],
}

onMounted(loadData)

async function loadData() {
  loading.value = true
  try {
    roles.value = await getRoles()
  } finally {
    loading.value = false
  }
}

function permissionLabel(permission: string): string {
  return PERMISSION_LABELS[permission] || permission
}

function openCreate() {
  editingRole.value = null
  form.name = ''
  form.description = ''
  form.permissions = []
  showDialog.value = true
}

function openEdit(row: RoleResponse) {
  editingRole.value = row
  form.name = row.name
  form.description = row.description || ''
  form.permissions = [...row.permissions]
  showDialog.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  saving.value = true
  try {
    if (editingRole.value) {
      await updateRole(editingRole.value.id, {
        name: form.name,
        description: form.description || undefined,
        permissions: form.permissions,
      })
      ElMessage.success('角色已更新')
    } else {
      await createRole({
        name: form.name,
        description: form.description || undefined,
        permissions: form.permissions,
      })
      ElMessage.success('角色已创建')
    }
    showDialog.value = false
    await loadData()
  } catch (error: unknown) {
    ElMessage.error(readError(error) || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: RoleResponse) {
  try {
    await ElMessageBox.confirm(`确定删除角色 ${row.name} 吗？`, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteRole(row.id)
    ElMessage.success('角色已删除')
    await loadData()
  } catch (error: unknown) {
    ElMessage.error(readError(error) || '删除失败')
  }
}

function formatTime(value: string): string {
  return value ? new Date(value).toLocaleString() : '--'
}

function readError(error: unknown): string {
  return error instanceof Error ? error.message : ''
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.permission-tag {
  margin-right: 6px;
  margin-bottom: 4px;
}

.no-permission {
  color: #909399;
  font-size: 12px;
}
</style>
