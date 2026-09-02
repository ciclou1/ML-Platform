export interface EvaluationRequest {
  model_id: string
  dataset_id: string
  iou_threshold?: number
  algorithm_package_version_id?: string
  fbeta_beta?: number
  class_weights?: Record<string, number>
}

export interface EvaluationSpeed {
  preprocess: number
  inference: number
  loss: number
  postprocess: number
  total: number
}

export interface EvaluationDatasetSummary {
  images: number
  instances: number
  classes: number
}

export interface EvaluationConfig {
  split?: string
}

export interface PerClassMetric {
  class_id: number
  class_name: string
  image_count: number
  precision: number
  recall: number
  f1: number
  fbeta?: number
  map50: number
  map50_95: number
}

export interface WeightedEvaluationMetrics {
  weighted_precision: number
  weighted_recall: number
  weighted_fbeta: number
  weighted_map50: number
}

export interface EvaluationCustomConfig {
  beta: number
  weights: Record<string, number>
}

export interface EvaluationReport {
  map50: number
  map75?: number
  map50_95: number
  precision: number
  recall: number
  f1?: number
  fbeta?: number
  fitness?: number
  weighted?: WeightedEvaluationMetrics
  custom_config?: EvaluationCustomConfig
  custom_metrics?: Record<string, unknown>
  custom_metrics_error?: string
  speed_ms?: EvaluationSpeed
  dataset_summary?: EvaluationDatasetSummary
  evaluation_config?: EvaluationConfig
  per_class?: PerClassMetric[]
}

function toNumber(value: unknown): number {
  return Number(value ?? 0)
}

function computeF1(precision: number, recall: number): number {
  if (precision + recall === 0) {
    return 0
  }
  return (2 * precision * recall) / (precision + recall)
}

function normalizeSpeed(value: unknown): EvaluationSpeed | undefined {
  if (!value || typeof value !== 'object') {
    return undefined
  }
  const speed = value as Record<string, unknown>
  return {
    preprocess: toNumber(speed.preprocess),
    inference: toNumber(speed.inference),
    loss: toNumber(speed.loss),
    postprocess: toNumber(speed.postprocess),
    total: toNumber(speed.total),
  }
}

function normalizeDatasetSummary(value: unknown): EvaluationDatasetSummary | undefined {
  if (!value || typeof value !== 'object') {
    return undefined
  }
  const summary = value as Record<string, unknown>
  return {
    images: toNumber(summary.images),
    instances: toNumber(summary.instances),
    classes: toNumber(summary.classes),
  }
}

function normalizeConfig(value: unknown): EvaluationConfig | undefined {
  if (!value || typeof value !== 'object') {
    return undefined
  }
  const config = value as Record<string, unknown>
  return {
    split: typeof config.split === 'string' ? config.split : 'val',
  }
}

function normalizePerClass(value: unknown): PerClassMetric[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.map((item) => {
    const row = item as Record<string, unknown>
    return {
      class_id: toNumber(row.class_id),
      class_name: String(row.class_name ?? row.class_id ?? ''),
      image_count: toNumber(row.image_count),
      precision: toNumber(row.precision),
      recall: toNumber(row.recall),
      f1: toNumber(row.f1),
      fbeta: typeof row.fbeta === 'number' ? row.fbeta : undefined,
      map50: toNumber(row.map50),
      map50_95: toNumber(row.map50_95),
    }
  })
}

function normalizeWeighted(value: unknown): WeightedEvaluationMetrics | undefined {
  if (!value || typeof value !== 'object') {
    return undefined
  }
  const metrics = value as Record<string, unknown>
  return {
    weighted_precision: toNumber(metrics.weighted_precision),
    weighted_recall: toNumber(metrics.weighted_recall),
    weighted_fbeta: toNumber(metrics.weighted_fbeta),
    weighted_map50: toNumber(metrics.weighted_map50),
  }
}

function normalizeCustomConfig(value: unknown): EvaluationCustomConfig | undefined {
  if (!value || typeof value !== 'object') {
    return undefined
  }
  const config = value as Record<string, unknown>
  const weights = config.weights
  const normalizedWeights: Record<string, number> = {}
  if (weights && typeof weights === 'object') {
    for (const [key, item] of Object.entries(weights as Record<string, unknown>)) {
      normalizedWeights[key] = toNumber(item)
    }
  }
  return {
    beta: toNumber(config.beta),
    weights: normalizedWeights,
  }
}

function normalizeCustomMetrics(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return undefined
  }
  return value as Record<string, unknown>
}

export function normalizeEvaluationReport(result: Record<string, unknown>): EvaluationReport {
  const precision = toNumber(result.precision)
  const recall = toNumber(result.recall)
  return {
    map50: toNumber(result.map50),
    map75: toNumber(result.map75 ?? result.map50_95),
    map50_95: toNumber(result.map50_95),
    precision,
    recall,
    f1: toNumber(result.f1 ?? computeF1(precision, recall)),
    fbeta: typeof result.fbeta === 'number' ? result.fbeta : undefined,
    fitness: toNumber(result.fitness),
    weighted: normalizeWeighted(result.weighted),
    custom_config: normalizeCustomConfig(result.custom_config),
    custom_metrics: normalizeCustomMetrics(result.custom_metrics),
    custom_metrics_error:
      typeof result.custom_metrics_error === 'string' ? result.custom_metrics_error : undefined,
    speed_ms: normalizeSpeed(result.speed_ms),
    dataset_summary: normalizeDatasetSummary(result.dataset_summary),
    evaluation_config: normalizeConfig(result.evaluation_config),
    per_class: normalizePerClass(result.per_class),
  }
}

export function formatPercent(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) {
    return '--'
  }
  return `${(value * 100).toFixed(1)}%`
}

export function formatMs(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) {
    return '--'
  }
  return value.toFixed(1)
}
