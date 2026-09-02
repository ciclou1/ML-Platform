<template>
  <div class="not-found">
    <div class="code">404</div>
    <div class="desc">页面不存在或已被移除</div>
    <el-button type="primary" @click="goHome">返回概览</el-button>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goHome() {
  router.push('/dashboard')
}
</script>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  height: 100%;
  min-height: 60vh;
}

.code {
  font-size: 72px;
  font-weight: 700;
  color: #909399;
}

.desc {
  font-size: 16px;
  color: #909399;
}
</style>
