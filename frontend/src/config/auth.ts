/** 权限点目录（与后端 app/core/security.py 的 PERMISSIONS 保持一致） */

export const PERMISSION_LABELS: Record<string, string> = {
  'dataset:read': '数据集查看',
  'dataset:write': '数据集管理',
  'annotation:read': '标注查看',
  'annotation:write': '标注管理',
  'model:read': '模型查看',
  'model:write': '模型管理',
  'task:run': '任务管理',
  'node:manage': '边缘节点管理',
  'system:manage': '系统管理',
}

export const ALL_PERMISSIONS = Object.keys(PERMISSION_LABELS)

export const WILDCARD_PERMISSION = '*'
