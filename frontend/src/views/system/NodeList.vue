<template>
  <div class="node-list">
    <div class="page-header">
      <h3>边缘节点</h3>
      <el-button type="primary" @click="registerVisible = true">注册节点</el-button>
    </div>

    <el-alert
      type="info"
      :closable="false"
      title="节点通过一次性令牌注册，之后轮询平台拉取部署与推理请求，本地执行并回传结果。运行：python scripts/node_agent.py --base http://localhost:8000/api/v1 --node-id <id> --token <token>"
      style="margin-bottom: 12px"
    />

    <el-table :data="nodes" border stripe>
      <el-table-column prop="name" label="节点名称" min-width="160" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'online' ? 'success' : 'info'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最近心跳" width="180">
        <template #default="{ row }">{{ row.last_heartbeat ? new Date(row.last_heartbeat).toLocaleString() : '--' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click="openDeployments(row)">部署</el-button>
          <el-button size="small" type="primary" link @click="openDeploymentList(row)">部署记录</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="registerVisible" title="注册节点" width="420px" @closed="resetRegister">
      <el-form label-width="80px">
        <el-form-item label="节点名称" required>
          <el-input v-model="registerName" placeholder="如 edge-node-01" />
        </el-form-item>
      </el-form>
      <el-alert
        v-if="registeredToken"
        type="success"
        :closable="false"
        title="节点令牌（仅显示一次，请妥善保存）"
      >
        <pre class="token-box">{{ registeredToken }}</pre>
      </el-alert>
      <template #footer>
        <el-button @click="registerVisible = false">关闭</el-button>
        <el-button type="primary" :loading="registering" @click="handleRegister">
          {{ registeredToken ? '再注册一个' : '注册' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deployVisible" title="部署算法到节点" width="480px">
      <el-form label-width="120px">
        <el-form-item label="算法包版本">
          <el-select v-model="selectedVersionId" style="width: 100%">
            <el-option
              v-for="version in publishedVersions"
              :key="version.id"
              :label="`${packageName(version.package_id)} / ${version.version}`"
              :value="version.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deployVisible = false">取消</el-button>
        <el-button type="primary" :loading="deploying" @click="handleDeploy">部署</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="deploymentListVisible" :title="`${activeNode?.name ?? ''} · 部署记录`" size="600px">
      <el-table :data="deployments" border>
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column label="最近结果" min-width="240">
          <template #default="{ row }">
            <pre v-if="row.last_result" class="result-box">{{ JSON.stringify(row.last_result, null, 2) }}</pre>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              link
              :disabled="row.pending_params != null"
              @click="handlePushInfer(row)"
            >
              下发推理
            </el-button>
            <el-button size="small" type="danger" link @click="handleUndeploy(row.id)">卸载</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <el-dialog v-model="inferVisible" title="下发远程推理" width="520px">
      <el-input v-model="inferParams" type="textarea" :rows="4" placeholder='{"values": [1, 2, 3]}' />
      <template #footer>
        <el-button @click="inferVisible = false">取消</el-button>
        <el-button type="primary" @click="handleInferSubmit">下发</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deployToNode,
  getNodeDeployments,
  getNodes,
  pushNodeInfer,
  registerNode,
  undeployFromNode,
} from '@/api/node'
import { getAlgorithmPackages, getAlgorithmPackageVersions } from '@/api/algorithmPackage'
import type { EdgeNode, NodeDeployment } from '@/types/node'
import type { AlgorithmPackageVersion } from '@/types/algorithmPackage'

const nodes = ref<EdgeNode[]>([])
const registerVisible = ref(false)
const registerName = ref('')
const registeredToken = ref('')
const registering = ref(false)
const activeNode = ref<EdgeNode | null>(null)
const deployVisible = ref(false)
const deploying = ref(false)
const selectedVersionId = ref('')
const publishedVersions = ref<AlgorithmPackageVersion[]>([])
const deployments = ref<NodeDeployment[]>([])
const deploymentListVisible = ref(false)
const inferVisible = ref(false)
const inferParams = ref('{"values": [1, 2, 3]}')
const activeDeployment = ref<NodeDeployment | null>(null)

onMounted(loadNodes)

async function loadNodes() {
  try {
    nodes.value = (await getNodes()) || []
  } catch {
    nodes.value = []
  }
}

async function handleRegister() {
  if (!registerName.value.trim()) {
    ElMessage.warning('请输入节点名称')
    return
  }
  registering.value = true
  try {
    const result = await registerNode(registerName.value.trim())
    registeredToken.value = result.token
    registerName.value = ''
    ElMessage.success('节点注册成功')
    loadNodes()
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '注册失败')
  } finally {
    registering.value = false
  }
}

function resetRegister() {
  registeredToken.value = ''
  registerName.value = ''
}

async function openDeployments(node: EdgeNode) {
  activeNode.value = node
  try {
    const packages = (await getAlgorithmPackages()) || []
    const versions: AlgorithmPackageVersion[] = []
    for (const pkg of packages) {
      versions.push(...((await getAlgorithmPackageVersions(pkg.id)) || []))
    }
    publishedVersions.value = versions.filter((v) => v.status === 'published')
    selectedVersionId.value = publishedVersions.value[0]?.id || ''
    deployVisible.value = true
  } catch {
    publishedVersions.value = []
    ElMessage.error('加载算法包失败')
  }
}

function packageName(packageId: string): string {
  return packageId.slice(0, 8)
}

async function handleDeploy() {
  if (!activeNode.value || !selectedVersionId.value) {
    ElMessage.warning('请选择要部署的算法版本')
    return
  }
  deploying.value = true
  try {
    await deployToNode(activeNode.value.id, selectedVersionId.value)
    ElMessage.success('部署成功')
    deployVisible.value = false
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '部署失败')
  } finally {
    deploying.value = false
  }
}

async function openDeploymentList(node: EdgeNode) {
  activeNode.value = node
  deploymentListVisible.value = true
  try {
    deployments.value = (await getNodeDeployments(node.id)) || []
  } catch {
    deployments.value = []
  }
}

function handlePushInfer(deployment: NodeDeployment) {
  activeDeployment.value = deployment
  inferVisible.value = true
}

async function handleInferSubmit() {
  if (!activeDeployment.value) return
  try {
    const params = JSON.parse(inferParams.value || '{}')
    await pushNodeInfer(activeDeployment.value.id, params)
    ElMessage.success('推理请求已下发，等待节点执行')
    inferVisible.value = false
    if (activeNode.value) {
      deployments.value = (await getNodeDeployments(activeNode.value.id)) || []
    }
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '下发失败')
  }
}

async function handleUndeploy(deploymentId: string) {
  try {
    await ElMessageBox.confirm('确定卸载该部署？', '确认', { type: 'warning' })
    await undeployFromNode(deploymentId)
    ElMessage.success('已卸载')
    if (activeNode.value) {
      deployments.value = (await getNodeDeployments(activeNode.value.id)) || []
    }
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

.token-box {
  background: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  word-break: break-all;
  font-size: 12px;
}

.result-box {
  background: #f5f7fa;
  padding: 6px;
  border-radius: 4px;
  font-size: 11px;
  margin: 0;
  max-height: 120px;
  overflow: auto;
}
</style>
