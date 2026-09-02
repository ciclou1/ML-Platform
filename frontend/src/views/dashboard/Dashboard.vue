<template>
  <div class="dashboard" v-loading="loading">
    <el-row :gutter="20" class="stat-row">
      <el-col :xs="24" :sm="12" :lg="6" v-for="card in statCards" :key="card.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card-content">
            <div class="stat-info">
              <span class="stat-label">{{ card.label }}</span>
              <span class="stat-value">{{ card.value }}</span>
              <span class="stat-note">{{ card.note }}</span>
            </div>
            <el-icon class="stat-icon" :size="36"><component :is="card.icon" /></el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="content-row">
      <el-col :xs="24" :lg="16">
        <el-card>
          <template #header>
            <div class="card-header"><span>最近任务</span><el-button link type="primary" @click="router.push('/model/training')">查看全部</el-button></div>
          </template>
          <el-table :data="overview.recent_tasks" size="small" empty-text="暂无任务记录">
            <el-table-column prop="name" label="任务名称" min-width="170" show-overflow-tooltip />
            <el-table-column prop="task_type" label="类型" width="100">
              <template #default="{ row }">{{ taskTypeLabel(row.task_type) }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }"><el-tag size="small" :type="taskStatusType(row.status)">{{ taskStatusLabel(row.status) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="进度" width="120">
              <template #default="{ row }"><el-progress :percentage="Math.max(0, Math.min(100, row.progress || 0))" :stroke-width="8" :show-text="false" /><span class="progress-text">{{ row.progress || 0 }}%</span></template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="165">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="8">
        <el-card>
          <template #header><div class="card-header"><span>审核与返工</span><el-button link type="primary" @click="router.push('/annotation/review')">进入审核</el-button></div></template>
          <div class="review-summary">
            <div class="review-row"><span>待审核</span><strong class="warning">{{ overview.pending_review_count }}</strong></div>
            <div class="review-row"><span>返工队列</span><strong class="danger">{{ overview.rejected_review_count }}</strong></div>
            <div class="review-row"><span>已通过</span><strong class="success">{{ overview.completed_review_count }}</strong></div>
          </div>
          <el-alert v-if="overview.rejected_review_count > 0" type="warning" :closable="false" show-icon class="rework-alert">
            有 {{ overview.rejected_review_count }} 条驳回记录待返工，可在质检审核中筛选“已驳回”查看原因和图片。
          </el-alert>
          <el-empty v-else description="暂无返工记录" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <el-card class="workflow-card">
      <template #header>工作流程</template>
      <div class="workflow">
        <div class="workflow-step" v-for="step in workflow" :key="step.title">
          <div class="step-circle">{{ step.num }}</div>
          <div class="step-text"><strong>{{ step.title }}</strong><p>{{ step.desc }}</p></div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Files, Edit, Cpu, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getDashboardOverview, type DashboardOverview } from '@/api/stats'

const router = useRouter()
const loading = ref(false)
const overview = reactive<DashboardOverview>({
  dataset_count: 0,
  image_count: 0,
  annotated_image_count: 0,
  model_count: 0,
  training_task_count: 0,
  running_task_count: 0,
  pending_review_count: 0,
  rejected_review_count: 0,
  completed_review_count: 0,
  recent_tasks: [],
})

const statCards = computed(() => [
  { label: '数据集', value: overview.dataset_count, note: `${overview.image_count} 张图片`, icon: markRaw(Files) },
  { label: '已标注图片', value: overview.annotated_image_count, note: `共 ${overview.image_count} 张`, icon: markRaw(Edit) },
  { label: '模型', value: overview.model_count, note: '模型库总数', icon: markRaw(Cpu) },
  { label: '训练任务', value: overview.training_task_count, note: `运行中 ${overview.running_task_count}`, icon: markRaw(VideoPlay) },
])

const workflow = [
  { num: '1', title: '创建并导入数据集', desc: '创建数据集并上传 ZIP，识别图片、标注与划分信息。' },
  { num: '2', title: '标注与质检审核', desc: '按批次分配图片，完成标注后提交质检，驳回记录进入返工队列。' },
  { num: '3', title: '创建数据集版本', desc: '冻结当前数据范围并校验可训练性，生成可追溯的数据版本。' },
  { num: '4', title: '导出训练输入', desc: '将版本导出为 YOLO 训练输入，生成 dataset.yaml 与划分结果。' },
  { num: '5', title: '启动训练并导出模型', desc: '选择训练输入和预训练模型，启动训练并导出最佳模型。' },
]

onMounted(loadOverview)

async function loadOverview() {
  loading.value = true
  try {
    Object.assign(overview, await getDashboardOverview())
  } catch (error) {
    ElMessage.error(readError(error) || '概览数据加载失败')
  } finally {
    loading.value = false
  }
}

function taskTypeLabel(type: string) {
  return ({ training: '训练', evaluation: '评估', inference: '推理', video_import: '视频抽帧', preprocess: '预处理', workflow: '时序组态' } as Record<string, string>)[type] || type
}

function taskStatusLabel(status: string) {
  return ({ pending: '等待中', running: '运行中', completed: '已完成', failed: '失败', cancelled: '已取消' } as Record<string, string>)[status] || status
}

function taskStatusType(status: string) {
  return ({ pending: 'info', running: 'warning', completed: 'success', failed: 'danger', cancelled: 'info' } as Record<string, 'info' | 'warning' | 'success' | 'danger'>)[status] || 'info'
}

function formatTime(value: string) {
  return value ? new Date(value).toLocaleString() : '--'
}

function readError(error: unknown) {
  return error instanceof Error ? error.message : ''
}
</script>

<style scoped>
.stat-row { margin-bottom: 20px; }
.content-row { margin-bottom: 20px; }
.stat-card-content { display: flex; justify-content: space-between; align-items: center; }
.stat-info { display: flex; flex-direction: column; gap: 4px; }
.stat-label { font-size: 14px; color: #909399; }
.stat-value { font-size: 28px; font-weight: 700; color: #303133; }
.stat-note { color: #909399; font-size: 12px; }
.stat-icon { color: #409eff; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.progress-text { display: inline-block; margin-top: 3px; font-size: 11px; color: #909399; }
.review-summary { display: grid; gap: 16px; padding: 8px 4px 18px; }
.review-row { display: flex; justify-content: space-between; align-items: center; color: #606266; }
.review-row strong { font-size: 24px; }
.warning { color: #e6a23c; }
.danger { color: #f56c6c; }
.success { color: #67c23a; }
.rework-alert { line-height: 1.5; }
.workflow-card { margin-bottom: 20px; }
.workflow { display: flex; flex-wrap: wrap; gap: 20px 12px; padding: 20px 0; }
.workflow-step { display: flex; flex-direction: column; align-items: center; text-align: center; flex: 1 1 180px; min-width: 0; }
.step-circle { width: 40px; height: 40px; border-radius: 50%; background: #409eff; color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; margin-bottom: 8px; }
.step-text strong { display: block; margin-bottom: 4px; }
.step-text p { font-size: 12px; color: #909399; margin: 0; line-height: 1.6; }
</style>
