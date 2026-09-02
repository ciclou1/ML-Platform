<template>
  <div class="workflow-page" tabindex="0" @keydown.delete="deleteSelection">
    <aside class="palette">
      <el-input v-model="workflowName" placeholder="工作流名称" />
      <div class="palette-actions">
        <el-button :icon="DocumentAdd" @click="createNew">新建</el-button>
        <el-button type="primary" :icon="DocumentChecked" :loading="saving" @click="saveWorkflow">保存</el-button>
      </div>
      <el-select v-model="selectedWorkflowId" clearable placeholder="已保存工作流" @change="loadWorkflow">
        <el-option v-for="workflow in workflows" :key="workflow.id" :label="workflow.name" :value="workflow.id" />
      </el-select>
      <el-divider />
      <div class="operator-list">
        <div v-for="operator in operators" :key="operator" class="operator-item" draggable="true" @click="addNode(operator)" @dragstart="startDrag($event, operator)">
          <el-icon><Plus /></el-icon><span>{{ operatorLabel(operator) }}</span>
        </div>
      </div>
      <el-upload :auto-upload="false" accept=".csv" :show-file-list="false" :on-change="selectCsv">
        <el-button :disabled="!selectedWorkflowId" :icon="Upload">上传 CSV</el-button>
      </el-upload>
      <el-upload :auto-upload="false" accept=".csv" :show-file-list="false" :on-change="selectLookupCsv">
        <el-button :disabled="!selectedWorkflowId" :icon="Upload">上传关联表</el-button>
      </el-upload>
      <el-tag v-if="lookupCsvPath" size="small" type="success" class="lookup-tag">关联表已就绪</el-tag>
      <el-button type="success" :disabled="!csvPath" :icon="VideoPlay" @click="run">运行</el-button>
    </aside>

    <main class="workspace">
      <div class="canvas" @dragover.prevent="allowDrop" @drop.prevent="dropNode">
        <VueFlow v-model:nodes="nodes" v-model:edges="edges" :default-viewport="{ x: 0, y: 0, zoom: 1 }" fit-view-on-init @connect="connectNodes" @node-click="selectNode" @edge-click="selectEdge" @edges-delete="removeEdges" @pane-click="clearSelection">
          <template #node-default="nodeProps">
            <Handle class="node-handle" type="target" :position="Position.Left" :connectable="true" />
            <div class="flow-node" :class="{ selected: nodeProps.id === selectedNodeId }">
              <div class="node-title">{{ nodeLabel(nodeProps.data) }}</div><div class="node-meta">{{ nodeColumn(nodeProps.data) }}</div>
            </div>
            <Handle class="node-handle" type="source" :position="Position.Right" :connectable="true" />
          </template>
        </VueFlow>
      </div>
      <aside class="inspector">
        <template v-if="selectedNodeId">
          <div class="inspector-header"><span>{{ operatorLabel(selectedOperator) }}</span><el-button :icon="Delete" text type="danger" @click="removeSelectedNode" /></div>
          <el-form label-position="top" size="small">
            <el-form-item v-for="field in activeFields" :key="field.key" :label="field.label">
              <el-input-number
                v-if="field.type === 'number'"
                :model-value="numberValue(field.key)"
                :min="0"
                control-position="right"
                @update:model-value="(input: number | undefined) => setConfigValue(field.key, input)"
              />
              <el-checkbox
                v-else-if="field.type === 'switch'"
                :model-value="selectedConfig[field.key] === true"
                @update:model-value="(checked: boolean | string | number) => setConfigValue(field.key, checked)"
              >
                {{ field.placeholder }}
              </el-checkbox>
              <el-input
                v-else
                :model-value="stringValue(field.key)"
                :placeholder="field.placeholder"
                @update:model-value="(input: string) => setConfigValue(field.key, input)"
              />
            </el-form-item>
            <div v-if="activeHint" class="field-hint">{{ activeHint }}</div>
            <el-form-item v-if="selectedOperator === 'join' || selectedOperator === 'union'" label="关联表 CSV">
              <el-input v-model="selectedConfig.second_csv" placeholder="先在左侧上传关联表" />
            </el-form-item>
          </el-form>
        </template>
        <template v-else-if="selectedEdgeId">
          <div class="inspector-header"><span>连接线</span><el-button :icon="Delete" text type="danger" @click="removeSelectedEdge" /></div>
          <el-button type="danger" plain :icon="Delete" @click="removeSelectedEdge">删除连接线</el-button>
        </template>
        <el-empty v-else description="选择节点" :image-size="64" />
        <div v-if="activeTask" class="task-result">
          <el-tag :type="taskTagType(activeTask.status)">{{ activeTask.status }}</el-tag>
          <pre v-if="taskOutput">{{ taskOutput }}</pre>
          <div v-else-if="activeTask.error_message" class="task-error">{{ activeTask.error_message }}</div>
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef } from 'vue'
import { DocumentAdd, DocumentChecked, Delete, Plus, Upload, VideoPlay } from '@element-plus/icons-vue'
import { Handle, Position, VueFlow, useVueFlow } from '@vue-flow/core'
import type { Connection, Edge, Node } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import { ElMessage } from 'element-plus'
import { createWorkflow, getWorkflows, runWorkflow, updateWorkflow, uploadWorkflowCsv } from '@/api/workflow'
import { getTask, syncTask } from '@/api/task'
import type { Task } from '@/types/task'
import type { Workflow, WorkflowGraph } from '@/types/workflow'

