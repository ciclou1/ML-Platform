<template>
  <div class="config-page">
    <div class="page-header">
      <h3>系统配置</h3>
    </div>

    <el-row :gutter="16" v-loading="loading">
      <el-col :span="12">
        <el-card header="应用">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="平台名称">{{ config?.app_name || '--' }}</el-descriptions-item>
            <el-descriptions-item label="运行环境">{{ config?.app_env || '--' }}</el-descriptions-item>
            <el-descriptions-item label="最大上传">
              {{ config ? `${config.max_upload_size_mb} MB` : '--' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card header="存储" class="gap-top">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="存储后端">{{ config?.storage_backend || '--' }}</el-descriptions-item>
            <el-descriptions-item label="存储路径">{{ config?.storage_root || '--' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card header="数据库">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="PostgreSQL">{{ config?.postgres_host || '--' }}</el-descriptions-item>
            <el-descriptions-item label="数据库名">{{ config?.postgres_db || '--' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card header="框架版本" class="gap-top">
          <el-descriptions :column="1" border>
            <el-descriptions-item
              v-for="(value, name) in config?.versions || {}"
              :key="name"
              :label="String(name)"
            >
              {{ value }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-alert
      class="gap-top"
      type="info"
      :closable="false"
      show-icon
      title="系统配置为只读展示，来源于后端环境变量与运行环境；如需调整请在部署环境修改 .env 后重启服务。"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getSystemConfig, type SystemConfig } from '@/api/system'

const config = ref<SystemConfig | null>(null)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    config.value = await getSystemConfig()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
}

.gap-top {
  margin-top: 16px;
}
</style>
