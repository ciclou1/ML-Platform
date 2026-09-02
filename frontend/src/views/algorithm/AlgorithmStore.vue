<template>
  <div class="algorithm-store">
    <div class="page-header">
      <h3>算法商店</h3>
      <el-button type="primary" @click="importVisible = true">导入算法包</el-button>
    </div>

    <el-alert
      type="info"
      :closable="false"
      title="算法包 = 自研推理代码 + 可选权重 + 元数据。导入后可在本机运行，也可下发给边缘节点（后续里程碑）。"
      style="margin-bottom: 12px"
    />

    <el-table :data="packages" border stripe>
      <el-table-column prop="name" label="算法名称" min-width="180" />
      <el-table-column prop="framework" label="框架" width="120" />
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click="openVersions(row)">版本</el-button>
          <el-button size="small" type="danger" link @click="handleDelete(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="importVisible" title="导入算法包" width="560px" @closed="resetImportForm">
      <el-form :model="importForm" label-width="100px">
        <el-form-item label="算法名称" required>
          <el-input v-model="importForm.name" placeholder="算法包名称" />
        </el-form-item>
        <el-form-item label="版本" required>
          <el-input v-model="importForm.version" placeholder="如 v1.0.0" />
        </el-form-item>
        <el-form-item label="框架">
          <el-input v-model="importForm.framework" placeholder="默认 custom" />
        </el-form-item>
        <el-form-item label="入口">
          <el-input v-model="importForm.entrypoint" placeholder="默认 inference.py:run" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="importForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="ZIP 文件" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".zip"
            :on-change="handleFileChange"
            :on-remove="() => (importForm.file = null)"
          >
            <el-button type="primary" plain>选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">
                zip 内需包含推理入口文件（如 inference.py），可选 weights/ 目录
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="handleImport">导入</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="versionsVisible" :title="`${activePackage?.name ?? ''} · 版本管理`" size="600px">
      <el-table :data="versions" border>
        <el-table-column prop="version" label="版本" width="120" />
        <el-table-column prop="entrypoint" label="入口" min-width="160" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="versionTag(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'draft'"
              size="small"
              type="success"
              link
              @click="handlePublish(row)"
            >
              发布
            </el-button>
            <el-button
              v-if="row.status === 'published'"
              size="small"
              type="warning"
              link
              @click="handleDeprecate(row)"
            >
              弃用
            </el-button>
            <el-button size="small" type="primary" link @click="handleDownload(row)">
              下载
            </el-button>
            <el-button size="small" type="primary" link @click="handleRun(row)">
              运行
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <el-dialog v-model="runVisible" title="运行算法包" width="520px">
      <el-alert type="info" :closable="false" title="输入参数以 JSON 形式传入" style="margin-bottom: 12px" />
      <el-input v-model="runParams" type="textarea" :rows="5" />
      <div v-if="runResult" style="margin-top: 12px">
        <el-divider>运行结果</el-divider>
        <pre class="result-box">{{ runResult }}</pre>
      </div>
      <template #footer>
        <el-button @click="runVisible = false">关闭</el-button>
        <el-button type="primary" :loading="running" @click="handleRunSubmit">运行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import {
  deleteAlgorithmPackage,
  deprecateAlgorithmVersion,
  getAlgorithmPackages,
  getAlgorithmPackageVersions,
  importAlgorithmPackage,
  publishAlgorithmVersion,
  createAlgorithmInference,
  algorithmVersionDownloadUrl,
} from '@/api/algorithmPackage'
import { getTask, getTaskProgress, startTask } from '@/api/task'
import type { AlgorithmPackage, AlgorithmPackageVersion } from '@/types/algorithmPackage'

