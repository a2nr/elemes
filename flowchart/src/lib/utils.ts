import type { Shape, Arrow } from './flowchartState.svelte';

export function distance(ax: number, ay: number, bx: number, by: number) {
  return Math.sqrt((bx - ax) ** 2 + (by - ay) ** 2);
}

export function pointInRect(px: number, py: number, rx: number, ry: number, rw: number, rh: number) {
  return px >= rx && px <= rx + rw && py >= ry && py <= ry + rh;
}

export function pointInCircle(px: number, py: number, cx: number, cy: number, r: number) {
  return distance(px, py, cx, cy) <= r;
}

export function pointInDiamond(px: number, py: number, dx: number, dy: number, dw: number, dh: number) {
  const hw = dw / 2, hh = dh / 2;
  const cx = dx + hw, cy = dy + hh;
  const nx = Math.abs(px - cx) / hw;
  const ny = Math.abs(py - cy) / hh;
  return nx + ny <= 1;
}

export function pointInParallelogram(px: number, py: number, x: number, y: number, w: number, h: number) {
  const skew = w * 0.25;
  const pts = [
    [x + skew, y],
    [x + w, y],
    [x + w - skew, y + h],
    [x, y + h]
  ];
  return pointInPolygon(px, py, pts);
}

export function pointInPolygon(px: number, py: number, pts: number[][]) {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const xi = pts[i][0], yi = pts[i][1];
    const xj = pts[j][0], yj = pts[j][1];
    if ((yi > py) !== (yj > py) && px < (xj - xi) * (py - yi) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

export function getShapeBounds(shape: Shape) {
  if (shape.type === 'circle') {
    return { x: shape.x - shape.r, y: shape.y - shape.r, w: shape.r * 2, h: shape.r * 2 };
  }
  return { x: shape.x, y: shape.y, w: shape.w, h: shape.h };
}

export function getShapeCenter(shape: Shape) {
  const b = getShapeBounds(shape);
  return { x: b.x + b.w / 2, y: b.y + b.h / 2 };
}

export function getShapeBorderPoint(shape: Shape, tx: number, ty: number) {
  const c = getShapeCenter(shape);
  const dx = tx - c.x;
  const dy = ty - c.y;
  
  if (shape.type === 'circle') {
    const angle = Math.atan2(dy, dx);
    return { x: c.x + Math.cos(angle) * shape.r, y: c.y + Math.sin(angle) * shape.r };
  }
  
  const b = getShapeBounds(shape);
  const hw = b.w / 2, hh = b.h / 2;
  
  if (dx === 0 && dy === 0) return { x: c.x, y: c.y - hh };
  
  const absDx = Math.abs(dx);
  const absDy = Math.abs(dy);
  const slope = absDy / absDx;
  const shapeSlope = hh / hw;
  
  let ex, ey;
  if (slope <= shapeSlope) {
    ex = hw * (dx > 0 ? 1 : -1);
    ey = ex * slope * (dy > 0 ? 1 : -1);
  } else {
    ey = hh * (dy > 0 ? 1 : -1);
    ex = ey / slope * (dx > 0 ? 1 : -1);
  }
  
  return { x: c.x + ex, y: c.y + ey };
}

export function getResizeHandles(shape: Shape) {
  const b = getShapeBounds(shape);
  return [
    { id: 'nw', x: b.x, y: b.y },
    { id: 'ne', x: b.x + b.w, y: b.y },
    { id: 'sw', x: b.x, y: b.y + b.h },
    { id: 'se', x: b.x + b.w, y: b.y + b.h },
    { id: 'n', x: b.x + b.w / 2, y: b.y },
    { id: 's', x: b.x + b.w / 2, y: b.y + b.h },
    { id: 'w', x: b.x, y: b.y + b.h / 2 },
    { id: 'e', x: b.x + b.w, y: b.y + b.h / 2 },
  ];
}

export function isPointInShape(shape: Shape, px: number, py: number) {
  const sw = shape.strokeWidth / 2;
  if (shape.type === 'circle') {
    return pointInCircle(px, py, shape.x, shape.y, shape.r + sw);
  } else if (shape.type === 'diamond') {
    return pointInDiamond(px, py, shape.x, shape.y, shape.w, shape.h);
  } else if (shape.type === 'parallelogram') {
    return pointInParallelogram(px, py, shape.x, shape.y, shape.w, shape.h);
  } else {
    return pointInRect(px, py, shape.x - sw, shape.y - sw, shape.w + sw * 2, shape.h + sw * 2);
  }
}

export function distToSegment(px: number, py: number, x1: number, y1: number, x2: number, y2: number) {
  const dx = x2 - x1, dy = y2 - y1;
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) return distance(px, py, x1, y1);
  let t = ((px - x1) * dx + (py - y1) * dy) / lenSq;
  t = Math.max(0, Math.min(1, t));
  return distance(px, py, x1 + t * dx, y1 + t * dy);
}

export function getArrowPoints(arrow: Arrow, shapes: Shape[]) {
  const fromShape = shapes.find(s => s.id === arrow.fromId);
  const toShape = shapes.find(s => s.id === arrow.toId);
  
  if (!fromShape || !toShape) return [];
  
  const fromC = getShapeCenter(fromShape);
  const toC = getShapeCenter(toShape);
  
  const hasPoints = arrow.points && arrow.points.length > 0;
  
  const firstTarget = hasPoints ? arrow.points[0] : toC;
  const lastTarget = hasPoints ? arrow.points[arrow.points.length - 1] : fromC;
  
  const fromBorder = getShapeBorderPoint(fromShape, firstTarget.x, firstTarget.y);
  const toBorder = getShapeBorderPoint(toShape, lastTarget.x, lastTarget.y);
  
  const pts = [{ x: fromBorder.x, y: fromBorder.y }];
  
  if (arrow.routing === 'orthogonal') {
    if (hasPoints) {
      // If manual points exist, make each segment orthogonal
      let curr = fromBorder;
      for (const p of arrow.points) {
        // Add a midpoint to make it orthogonal
        if (Math.abs(p.x - curr.x) > Math.abs(p.y - curr.y)) {
          pts.push({ x: p.x, y: curr.y });
        } else {
          pts.push({ x: curr.x, y: p.y });
        }
        pts.push(p);
        curr = p;
      }
      // Final segment to toBorder
      if (Math.abs(toBorder.x - curr.x) > Math.abs(toBorder.y - curr.y)) {
        pts.push({ x: toBorder.x, y: curr.y });
      } else {
        pts.push({ x: curr.x, y: toBorder.y });
      }
    } else {
      // Auto orthogonal (3-segments usually looks best)
      const midX = (fromBorder.x + toBorder.x) / 2;
      const midY = (fromBorder.y + toBorder.y) / 2;
      
      // Decide based on whether shapes are more horizontal or vertical to each other
      if (Math.abs(fromBorder.x - toBorder.x) > Math.abs(fromBorder.y - toBorder.y)) {
        pts.push({ x: midX, y: fromBorder.y });
        pts.push({ x: midX, y: toBorder.y });
      } else {
        pts.push({ x: fromBorder.x, y: midY });
        pts.push({ x: toBorder.x, y: midY });
      }
    }
  } else {
    if (hasPoints) {
      pts.push(...arrow.points);
    }
  }
  
  pts.push({ x: toBorder.x, y: toBorder.y });
  return pts;
}

export function getArrowSegmentCenters(arrow: Arrow, shapes: Shape[]) {
  const pts = getArrowPoints(arrow, shapes);
  const centers = [];
  for (let i = 0; i < pts.length - 1; i++) {
    centers.push({
      x: (pts[i].x + pts[i+1].x) / 2,
      y: (pts[i].y + pts[i+1].y) / 2,
      index: i
    });
  }
  return centers;
}

export function getArrowLabelPosition(arrow: Arrow, shapes: Shape[]) {
  const pts = getArrowPoints(arrow, shapes);
  if (pts.length < 2) return null;
  
  if (pts.length === 2) {
    return {
      x: (pts[0].x + pts[1].x) / 2,
      y: (pts[0].y + pts[1].y) / 2,
      angle: Math.atan2(pts[1].y - pts[0].y, pts[1].x - pts[0].x)
    };
  }
  
  let totalLength = 0;
  const segments = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const len = distance(pts[i].x, pts[i].y, pts[i + 1].x, pts[i + 1].y);
    segments.push(len);
    totalLength += len;
  }
  
  const halfLength = totalLength / 2;
  let accumulatedLength = 0;
  
  for (let i = 0; i < segments.length; i++) {
    if (accumulatedLength + segments[i] >= halfLength) {
      const remaining = halfLength - accumulatedLength;
      const t = segments[i] > 0 ? remaining / segments[i] : 0;
      const x = pts[i].x + (pts[i + 1].x - pts[i].x) * t;
      const y = pts[i].y + (pts[i + 1].y - pts[i].y) * t;
      const angle = Math.atan2(pts[i + 1].y - pts[i].y, pts[i + 1].x - pts[i].x);
      return { x, y, angle };
    }
    accumulatedLength += segments[i];
  }
  
  const last = pts[pts.length - 1];
  const prev = pts[pts.length - 2];
  return {
    x: (last.x + prev.x) / 2,
    y: (last.y + prev.y) / 2,
    angle: Math.atan2(last.y - prev.y, last.x - prev.x)
  };
}

export function isPointNearArrow(arrow: Arrow, px: number, py: number, tolerance: number, shapes: Shape[]) {
  const pts = getArrowPoints(arrow, shapes);
  for (let i = 0; i < pts.length - 1; i++) {
    const d = distToSegment(px, py, pts[i].x, pts[i].y, pts[i + 1].x, pts[i + 1].y);
    if (d <= tolerance) return true;
  }
  return false;
}
