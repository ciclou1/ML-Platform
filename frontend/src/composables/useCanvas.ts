import { ref, type Ref } from 'vue'

/**
 * 标注画布：统一 Shape 模型，支持 bbox / polygon / obb / keypoint / classify。
 *
 * 交互约定：
 * - draw 模式：bbox/obb 按下拖拽创建；polygon 单击加点、双击或 Enter 闭合；
 *   keypoint 先拖出包围框，再逐次单击添加关键点，Enter/双击结束；
 *   classify 无几何，单击画布（或在类别面板选择类别）即为整图打标
 * - select 模式：整体拖动；polygon 顶点可拖拽；obb 可拖旋转手柄；
 *   keypoint 的关键点可拖拽
 * - Escape 取消绘制中的图形，Delete 删除选中图形
 */

export type ShapeType = 'bbox' | 'polygon' | 'obb' | 'keypoint' | 'classify'

export interface ShapeBase {
  id: string
  type: ShapeType
  labelId: string
  labelName: string
  color: string
}

export interface BBoxShape extends ShapeBase {
  type: 'bbox'
  x: number
  y: number
  width: number
  height: number
}

export interface PolygonShape extends ShapeBase {
  type: 'polygon'
  points: [number, number][]
}

export interface ObbShape extends ShapeBase {
  type: 'obb'
  cx: number
  cy: number
  w: number
  h: number
  angle: number
}

export interface KeypointShape extends ShapeBase {
  type: 'keypoint'
  bbox: { x: number; y: number; width: number; height: number }
  points: [number, number, number][]
}

/** 图级分类：无几何数据，每张图片至多一条 */
export interface ClassifyShape extends ShapeBase {
  type: 'classify'
}

export type Shape = BBoxShape | PolygonShape | ObbShape | KeypointShape | ClassifyShape

/** 兼容旧引用：矩形即 bbox 形状 */
export type BBox = BBoxShape

type DrawMode = 'draw' | 'select'

const HANDLE_SIZE = 6
const ROTATE_HANDLE_DISTANCE = 24
const MIN_RECT_SIZE = 5

type Interaction =
  | { kind: 'draw-rect'; startX: number; startY: number }
  | { kind: 'draw-poly' }
  | { kind: 'place-points'; shapeId: string }
  | { kind: 'drag-shape'; shapeId: string; grabX: number; grabY: number; origin: Shape }
  | { kind: 'drag-vertex'; shapeId: string; vertexIndex: number }
  | { kind: 'rotate'; shapeId: string }