interface WorkflowNodeData { label: string; operator: string; config: Record<string, string | number | boolean | undefined> }

const operatorLabels: Record<string, string> = {
  csv_source: 'CSV 输入', select_columns: '选择字段', rename_columns: '重命名字段', drop_columns: '删除字段', fill_missing: '填充空值', filter_equals: '等值筛选', filter_contains: '包含筛选', filter_gt: '大于筛选', filter_lt: '小于筛选', sort: '排序', limit: '限制行数', deduplicate: '去重', add_constant: '添加常量', cast_number: '转换数值', add: '加法', subtract: '减法', multiply: '乘法', divide: '除法', absolute: '绝对值', round: '四舍五入', clamp: '区间限制', moving_average: '移动平均', cumulative_sum: '累计求和', difference: '差分', normalize_minmax: '归一化', zscore: '标准化', bucket: '分桶', threshold: '阈值判断', flag_range: '范围标记', group_count: '分组计数', group_sum: '分组求和', group_mean: '分组均值', group_min: '分组最小值', group_max: '分组最大值', aggregate_count: '汇总计数', aggregate_sum: '汇总求和', aggregate_mean: '汇总均值', aggregate_min: '汇总最小值', aggregate_max: '汇总最大值', rolling_min: '滚动最小值', rolling_max: '滚动最大值', rolling_std: '滚动标准差', top_n: '前 N 条', bottom_n: '后 N 条', sample: '等距采样', pivot_count: '透视计数', join: '关联', union: '合并', quality_missing: '空值质检', quality_duplicates: '重复质检', export_csv: '导出 CSV',
}
const operators = Object.keys(operatorLabels)

/** 每个算子在检查器中渲染的配置字段（与后端 workflow_engine 的 config 契约一致） */
interface OperatorField {
  key: 'column' | 'value' | 'target' | 'count' | 'descending' | 'second_csv'
  label: string
  type: 'text' | 'number' | 'switch'
  placeholder?: string
}

const FIELD = {
  column: (label = '字段') => ({ key: 'column', label, type: 'text' }) as OperatorField,
  value: (label = '值', placeholder = '') => ({ key: 'value', label, type: 'text', placeholder }) as OperatorField,
  valueNumber: (label = '值') => ({ key: 'value', label, type: 'number' }) as OperatorField,
  target: (label = '输出字段（可选）') => ({ key: 'target', label, type: 'text' }) as OperatorField,
  count: (label = '数量') => ({ key: 'count', label, type: 'number' }) as OperatorField,
  descending: () => ({ key: 'descending', label: '', type: 'switch', placeholder: '倒序' }) as OperatorField,
}

