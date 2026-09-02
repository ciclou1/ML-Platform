<template>
  <div class="app-root">
    <div v-show="loading.isLoading" class="global-loading-bar" />
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { useLoadingStore } from '@/stores/loading'

const loading = useLoadingStore()
</script>

<style scoped>
.app-root {
  height: 100%;
}

.global-loading-bar {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 9999;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, #409eff, #67c23a, #409eff);
  background-size: 200% 100%;
  animation: loading-slide 1s linear infinite;
}

@keyframes loading-slide {
  from {
    background-position: 0% 0;
  }
  to {
    background-position: -200% 0;
  }
}
</style>
