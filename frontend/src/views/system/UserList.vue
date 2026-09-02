<template>
  <div class="user-list">
    <div class="page-header">
      <h3>用户管理</h3>
      <el-button type="primary" :disabled="!canManage" @click="openCreate">新建用户</el-button>
    </div>

    <el-table :data="users" border stripe v-loading="loading">
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="display_name" label="显示名" min-width="120">
        <template #default="{ row }">{{ row.display_name || '--' }}</template>
      </el-table-column>
      <el-table-column prop="role_name" label="角色" width="120">
        <template #default="{ row }">{{ row.role_name || '--' }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'danger'">
            {{ row.status === 'active' ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_login_at" label="最后登录" width="170">
        <template #default="{ row }">{{ formatTime(row.last_login_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="260" v-if="canManage">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="warning" link @click="openResetPassword(row)">重置密码</el-button>
          <el-button
            size="small"
            :type="row.status === 'active' ? 'info' : 'success'"
            link
            @click="toggleStatus(row)"
          >
            {{ row.status === 'active' ? '禁用' : '启用' }}
          </el-button>
          <el-button size="small" type="danger" link @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showDialog" :title="editingUser ? '编辑用户' : '新建用户'" width="420px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="!!editingUser" />
        </el-form-item>
        <el-form-item v-if="!editingUser" label="初始密码" prop="password">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="显示名" prop="display_name">
          <el-input v-model="form.display_name" />
        </el-form-item>
        <el-form-item label="角色" prop="role_id">
          <el-select v-model="form.role_id" placeholder="选择角色" style="width: 100%">
            <el-option v-for="role in roles" :key="role.id" :label="role.name" :value="role.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showPasswordDialog" title="重置密码" width="380px">
      <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="80px">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="pwdForm.password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPasswordDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleResetPassword">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  createUser,
  deleteUser,
  getRoles,
  getUsers,
  resetUserPassword,
  setUserStatus,
  updateUser,
  type RoleResponse,
  type UserResponse,
} from '@/api/user'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canManage = computed(() => auth.hasPermission('system:manage'))

const users = ref<UserResponse[]>([])
const roles = ref<RoleResponse[]>([])
const loading = ref(false)
const saving = ref(false)
const showDialog = ref(false)
const showPasswordDialog = ref(false)
const editingUser = ref<UserResponse | null>(null)
const resettingUser = ref<UserResponse | null>(null)
const formRef = ref<FormInstance>()
const pwdFormRef = ref<FormInstance>()

const form = reactive({ username: '', password: '', display_name: '', role_id: '' })
const pwdForm = reactive({ password: '' })

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名 2-50 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入初始密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  role_id: [{ required: true, message: '请选择角色', trigger: 'change' }],
}
const pwdRules: FormRules = {
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
}

onMounted(loadData)

async function loadData() {
  loading.value = true
  try {
    const [userRows, roleRows] = await Promise.all([getUsers(), getRoles()])
    users.value = userRows
    roles.value = roleRows
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingUser.value = null
  form.username = ''
  form.password = ''
  form.display_name = ''
  form.role_id = ''
  showDialog.value = true
}

function openEdit(row: UserResponse) {
  editingUser.value = row
  form.username = row.username
  form.display_name = row.display_name || ''
  form.role_id = row.role_id
  showDialog.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  saving.value = true
  try {
    if (editingUser.value) {
      await updateUser(editingUser.value.id, {
        display_name: form.display_name || undefined,
        role_id: form.role_id,
      })
      ElMessage.success('用户已更新')
    } else {
      await createUser({
        username: form.username,
        password: form.password,
        display_name: form.display_name || undefined,
        role_id: form.role_id,
      })
      ElMessage.success('用户已创建')
    }
    showDialog.value = false
    await loadData()
  } catch (error: unknown) {
    ElMessage.error(readError(error) || '保存失败')
  } finally {
    saving.value = false
  }
}

function openResetPassword(row: UserResponse) {
  resettingUser.value = row
  pwdForm.password = ''
  showPasswordDialog.value = true
}

async function handleResetPassword() {
  const valid = await pwdFormRef.value?.validate().catch(() => false)
  if (!valid || !resettingUser.value) {
    return
  }
  saving.value = true
  try {
    await resetUserPassword(resettingUser.value.id, pwdForm.password)
    ElMessage.success('密码已重置')
    showPasswordDialog.value = false
  } catch (error: unknown) {
    ElMessage.error(readError(error) || '重置失败')
  } finally {
    saving.value = false
  }
}

async function toggleStatus(row: UserResponse) {
  const next = row.status === 'active' ? 'disabled' : 'active'
  try {
    await setUserStatus(row.id, next)
    ElMessage.success(next === 'active' ? '用户已启用' : '用户已禁用')
    await loadData()
  } catch (error: unknown) {
    ElMessage.error(readError(error) || '操作失败')
  }
}

async function handleDelete(row: UserResponse) {
  try {
    await ElMessageBox.confirm(`确定删除用户 ${row.username} 吗？`, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteUser(row.id)
    ElMessage.success('用户已删除')
    await loadData()
  } catch (error: unknown) {
    ElMessage.error(readError(error) || '删除失败')
  }
}

function formatTime(value: string | null): string {
  if (!value) return '--'
  return new Date(value).toLocaleString()
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
</style>
