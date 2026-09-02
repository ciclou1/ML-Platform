import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/Login.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: () => import('@/components/layout/AppLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/Dashboard.vue'),
        meta: { title: '概览' },
      },
      {
        path: 'data/datasets',
        name: 'Datasets',
        component: () => import('@/views/data/DatasetList.vue'),
        meta: { title: '数据集管理' },
      },
      {
        path: 'data/videos',
        name: 'Videos',
        component: () => import('@/views/data/VideoList.vue'),
        meta: { title: '视频接入' },
      },
      {
        path: 'data/preprocess',
        name: 'Preprocess',
        component: () => import('@/views/data/PreprocessList.vue'),
        meta: { title: '预处理任务' },
      },
      {
        path: 'data/versions',
        name: 'DatasetVersions',
        component: () => import('@/views/data/DatasetVersionList.vue'),
        meta: { title: '数据集版本 / 导出记录' },
      },
      {
        path: 'data/versions/new',
        name: 'DatasetVersionCreate',
        component: () => import('@/views/data/DatasetVersionCreate.vue'),
        meta: { title: '新建数据集版本' },
      },
      {
        path: 'data/versions/compare',
        name: 'DatasetVersionCompare',
        component: () => import('@/views/data/DatasetVersionCompare.vue'),
        meta: { title: '数据集版本对比' },
      },
      {
        path: 'data/versions/rules',
        name: 'DatasetVersionRules',
        component: () => import('@/views/data/DatasetVersionRules.vue'),
        meta: { title: '版本规则' },
      },
      {
        path: 'data/versions/validation/:versionId',
        name: 'DatasetVersionValidation',
        component: () => import('@/views/data/DatasetVersionValidation.vue'),
        meta: { title: '版本校验结果' },
      },
      {
        path: 'data/versions/exports/:recordId',
        name: 'DatasetExportRecordDetail',
        component: () => import('@/views/data/DatasetExportRecordDetail.vue'),
        meta: { title: '导出记录详情' },
      },
      {
        path: 'annotation/workspace/:datasetId?',
        name: 'AnnotationWorkspace',
        component: () => import('@/views/annotation/AnnotationWorkspace.vue'),
        meta: { title: '标注工作台' },
      },
      {
        path: 'annotation/batches',
        name: 'AnnotationBatches',
        component: () => import('@/views/annotation/BatchList.vue'),
        meta: { title: '标注批次' },
      },
      {
        path: 'annotation/review',
        name: 'AnnotationReview',
        component: () => import('@/views/annotation/ReviewList.vue'),
        meta: { title: '质检审核' },
      },
      {
        path: 'model/list',
        name: 'Models',
        component: () => import('@/views/model/ModelList.vue'),
        meta: { title: '模型管理' },
      },
      {
        path: 'model/training',
        name: 'Training',
        component: () => import('@/views/model/TrainingList.vue'),
        meta: { title: '训练任务' },
      },
      {
        path: 'model/evaluation',
        name: 'Evaluation',
        component: () => import('@/views/model/EvaluationReport.vue'),
        meta: { title: '模型评估' },
      },
      {
        path: 'model/evaluation-history',
        name: 'EvaluationHistory',
        component: () => import('@/views/model/EvaluationHistory.vue'),
        meta: { title: '评估历史' },
      },
      {
        path: 'model/inference',
        name: 'Inference',
        component: () => import('@/views/model/InferenceWorkspace.vue'),
        meta: { title: '模型推理' },
      },
      {
        path: 'algorithm/store',
        name: 'AlgorithmStore',
        component: () => import('@/views/algorithm/AlgorithmStore.vue'),
        meta: { title: '算法商店' },
      },
      { path: 'data/preset-alignment', name: 'PresetAlignment', component: () => import('@/views/data/PresetAlignment.vue'), meta: { title: '预置位纠偏' } },
      {
        path: 'algorithm/workflows',
        name: 'WorkflowEditor',
        component: () => import('@/views/algorithm/WorkflowEditor.vue'),
        meta: { title: '时序算法组态' },
      },
      {
        path: 'system/users',
        name: 'Users',
        component: () => import('@/views/system/UserList.vue'),
        meta: { title: '用户管理' },
      },
      {
        path: 'system/roles',
        name: 'Roles',
        component: () => import('@/views/system/RoleList.vue'),
        meta: { title: '角色权限' },
      },
      {
        path: 'system/logs',
        name: 'Logs',
        component: () => import('@/views/system/LogList.vue'),
        meta: { title: '操作日志' },
      },
      {
        path: 'system/config',
        name: 'Config',
        component: () => import('@/views/system/ConfigPage.vue'),
        meta: { title: '系统配置' },
      },
      {
        path: 'system/nodes',
        name: 'EdgeNodes',
        component: () => import('@/views/system/NodeList.vue'),
        meta: { title: '边缘节点' },
      },
      {
        path: ':pathMatch(.*)*',
        name: 'NotFound',
        component: () => import('@/views/error/NotFound.vue'),
        meta: { title: '页面不存在' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta?.public) {
    return true
  }
  try {
    const token = localStorage.getItem('auth-token')
    if (!token) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
    if (to.path === '/login') {
      return '/dashboard'
    }
  } catch {
    return { path: '/login' }
  }
  return true
})

export default router
