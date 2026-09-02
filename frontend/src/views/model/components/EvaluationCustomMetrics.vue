<template>
  <el-card class="report-row">
    <template #header>自定义评测指标</template>

    <el-descriptions v-if="weighted" :column="2" border size="small">
      <el-descriptions-item label="加权 Precision">
        {{ formatPercent(weighted.weighted_precision) }}
      </el-descriptions-item>
      <el-descriptions-item label="加权 Recall">
        {{ formatPercent(weighted.weighted_recall) }}
      </el-descriptions-item>
      <el-descriptions-item label="加权 F-beta">
        {{ formatPercent(weighted.weighted_fbeta) }}
      </el-descriptions-item>
      <el-descriptions-item label="加权 mAP50">
        {{ formatPercent(weighted.weighted_map50) }}
      </el-descriptions-item>
      <el-descriptions-item v-if="customConfig" label="F-beta beta" :span="2">
        {{ customConfig.beta }}
      </el-descriptions-item>
    </el-descriptions>

    <el-alert
      v-if="customMetricsError"
      :title="customMetricsError"
      type="warning"
      :closable="false"
      class="metric-error"
    />

    <el-table v-if="customMetricRows.length" :data="customMetricRows" border size="small" class="metric-table">
      <el-table-column prop="name" label="算法包指标" min-width="180" />
      <el-table-column prop="value" label="值" min-width="180" />
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatPercent } from '@/types/evaluation'
import type { EvaluationCustomConfig, WeightedEvaluationMetrics } from '@/types/evaluation'

const props = defineProps<{
  weighted?: WeightedEvaluationMetrics
  customConfig?: EvaluationCustomConfig
  customMetrics?: Record<string, unknown>
  customMetricsError?: string
}>()

const customMetricRows = computed(() => Object.entries(props.customMetrics || {}).map(([name, value]) => ({
  name,
  value: formatMetricValue(value),
})))

function formatMetricValue(value: unknown): string {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value.toFixed(4) : '--'
  }
  if (typeof value === 'string' || typeof value === 'boolean') {
    return String(value)
  }
  if (value === null || value === undefined) {
    return '--'
  }
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}
</script>

<style scoped>
.report-row {
  margin-top: 20px;
}

.metric-error,
.metric-table {
  margin-top: 12px;
}
</style>
