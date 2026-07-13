<template>
  <div class="dashboard">
    <el-row :gutter="20" class="stat-row">
      <el-col :span="6" v-for="card in statCards" :key="card.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card-content">
            <div class="stat-info">
              <span class="stat-label">{{ card.label }}</span>
              <span class="stat-value">{{ card.value }}</span>
            </div>
            <el-icon class="stat-icon" :size="36"><component :is="card.icon" /></el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="16">
        <el-card>
          <template #header>工作流程</template>
          <div class="workflow">
            <div class="workflow-step" v-for="step in workflow" :key="step.title">
              <div class="step-circle">{{ step.num }}</div>
              <div class="step-text">
                <strong>{{ step.title }}</strong>
                <p>{{ step.desc }}</p>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>最近任务</template>
          <div class="recent-tasks">
            <p class="empty-hint">暂无任务记录</p>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { reactive, markRaw } from 'vue'
import { Files, Edit, Cpu, VideoPlay } from '@element-plus/icons-vue'

const statCards = reactive([
  { label: '数据集', value: '--', icon: markRaw(Files) },
  { label: '已标注图片', value: '--', icon: markRaw(Edit) },
  { label: '模型', value: '--', icon: markRaw(Cpu) },
  { label: '训练任务', value: '--', icon: markRaw(VideoPlay) },
])

const workflow = [
  {
    num: '1',
    title: '创建并导入数据集',
    desc: '创建数据集并上传 ZIP，识别图片、标注与划分信息。',
  },
  {
    num: '2',
    title: '检查与补充标注',
    desc: '在标注工作台检查类别与标注结果，补齐训练前数据。',
  },
  {
    num: '3',
    title: '创建数据集版本',
    desc: '冻结当前数据范围并校验可训练性，生成可追溯的数据版本。',
  },
  {
    num: '4',
    title: '导出训练版本',
    desc: '将版本导出为 YOLO 训练输入，生成 dataset.yaml 与划分结果。',
  },
  {
    num: '5',
    title: '发起训练并导出模型',
    desc: '选择训练输入和预训练模型，启动训练并将最佳模型导入模型库。',
  },
]
</script>

<style scoped>
.stat-row {
  margin-bottom: 20px;
}

.stat-card-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}

.stat-icon {
  color: #409eff;
}

.workflow {
  display: flex;
  flex-wrap: wrap;
  gap: 20px 12px;
  padding: 20px 0;
}

.workflow-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  flex: 1 1 180px;
  min-width: 0;
}

.step-circle {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  margin-bottom: 8px;
}

.step-text strong {
  display: block;
  margin-bottom: 4px;
}

.step-text p {
  font-size: 12px;
  color: #909399;
  margin: 0;
  line-height: 1.6;
}

.recent-tasks {
  min-height: 150px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-hint {
  color: #999;
  font-size: 14px;
}
</style>