const OPERATOR_FIELDS: Record<string, OperatorField[]> = {
  csv_source: [],
  export_csv: [],
  select_columns: [FIELD.value('列名（逗号分隔）', 'timestamp,device_id')],
  rename_columns: [FIELD.value('重命名（旧=新，逗号分隔）', 'old=new')],
  drop_columns: [FIELD.value('删除列（逗号分隔）', 'col1,col2')],
  fill_missing: [FIELD.column('字段'), FIELD.value('填充值', '0')],
  filter_equals: [FIELD.column(), FIELD.value('等于值')],
  filter_contains: [FIELD.column(), FIELD.value('包含文本')],
  filter_gt: [FIELD.column(), FIELD.valueNumber('大于')],
  filter_lt: [FIELD.column(), FIELD.valueNumber('小于')],
  sort: [FIELD.column(), FIELD.descending()],
  limit: [FIELD.count('保留行数')],
  deduplicate: [FIELD.column('去重字段')],
  add_constant: [FIELD.value('常量值'), FIELD.target()],
  cast_number: [FIELD.column()],
  add: [FIELD.column(), FIELD.valueNumber('加数'), FIELD.target()],
  subtract: [FIELD.column(), FIELD.valueNumber('减数'), FIELD.target()],
  multiply: [FIELD.column(), FIELD.valueNumber('乘数'), FIELD.target()],
  divide: [FIELD.column(), FIELD.valueNumber('除数'), FIELD.target()],
  absolute: [FIELD.column()],
  round: [FIELD.column(), FIELD.count('小数位')],
  clamp: [FIELD.column(), FIELD.value('下限,上限', '0,100')],
  moving_average: [FIELD.column(), FIELD.count('窗口大小'), FIELD.target()],
  cumulative_sum: [FIELD.column(), FIELD.target()],
  difference: [FIELD.column(), FIELD.target()],
  normalize_minmax: [FIELD.column(), FIELD.target()],
  zscore: [FIELD.column(), FIELD.target()],
  bucket: [FIELD.column(), FIELD.count('桶数'), FIELD.target()],
  threshold: [FIELD.column(), FIELD.valueNumber('阈值'), FIELD.target()],
  flag_range: [FIELD.column(), FIELD.value('下限,上限', '0,100'), FIELD.target()],
  group_count: [FIELD.column('分组字段')],
  group_sum: [FIELD.column('分组字段'), FIELD.value('数值字段')],
  group_mean: [FIELD.column('分组字段'), FIELD.value('数值字段')],
  group_min: [FIELD.column('分组字段'), FIELD.value('数值字段')],
  group_max: [FIELD.column('分组字段'), FIELD.value('数值字段')],
  aggregate_count: [FIELD.target('输出字段（可选）')],
  aggregate_sum: [FIELD.column('数值字段'), FIELD.target()],
  aggregate_mean: [FIELD.column('数值字段'), FIELD.target()],
  aggregate_min: [FIELD.column('数值字段'), FIELD.target()],
  aggregate_max: [FIELD.column('数值字段'), FIELD.target()],
  rolling_min: [FIELD.column(), FIELD.count('窗口大小'), FIELD.target()],
  rolling_max: [FIELD.column(), FIELD.count('窗口大小'), FIELD.target()],
  rolling_std: [FIELD.column(), FIELD.count('窗口大小'), FIELD.target()],
  top_n: [FIELD.column(), FIELD.count('N')],
  bottom_n: [FIELD.column(), FIELD.count('N')],
  sample: [FIELD.count('采样行数')],
  pivot_count: [FIELD.column('行字段'), FIELD.value('列字段')],
  join: [FIELD.column('左表键'), FIELD.target('右表键（可选）'), FIELD.value('引入列（逗号分隔，可选）')],
  union: [],
  quality_missing: [FIELD.column('字段（空=整行）'), FIELD.target()],
  quality_duplicates: [FIELD.column('字段（空=整行）'), FIELD.target()],
}

const OPERATOR_HINTS: Record<string, string> = {
  csv_source: '输入占位节点，无需配置；运行时使用左侧上传的 CSV。',
  export_csv: '输出占位节点，运行结果自动写出到 CSV。',
  join: '左连接：从关联表按键引入列；请先在左侧上传关联表。',
  union: '纵向合并主表与关联表；请先在左侧上传关联表。',
  sample: '按等间隔确定性抽取指定行数。',
}

const flow = useVueFlow()
const workflows = ref<Workflow[]>([])
const workflowName = ref('未命名工作流')
const selectedWorkflowId = ref('')
const csvPath = ref('')
const saving = ref(false)
const selectedNodeId = ref('')
const selectedEdgeId = ref('')
const draggedOperator = ref('')
const nodes = shallowRef<Node[]>([])
const edges = shallowRef<Edge[]>([])