const packages = ref<AlgorithmPackage[]>([])
const versions = ref<AlgorithmPackageVersion[]>([])
const activePackage = ref<AlgorithmPackage | null>(null)
const versionsVisible = ref(false)
const importVisible = ref(false)
const importing = ref(false)
const runVisible = ref(false)
const running = ref(false)
const activeVersion = ref<AlgorithmPackageVersion | null>(null)
const runParams = ref('{"values": [1, 2, 3]}')
const runResult = ref('')

const importForm = ref({
  name: '',
  version: '',
  framework: 'custom',
  entrypoint: 'inference.py:run',
  description: '',
  file: null as File | null,
})

onMounted(loadPackages)

async function loadPackages() {
  try {
    packages.value = (await getAlgorithmPackages()) || []
  } catch {
    packages.value = []
  }
}

async function openVersions(pkg: AlgorithmPackage) {
  activePackage.value = pkg
  versionsVisible.value = true
  try {
    versions.value = (await getAlgorithmPackageVersions(pkg.id)) || []
  } catch {
    versions.value = []
  }
}

function handleFileChange(uploadFile: UploadFile) {
  const file = uploadFile.raw
  if (file) {
    importForm.value.file = file
  }
}

function resetImportForm() {
  importForm.value = {
    name: '',
    version: '',
    framework: 'custom',
    entrypoint: 'inference.py:run',
    description: '',
    file: null,
  }
}

async function handleImport() {
  const { name, version, file } = importForm.value
  if (!name || !version || !file) {
    ElMessage.warning('请填写名称、版本并选择 ZIP 文件')
    return
  }
  importing.value = true
  try {
    await importAlgorithmPackage({
      name,
      version,
      framework: importForm.value.framework || 'custom',
      entrypoint: importForm.value.entrypoint || 'inference.py:run',
      description: importForm.value.description || undefined,
      file,
    })
    ElMessage.success('算法包导入成功')
    importVisible.value = false
    loadPackages()
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '导入失败')
  } finally {
    importing.value = false
  }
}

async function handlePublish(version: AlgorithmPackageVersion) {
  await publishAlgorithmVersion(version.id)
  ElMessage.success('已发布')
  if (activePackage.value) openVersions(activePackage.value)
}

async function handleDeprecate(version: AlgorithmPackageVersion) {
  await deprecateAlgorithmVersion(version.id)
  ElMessage.success('已弃用')
  if (activePackage.value) openVersions(activePackage.value)
}

function handleDownload(version: AlgorithmPackageVersion) {
  window.open(algorithmVersionDownloadUrl(version.id), '_blank')
}

function versionTag(status: string): 'info' | 'success' | 'warning' {
  if (status === 'published') return 'success'
  if (status === 'deprecated') return 'warning'
  return 'info'
}

function handleRun(version: AlgorithmPackageVersion) {
  activeVersion.value = version
  runResult.value = ''
  runVisible.value = true
}

async function handleRunSubmit() {
  if (!activeVersion.value) return
  running.value = true
  try {
    let params: Record<string, unknown>
    try {
      params = JSON.parse(runParams.value || '{}')
    } catch {
      ElMessage.error('参数不是合法 JSON')
      return
    }
    const task = await createAlgorithmInference(activeVersion.value.id, params)
    await startTask(task.id)
    // 轮询结果
    for (let i = 0; i < 30; i++) {
      const progress = await getTaskProgress(task.id)
      if (progress.progress >= 100) {
        const t = await getTask(task.id)
        runResult.value = JSON.stringify(t.result?.output ?? t.result, null, 2)
        break
      }
      await new Promise((resolve) => setTimeout(resolve, 1000))
    }
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '运行失败')
  } finally {
    running.value = false
  }
}

async function handleDelete(id: string) {
  try {
    await ElMessageBox.confirm('确定删除该算法包及其全部版本？', '确认', { type: 'warning' })
    await deleteAlgorithmPackage(id)
    ElMessage.success('已删除')
    loadPackages()
  } catch {
    // cancelled
  }
}
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.result-box {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 240px;
  overflow: auto;
}
</style>