export function useCanvas(canvasRef: Ref<HTMLCanvasElement | null>) {
  const shapes = ref<Shape[]>([])
  const selectedId = ref<string | null>(null)
  const mode = ref<DrawMode>('draw')
  const shapeType = ref<ShapeType>('bbox')
  const currentLabelId = ref('')
  const currentLabelName = ref('')
  const currentColor = ref('#FF0000')

  let image: HTMLImageElement | null = null
  let scale = 1
  let offsetX = 0
  let offsetY = 0

  // 绘制中的临时状态
  let tempRect: { x: number; y: number; w: number; h: number } | null = null
  let tempPoly: [number, number][] = []
  let cursorPos: { x: number; y: number } | null = null
  let interaction: Interaction | null = null

  function loadImage(src: string): Promise<void> {
    return new Promise((resolve) => {
      const img = new Image()
      img.onload = () => {
        image = img
        fitToCanvas()
        render()
        resolve()
      }
      img.src = src
    })
  }

  function fitToCanvas() {
    const canvas = canvasRef.value
    if (!canvas || !image) return
    const scaleX = canvas.width / image.width
    const scaleY = canvas.height / image.height
    scale = Math.min(scaleX, scaleY)
    offsetX = (canvas.width - image.width * scale) / 2
    offsetY = (canvas.height - image.height * scale) / 2
  }

  function canvasToImage(cx: number, cy: number): { x: number; y: number } {
    return { x: (cx - offsetX) / scale, y: (cy - offsetY) / scale }
  }

  function toCanvasPoint(x: number, y: number): { x: number; y: number } {
    return { x: x * scale + offsetX, y: y * scale + offsetY }
  }

  function render() {
    const canvas = canvasRef.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    if (image) {
      ctx.drawImage(image, offsetX, offsetY, image.width * scale, image.height * scale)
    }

    for (const shape of shapes.value) {
      drawShape(ctx, shape, shape.id === selectedId.value)
    }

    drawInFlight(ctx)
  }

  function drawInFlight(ctx: CanvasRenderingContext2D) {
    ctx.lineWidth = 2
    if (tempRect) {
      ctx.strokeStyle = currentColor.value
      ctx.setLineDash([4, 4])
      ctx.strokeRect(
        tempRect.x * scale + offsetX,
        tempRect.y * scale + offsetY,
        tempRect.w * scale,
        tempRect.h * scale
      )
      ctx.setLineDash([])
    }

    if (tempPoly.length > 0 || (interaction?.kind === 'draw-poly' && cursorPos)) {
      ctx.strokeStyle = currentColor.value
      ctx.setLineDash([4, 4])
      ctx.beginPath()
      tempPoly.forEach((point, index) => {
        const p = toCanvasPoint(point[0], point[1])
        if (index === 0) ctx.moveTo(p.x, p.y)
        else ctx.lineTo(p.x, p.y)
      })
      if (cursorPos && interaction?.kind === 'draw-poly') {
        ctx.lineTo(cursorPos.x * scale + offsetX, cursorPos.y * scale + offsetY)
      }
      ctx.stroke()
      ctx.setLineDash([])
      for (const point of tempPoly) {
        const p = toCanvasPoint(point[0], point[1])
        ctx.fillStyle = currentColor.value
        ctx.fillRect(p.x - 3, p.y - 3, 6, 6)
      }
    }
  }

  function drawShape(ctx: CanvasRenderingContext2D, shape: Shape, selected: boolean) {
    ctx.strokeStyle = shape.color
    ctx.lineWidth = selected ? 3 : 2
    ctx.fillStyle = shape.color
    ctx.font = '12px sans-serif'

    if (shape.type === 'classify') {
      // 图级分类无几何，在画布左上角画类别徽标
      const text = `分类：${shape.labelName}`
      ctx.font = '13px sans-serif'
      const width = ctx.measureText(text).width + 16
      ctx.globalAlpha = 0.85
      ctx.fillStyle = shape.color
      ctx.fillRect(8, 8, width, 24)
      ctx.globalAlpha = 1
      ctx.fillStyle = '#fff'
      ctx.fillText(text, 16, 25)
      ctx.strokeStyle = shape.color
      ctx.lineWidth = selected ? 3 : 2
      ctx.strokeRect(8, 8, width, 24)
      return
    }

    if (shape.type === 'bbox') {
      const p = toCanvasPoint(shape.x, shape.y)
      const w = shape.width * scale
      const h = shape.height * scale
      ctx.globalAlpha = 0.15
      ctx.fillRect(p.x, p.y, w, h)
      ctx.globalAlpha = 1
      ctx.strokeRect(p.x, p.y, w, h)
      ctx.fillText(shape.labelName, p.x + 2, p.y - 4)
    } else if (shape.type === 'polygon') {
      ctx.globalAlpha = 0.15
      ctx.beginPath()
      shape.points.forEach((point, index) => {
        const p = toCanvasPoint(point[0], point[1])
        if (index === 0) ctx.moveTo(p.x, p.y)
        else ctx.lineTo(p.x, p.y)
      })
      ctx.closePath()
      ctx.fill()
      ctx.globalAlpha = 1
      ctx.stroke()
      const first = toCanvasPoint(shape.points[0][0], shape.points[0][1])
      ctx.fillText(shape.labelName, first.x + 2, first.y - 4)
    } else if (shape.type === 'obb') {
      const corners = obbCorners(shape)
      ctx.globalAlpha = 0.15
      ctx.beginPath()
      corners.forEach((point, index) => {
        const c = toCanvasPoint(point[0], point[1])
        if (index === 0) ctx.moveTo(c.x, c.y)
        else ctx.lineTo(c.x, c.y)
      })
      ctx.closePath()
      ctx.fill()
      ctx.globalAlpha = 1
      ctx.stroke()
      const center = toCanvasPoint(shape.cx, shape.cy)
      ctx.fillText(shape.labelName, center.x + 2, center.y - 4)
    } else {
      const p = toCanvasPoint(shape.bbox.x, shape.bbox.y)
      const w = shape.bbox.width * scale
      const h = shape.bbox.height * scale
      ctx.setLineDash([4, 4])
      ctx.strokeRect(p.x, p.y, w, h)
      ctx.setLineDash([])
      ctx.fillText(shape.labelName, p.x + 2, p.y - 4)
      for (const point of shape.points) {
        const c = toCanvasPoint(point[0], point[1])
        ctx.beginPath()
        ctx.arc(c.x, c.y, 4, 0, Math.PI * 2)
        ctx.fill()
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 1
        ctx.stroke()
        ctx.strokeStyle = shape.color
        ctx.lineWidth = selected ? 3 : 2
      }
    }

    if (selected) {
      drawSelectionHandles(ctx, shape)
    }
  }

  function drawSelectionHandles(ctx: CanvasRenderingContext2D, shape: Shape) {
    ctx.fillStyle = '#fff'
    ctx.strokeStyle = shape.color
    ctx.lineWidth = 1

    const handles = getHandles(shape)
    for (const handle of handles) {
      const p = toCanvasPoint(handle.imageX, handle.imageY)
      ctx.fillRect(p.x - HANDLE_SIZE / 2, p.y - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE)
      ctx.strokeRect(p.x - HANDLE_SIZE / 2, p.y - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE)
    }

    if (shape.type === 'obb') {
      // 旋转手柄：局部坐标上方 h/2 + 距离 处
      const handleImage = rotateHandlePos(shape)
      const p = toCanvasPoint(handleImage[0], handleImage[1])
      ctx.beginPath()
      ctx.arc(p.x, p.y, HANDLE_SIZE / 2 + 1, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
    }
  }

  type Handle = { imageX: number; imageY: number }

  function getHandles(shape: Shape): Handle[] {
    if (shape.type === 'classify') {
      return []
    }
    if (shape.type === 'bbox') {
      return [
        { imageX: shape.x, imageY: shape.y },
        { imageX: shape.x + shape.width, imageY: shape.y },
        { imageX: shape.x, imageY: shape.y + shape.height },
        { imageX: shape.x + shape.width, imageY: shape.y + shape.height },
      ]
    }
    if (shape.type === 'polygon') {
      return shape.points.map((point) => ({ imageX: point[0], imageY: point[1] }))
    }
    if (shape.type === 'obb') {
      return obbCorners(shape).map((point) => ({ imageX: point[0], imageY: point[1] }))
    }
    return shape.bbox
      ? [
          { imageX: shape.bbox.x, imageY: shape.bbox.y },
          {
            imageX: shape.bbox.x + shape.bbox.width,
            imageY: shape.bbox.y + shape.bbox.height,
          },
        ]
      : []
  }

  function obbCorners(shape: ObbShape): [number, number][] {
    const cos = Math.cos(shape.angle)
    const sin = Math.sin(shape.angle)
    const offsets: [number, number][] = [
      [shape.w / 2, shape.h / 2],
      [-shape.w / 2, shape.h / 2],
      [-shape.w / 2, -shape.h / 2],
      [shape.w / 2, -shape.h / 2],
    ]
    return offsets.map(([dx, dy]) => [
      shape.cx + dx * cos - dy * sin,
      shape.cy + dx * sin + dy * cos,
    ])
  }

  function rotateHandlePos(shape: ObbShape): [number, number] {
    const distance = shape.h / 2 + ROTATE_HANDLE_DISTANCE / scale
    return [
      shape.cx - Math.sin(shape.angle) * distance,
      shape.cy - Math.cos(shape.angle) * distance,
    ]
  }

  function findShapeAt(cx: number, cy: number): Shape | null {
    const { x: ix, y: iy } = canvasToImage(cx, cy)
    for (let i = shapes.value.length - 1; i >= 0; i--) {
      if (hitTest(shapes.value[i], ix, iy)) {
        return shapes.value[i]
      }
    }
    return null
  }

  function hitTest(shape: Shape, ix: number, iy: number): boolean {
    if (shape.type === 'classify') {
      return false
    }
    if (shape.type === 'bbox') {
      return (
        ix >= shape.x &&
        ix <= shape.x + shape.width &&
        iy >= shape.y &&
        iy <= shape.y + shape.height
      )
    }
    if (shape.type === 'polygon') {
      return pointInPolygon(ix, iy, shape.points)
    }
    if (shape.type === 'obb') {
      const dx = ix - shape.cx
      const dy = iy - shape.cy
      const localX = dx * Math.cos(shape.angle) + dy * Math.sin(shape.angle)
      const localY = -dx * Math.sin(shape.angle) + dy * Math.cos(shape.angle)
      return Math.abs(localX) <= shape.w / 2 && Math.abs(localY) <= shape.h / 2
    }
    const b = shape.bbox
    return ix >= b.x && ix <= b.x + b.width && iy >= b.y && iy <= b.y + b.height
  }

  function pointInPolygon(ix: number, iy: number, points: [number, number][]): boolean {
    let inside = false
    for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
      const [xi, yi] = points[i]
      const [xj, yj] = points[j]
      const intersects =
        yi > iy !== yj > iy && ix < ((xj - xi) * (iy - yi)) / (yj - yi) + xi
      if (intersects) inside = !inside
    }
    return inside
  }

  function findVertexAt(shape: Shape, ix: number, iy: number): number {
    const tolerance = 8 / scale
    if (shape.type === 'polygon') {
      return shape.points.findIndex(
        (point) =>
          Math.abs(point[0] - ix) <= tolerance && Math.abs(point[1] - iy) <= tolerance
      )
    }
    if (shape.type === 'keypoint') {
      return shape.points.findIndex(
        (point) =>
          Math.abs(point[0] - ix) <= tolerance && Math.abs(point[1] - iy) <= tolerance
      )
    }
    return -1
  }

  function newShapeId(): string {
    return crypto.randomUUID()
  }

  function onMouseDown(e: MouseEvent) {
    const rect = canvasRef.value?.getBoundingClientRect()
    if (!rect) return
    const cx = e.clientX - rect.left
    const cy = e.clientY - rect.top
    const imgPos = canvasToImage(cx, cy)

    if (mode.value === 'select') {
      handleSelectMouseDown(imgPos)
      render()
      return
    }

    if (shapeType.value === 'polygon') {
      tempPoly.push([imgPos.x, imgPos.y])
      interaction = { kind: 'draw-poly' }
      render()
      return
    }

    if (shapeType.value === 'classify') {
      applyClassify()
      render()
      return
    }

    if (drawingEnded) {
      // keypoint 包围框已完成、进入点放置阶段
      return
    }

    drawingEnded = false
    interaction = { kind: 'draw-rect', startX: imgPos.x, startY: imgPos.y }
    tempRect = { x: imgPos.x, y: imgPos.y, w: 0, h: 0 }
  }

  // keypoint 两阶段创建：包围框完成后的点放置
  let drawingEnded = false

  function handleSelectMouseDown(imgPos: { x: number; y: number }) {
    const shape = findShapeAt(imgPos.x, imgPos.y)
    if (!shape) {
      selectedId.value = null
      interaction = null
      return
    }

    selectedId.value = shape.id

    // 顶点/关键点拖拽优先
    const vertexIndex = findVertexAt(shape, imgPos.x, imgPos.y)
    if (vertexIndex >= 0 && (shape.type === 'polygon' || shape.type === 'keypoint')) {
      interaction = { kind: 'drag-vertex', shapeId: shape.id, vertexIndex }
      return
    }

    // obb 旋转手柄
    if (shape.type === 'obb') {
      const handle = rotateHandlePos(shape)
      const tolerance = 10 / scale
      if (
        Math.abs(handle[0] - imgPos.x) <= tolerance &&
        Math.abs(handle[1] - imgPos.y) <= tolerance
      ) {
        interaction = { kind: 'rotate', shapeId: shape.id }
        return
      }
    }

    interaction = {
      kind: 'drag-shape',
      shapeId: shape.id,
      grabX: imgPos.x,
      grabY: imgPos.y,
      origin: JSON.parse(JSON.stringify(shape)) as Shape,
    }
  }

  function onMouseMove(e: MouseEvent) {
    const rect = canvasRef.value?.getBoundingClientRect()
    if (!rect) return
    const cx = e.clientX - rect.left
    const cy = e.clientY - rect.top
    const imgPos = canvasToImage(cx, cy)
    cursorPos = imgPos

    if (!interaction) {
      return
    }

    if (interaction.kind === 'draw-rect' && tempRect) {
      tempRect.w = imgPos.x - interaction.startX
      tempRect.h = imgPos.y - interaction.startY
      render()
      return
    }

    if (interaction.kind === 'draw-poly') {
      render()
      return
    }

    if (interaction.kind === 'drag-shape') {
      const act = interaction
      const shape = shapes.value.find((item) => item.id === act.shapeId)
      if (shape) {
        moveShape(shape, act.origin, imgPos.x - act.grabX, imgPos.y - act.grabY)
        render()
      }
      return
    }

    if (interaction.kind === 'drag-vertex') {
      const act = interaction
      const shape = shapes.value.find((item) => item.id === act.shapeId)
      if (shape && shape.type === 'polygon') {
        shape.points[act.vertexIndex] = [imgPos.x, imgPos.y]
        render()
      } else if (shape && shape.type === 'keypoint') {
        shape.points[act.vertexIndex] = [imgPos.x, imgPos.y, 2]
        render()
      }
      return
    }

    if (interaction.kind === 'rotate') {
      const act = interaction
      const shape = shapes.value.find(
        (item): item is ObbShape => item.id === act.shapeId && item.type === 'obb'
      )
      if (shape) {
        shape.angle = Math.atan2(imgPos.x - shape.cx, -(imgPos.y - shape.cy))
        render()
      }
    }
  }

  function moveShape(shape: Shape, origin: Shape, dx: number, dy: number) {
    if (shape.type === 'bbox' && origin.type === 'bbox') {
      shape.x = origin.x + dx
      shape.y = origin.y + dy
    } else if (shape.type === 'polygon' && origin.type === 'polygon') {
      shape.points = origin.points.map(
        (point) => [point[0] + dx, point[1] + dy] as [number, number]
      )
    } else if (shape.type === 'obb' && origin.type === 'obb') {
      shape.cx = origin.cx + dx
      shape.cy = origin.cy + dy
    } else if (shape.type === 'keypoint' && origin.type === 'keypoint') {
      shape.bbox = {
        x: origin.bbox.x + dx,
        y: origin.bbox.y + dy,
        width: origin.bbox.width,
        height: origin.bbox.height,
      }
      shape.points = origin.points.map(
        (point) => [point[0] + dx, point[1] + dy, point[2]] as [number, number, number]
      )
    }
  }

  function onMouseUp(e: MouseEvent) {
    const rect = canvasRef.value?.getBoundingClientRect()
    const imgPos = rect ? canvasToImage(e.clientX - rect.left, e.clientY - rect.top) : null

    if (interaction?.kind === 'draw-rect' && tempRect) {
      finishDrawRect(interaction.startX, interaction.startY)
      return
    }

    if (interaction?.kind === 'place-points' && imgPos) {
      addKeypoint(imgPos)
      return
    }

    if (interaction?.kind === 'draw-poly') {
      return
    }

    interaction = null
    render()
  }

  function finishDrawRect(startX: number, startY: number) {
    const w = Math.abs(tempRect!.w)
    const h = Math.abs(tempRect!.h)
    const x = tempRect!.w < 0 ? startX + tempRect!.w : startX
    const y = tempRect!.h < 0 ? startY + tempRect!.h : startY
    tempRect = null

    if (w > MIN_RECT_SIZE && h > MIN_RECT_SIZE) {
      if (shapeType.value === 'keypoint') {
        const shape: KeypointShape = {
          id: newShapeId(),
          type: 'keypoint',
          bbox: { x, y, width: w, height: h },
          points: [],
          labelId: currentLabelId.value,
          labelName: currentLabelName.value,
          color: currentColor.value,
        }
        shapes.value.push(shape)
        selectedId.value = shape.id
        interaction = { kind: 'place-points', shapeId: shape.id }
        drawingEnded = true
        render()
        return
      }

      const shape: Shape =
        shapeType.value === 'obb'
          ? {
              id: newShapeId(),
              type: 'obb',
              cx: x + w / 2,
              cy: y + h / 2,
              w,
              h,
              angle: 0,
              labelId: currentLabelId.value,
              labelName: currentLabelName.value,
              color: currentColor.value,
            }
          : {
              id: newShapeId(),
              type: 'bbox',
              x,
              y,
              width: w,
              height: h,
              labelId: currentLabelId.value,
              labelName: currentLabelName.value,
              color: currentColor.value,
            }
      shapes.value.push(shape)
      selectedId.value = shape.id
    }

    interaction = null
    render()
  }

  function addKeypoint(imgPos: { x: number; y: number }) {
    if (interaction?.kind !== 'place-points') {
      return
    }
    const act = interaction
    const shape = shapes.value.find(
      (item): item is KeypointShape => item.id === act.shapeId && item.type === 'keypoint'
    )
    if (!shape) {
      interaction = null
      return
    }
    shape.points.push([imgPos.x, imgPos.y, 2])
    render()
  }

  function onDoubleClick() {
    if (interaction?.kind === 'draw-poly') {
      finishPolygon()
      return
    }
    if (interaction?.kind === 'place-points') {
      interaction = null
      drawingEnded = false
      render()
    }
  }

  function finishPolygon() {
    if (tempPoly.length >= 3) {
      const shape: PolygonShape = {
        id: newShapeId(),
        type: 'polygon',
        points: tempPoly.map((point) => [point[0], point[1]] as [number, number]),
        labelId: currentLabelId.value,
        labelName: currentLabelName.value,
        color: currentColor.value,
      }
      shapes.value.push(shape)
      selectedId.value = shape.id
    }
    tempPoly = []
    interaction = null
    render()
  }

  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      tempPoly = []
      tempRect = null
      drawingEnded = false
      interaction = null
      render()
    } else if (e.key === 'Enter') {
      if (interaction?.kind === 'draw-poly') {
        finishPolygon()
      } else if (interaction?.kind === 'place-points') {
        interaction = null
        drawingEnded = false
        render()
      }
    }
  }

  function deleteSelected() {
    if (!selectedId.value) return
    shapes.value = shapes.value.filter((s) => s.id !== selectedId.value)
    selectedId.value = null
    render()
  }

  function updateSelectedLabel(labelId: string, labelName: string, color: string) {
    if (!selectedId.value) return
    const shape = shapes.value.find((s) => s.id === selectedId.value)
    if (shape) {
      shape.labelId = labelId
      shape.labelName = labelName
      shape.color = color
      render()
    }
  }

  /** 用当前类别为整图打标：替换已有 classify 标注（每图至多一条） */
  function applyClassify() {
    setClassifyLabel(currentLabelId.value, currentLabelName.value, currentColor.value)
  }

  function setClassifyLabel(labelId: string, labelName: string, color: string) {
    if (!labelId) return
    const shape: ClassifyShape = {
      id: newShapeId(),
      type: 'classify',
      labelId,
      labelName,
      color,
    }
    shapes.value = [...shapes.value.filter((s) => s.type !== 'classify'), shape]
    selectedId.value = shape.id
    render()
  }

  function setShapes(newShapes: Shape[]) {
    shapes.value = newShapes
    render()
  }

  function setLabel(labelId: string, labelName: string, color: string) {
    currentLabelId.value = labelId
    currentLabelName.value = labelName
    currentColor.value = color
  }

  return {
    shapes,
    selectedId,
    mode,
    shapeType,
    loadImage,
    render,
    onMouseDown,
    onMouseMove,
    onMouseUp,
    onDoubleClick,
    onKeyDown,
    deleteSelected,
    updateSelectedLabel,
    applyClassify,
    setClassifyLabel,
    setShapes,
    setLabel,
  }
}