const selectedOperator = ref('')
const selectedConfig = ref<WorkflowNodeData['config']>({})
const activeTask = ref<Task | null>(null)
const lookupCsvPath = ref('')
const activeFields = computed<OperatorField[]>(() => OPERATOR_FIELDS[selectedOperator.value] || [
  FIELD.column(),
  FIELD.value(),
  FIELD.target(),
  FIELD.count(),
  FIELD.descending(),
])
const activeHint = computed(() => OPERATOR_HINTS[selectedOperator.value] || '')
const taskOutput = computed(() => activeTask.value?.result ? JSON.stringify(activeTask.value.result, null, 2) : '')
let pollTimer: ReturnType<typeof setTimeout> | null = null

onMounted(loadWorkflows)
onUnmounted(clearPollTimer)

function createNew() { selectedWorkflowId.value = ''; workflowName.value = '未命名工作流'; csvPath.value = ''; nodes.value = []; edges.value = []; clearSelection(); activeTask.value = null }
function addNode(operator: string, position?: { x: number; y: number }) {
  const id = `${operator}-${crypto.randomUUID()}`
  const config: WorkflowNodeData['config'] = {}
  if ((operator === 'join' || operator === 'union') && lookupCsvPath.value) {
    config.second_csv = lookupCsvPath.value
  }
  nodes.value = [...nodes.value, { id, type: 'default', position: position || { x: 80 + nodes.value.length * 36, y: 100 + nodes.value.length * 30 }, data: { label: operator, operator, config } }]
  selectedNodeId.value = id; selectedEdgeId.value = ''; selectedOperator.value = operator; selectedConfig.value = config
}
function startDrag(event: DragEvent, operator: string) { draggedOperator.value = operator; event.dataTransfer?.setData('application/x-workflow-operator', operator); if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move' }
function allowDrop(event: DragEvent) { if (event.dataTransfer) event.dataTransfer.dropEffect = 'move' }
function dropNode(event: DragEvent) {
  const operator = event.dataTransfer?.getData('application/x-workflow-operator') || draggedOperator.value
  if (!operator) return
  addNode(operator, flow.screenToFlowCoordinate({ x: event.clientX, y: event.clientY }))
  draggedOperator.value = ''
}
function connectNodes(connection: Connection) {
  if (!connection.source || !connection.target) return
  edges.value = [...edges.value, {
    id: `edge-${crypto.randomUUID()}`,
    source: connection.source,
    target: connection.target,
    sourceHandle: connection.sourceHandle,
    targetHandle: connection.targetHandle,
  }]
}
function selectEdge(event: { edge: { id: string } }) { selectedEdgeId.value = event.edge.id; selectedNodeId.value = ''; selectedOperator.value = ''; selectedConfig.value = {} }
function removeEdges(deletedEdges: Edge[]) { const deletedIds = new Set(deletedEdges.map((edge) => edge.id)); edges.value = edges.value.filter((edge) => !deletedIds.has(edge.id)); if (deletedIds.has(selectedEdgeId.value)) selectedEdgeId.value = '' }
function removeSelectedEdge() { if (!selectedEdgeId.value) return; removeEdges(edges.value.filter((edge) => edge.id === selectedEdgeId.value)) }
function clearSelection() { selectedNodeId.value = ''; selectedEdgeId.value = ''; selectedOperator.value = ''; selectedConfig.value = {} }
function deleteSelection() { if (selectedEdgeId.value) removeSelectedEdge(); else removeSelectedNode() }
function selectNode(event: { node: { id: string } }) {
  selectedNodeId.value = event.node.id; selectedEdgeId.value = ''
  for (const node of nodes.value) {
    if (node.id !== event.node.id) continue
    const data = workflowNodeData(node.data)
    selectedOperator.value = data.operator
    selectedConfig.value = data.config
    return
  }
  selectedOperator.value = ''
  selectedConfig.value = {}
}
function removeSelectedNode() {
  if (!selectedNodeId.value) return
  const id = selectedNodeId.value
  const remainingNodes: Node[] = []
  const remainingEdges: Edge[] = []
  for (const node of nodes.value) if (node.id !== id) remainingNodes.push(node)
  for (const edge of edges.value) if (edge.source !== id && edge.target !== id) remainingEdges.push(edge)
  nodes.value = remainingNodes
  edges.value = remainingEdges
  clearSelection()
}
async function loadWorkflows() { try { workflows.value = await getWorkflows() } catch (err: unknown) { ElMessage.error(err instanceof Error ? err.message : '加载工作流失败') } }
async function loadWorkflow(id: string) {
  let workflow: Workflow | undefined
  for (const item of workflows.value) if (item.id === id) workflow = item
  if (!workflow) return
  workflowName.value = workflow.name; nodes.value = workflow.graph.nodes.map(toWorkflowNode).filter(hasNode); edges.value = workflow.graph.edges.map(toWorkflowEdge).filter(hasEdge); csvPath.value = ''; clearSelection(); activeTask.value = null
  await nextTick(); flow.fitView()
}
async function saveWorkflow() {
  saving.value = true
  try {
    const graph = serializeGraph()
    const workflow = selectedWorkflowId.value ? await updateWorkflow(selectedWorkflowId.value, { name: workflowName.value, graph }) : await createWorkflow({ name: workflowName.value, graph })
    selectedWorkflowId.value = workflow.id; await loadWorkflows(); ElMessage.success('工作流已保存')
  } catch (err: unknown) { ElMessage.error(err instanceof Error ? err.message : '保存失败') } finally { saving.value = false }
}
async function selectCsv(upload: { raw?: File }) { if (!selectedWorkflowId.value || !upload.raw) return; try { csvPath.value = (await uploadWorkflowCsv(selectedWorkflowId.value, upload.raw)).path; ElMessage.success('CSV 已上传') } catch (err: unknown) { ElMessage.error(err instanceof Error ? err.message : '上传失败') } }
async function selectLookupCsv(upload: { raw?: File }) {
  if (!selectedWorkflowId.value || !upload.raw) return
  try {
    lookupCsvPath.value = (await uploadWorkflowCsv(selectedWorkflowId.value, upload.raw)).path
    for (const node of nodes.value) {
      const data = workflowNodeData(node.data)
      if (data.operator === 'join' || data.operator === 'union') {
        data.config.second_csv = lookupCsvPath.value
      }
    }
    ElMessage.success('关联表已上传，join/union 节点已自动填入路径')
  } catch (err: unknown) { ElMessage.error(err instanceof Error ? err.message : '上传失败') }
}
function stringValue(key: OperatorField['key']): string {
  const value = selectedConfig.value[key]
  return typeof value === 'string' ? value : value === undefined || value === null ? '' : String(value)
}
function numberValue(key: OperatorField['key']): number | undefined {
  const value = selectedConfig.value[key]
  return typeof value === 'number' ? value : undefined
}
function setConfigValue(key: OperatorField['key'], input: string | number | boolean | undefined) {
  if (input === undefined || input === '') {
    delete selectedConfig.value[key]
    return
  }
  selectedConfig.value[key] = input
}
async function run() {
  if (!selectedWorkflowId.value || !csvPath.value) return
  try {
    activeTask.value = await runWorkflow(selectedWorkflowId.value, csvPath.value)
    pollTask(activeTask.value.id)
  } catch (err: unknown) { ElMessage.error(err instanceof Error ? err.message : '启动失败') }
}
function pollTask(taskId: string) {
  clearPollTimer()
  pollTimer = setTimeout(async () => {
    try {
      await syncTask(taskId)
      activeTask.value = await getTask(taskId)
      if (activeTask.value.status === 'running' || activeTask.value.status === 'pending') pollTask(taskId)
    } catch (err: unknown) { ElMessage.error(err instanceof Error ? err.message : '任务状态同步失败') }
  }, 800)
}
function clearPollTimer() { if (pollTimer) { clearTimeout(pollTimer); pollTimer = null } }
function taskTagType(status: string): 'info' | 'success' | 'warning' | 'danger' { return status === 'completed' ? 'success' : status === 'failed' ? 'danger' : status === 'running' ? 'warning' : 'info' }
function operatorLabel(operator: string): string { return operatorLabels[operator] || operator }
function nodeLabel(data: unknown): string { const value = workflowNodeData(data); return operatorLabel(value.operator || value.label) }
function nodeColumn(data: unknown): string { const value = workflowNodeData(data); return String(value.config.column || value.config.target || '') }
function serializeGraph(): WorkflowGraph {
  return {
    nodes: nodes.value.map((node) => ({ id: node.id, type: node.type, position: node.position, data: workflowNodeData(node.data) })),
    edges: edges.value.map((edge) => ({ id: edge.id, source: edge.source, target: edge.target, sourceHandle: edge.sourceHandle, targetHandle: edge.targetHandle })),
  }
}
function workflowNodeData(value: unknown): WorkflowNodeData {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return { label: '', operator: '', config: {} }
  const data = value as { label?: unknown; operator?: unknown; config?: unknown }
  return { label: String(data.label || data.operator || ''), operator: String(data.operator || data.label || ''), config: isConfig(data.config) ? data.config : {} }
}
function toWorkflowNode(value: Record<string, unknown>): Node | null {
  const position = value.position
  const data = value.data
  if (!position || typeof position !== 'object' || !data || typeof data !== 'object' || typeof value.id !== 'string') return null
  const point = position as { x?: unknown; y?: unknown }
  const details = workflowNodeData(data)
  return { id: value.id, type: 'default', position: { x: Number(point.x) || 0, y: Number(point.y) || 0 }, data: details }
}
function toWorkflowEdge(value: Record<string, unknown>): Edge | null {
  if (typeof value.id !== 'string' || typeof value.source !== 'string' || typeof value.target !== 'string') return null
  return { id: value.id, source: value.source, target: value.target }
}
function isConfig(value: unknown): value is WorkflowNodeData['config'] { return Boolean(value) && typeof value === 'object' && !Array.isArray(value) }
function hasNode(value: Node | null): value is Node { return value !== null }
function hasEdge(value: Edge | null): value is Edge { return value !== null }
</script>

<style scoped>
.workflow-page { height: calc(100vh - 110px); min-height: 620px; display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: 12px; outline: none; }
.palette, .inspector { min-width: 0; padding: 12px; border: 1px solid #dcdfe6; background: #fff; overflow: auto; }
.palette { display: flex; flex-direction: column; gap: 10px; }.palette-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }.operator-list { display: grid; gap: 4px; overflow: auto; padding-right: 4px; }
.operator-item { display: flex; align-items: center; gap: 8px; min-height: 32px; padding: 0 8px; border: 1px solid #e4e7ed; background: #fafafa; cursor: grab; user-select: none; font-size: 12px; }.operator-item:hover { border-color: #409eff; color: #409eff; }.operator-item:active { cursor: grabbing; }
.workspace { min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr) 220px; gap: 12px; }.canvas { min-width: 0; min-height: 620px; border: 1px solid #bfcbd9; background: #f8fafc; }
.flow-node { min-width: 150px; padding: 10px 12px; border: 1px solid #bfcbd9; background: #fff; color: #303133; }.flow-node.selected { border-color: #409eff; box-shadow: 0 0 0 2px rgb(64 158 255 / 16%); }.node-title { font-weight: 600; font-size: 13px; }.node-meta { min-height: 16px; margin-top: 4px; color: #909399; font-size: 12px; }
:deep(.node-handle) { width: 22px; height: 22px; border: 2px solid #fff; border-radius: 50%; background: #409eff; color: #fff; box-shadow: 0 0 0 1px #409eff; display: grid; place-items: center; font-size: 18px; font-weight: 500; line-height: 1; }
:deep(.node-handle::after) { content: '+'; transform: translateY(-1px); }
:deep(.node-handle:hover) { background: #1677d2; box-shadow: 0 0 0 3px rgb(64 158 255 / 20%); }
.inspector { display: flex; flex-direction: column; }.inspector-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; font-weight: 600; }
.task-result { margin-top: auto; padding-top: 16px; }.task-result pre { max-height: 180px; margin: 8px 0 0; padding: 8px; overflow: auto; background: #f5f7fa; font-size: 11px; white-space: pre-wrap; }.task-error { margin-top: 8px; color: #f56c6c; font-size: 12px; }
@media (max-width: 1000px) { .workflow-page { grid-template-columns: 190px minmax(0, 1fr); }.workspace { grid-template-columns: minmax(0, 1fr); }.inspector { display: none; } }
.lookup-tag { align-self: flex-start; }
.field-hint { color: #909399; font-size: 12px; line-height: 1.5; margin-bottom: 10px; }
</style>
