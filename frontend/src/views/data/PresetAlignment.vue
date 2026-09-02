<template>
  <div class="alignment-page">
    <el-form label-width="110px" class="form">
      <el-form-item label="数据集"><el-select v-model="datasetId" @change="loadImages"><el-option v-for="item in datasets" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
      <el-form-item label="参考图"><el-select v-model="referenceId"><el-option v-for="item in images" :key="item.id" :label="item.filename" :value="item.id" /></el-select></el-form-item>
      <el-form-item label="目标图"><el-select v-model="imageId"><el-option v-for="item in images" :key="item.id" :label="item.filename" :value="item.id" /></el-select></el-form-item>
      <el-form-item label="最小置信度"><el-input-number v-model="minConfidence" :min="0" :max="1" :step="0.001" :precision="3" /></el-form-item>
      <el-form-item><el-button @click="estimate">估计偏移</el-button><el-button type="primary" @click="apply">校正标注</el-button></el-form-item>
    </el-form>
    <el-descriptions v-if="result" title="估计结果" :column="3" border><el-descriptions-item label="X 偏移">{{ result.dx }}</el-descriptions-item><el-descriptions-item label="Y 偏移">{{ result.dy }}</el-descriptions-item><el-descriptions-item label="置信度">{{ result.confidence }}</el-descriptions-item></el-descriptions>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getDatasets, getDatasetImages } from '@/api/dataset'
import { applyPresetAlignment, estimatePresetAlignment } from '@/api/annotation'
import type { Dataset, DatasetImage } from '@/types/dataset'
const datasets = ref<Dataset[]>([]); const images = ref<DatasetImage[]>([]); const datasetId = ref(''); const referenceId = ref(''); const imageId = ref(''); const minConfidence = ref(0); const result = ref<{ dx: number; dy: number; confidence: number } | null>(null)
onMounted(async () => { datasets.value = await getDatasets() })
async function loadImages() { images.value = await getDatasetImages(datasetId.value, { page_size: 1000 }); referenceId.value = ''; imageId.value = ''; result.value = null }
async function estimate() { if (!imageId.value || !referenceId.value) return; try { result.value = await estimatePresetAlignment(imageId.value, referenceId.value) } catch (err: unknown) { ElMessage.error(err instanceof Error ? err.message : '估计失败') } }
async function apply() { if (!imageId.value || !referenceId.value) return; try { const value = await applyPresetAlignment(imageId.value, referenceId.value, minConfidence.value); result.value = value; ElMessage.success(`已校正 ${value.corrected_annotations} 条标注`) } catch (err: unknown) { ElMessage.error(err instanceof Error ? err.message : '校正失败') } }
</script>
<style scoped>.alignment-page { max-width: 720px; }.form { margin-bottom: 24px; }</style>
