import { fcState } from './flowchartState.svelte';
import * as utils from './utils';

export class CanvasController {
  canvas: HTMLCanvasElement;
  container: HTMLDivElement;
  render: () => void;
  lastMouseDownTime = 0;
  lastTapTime = 0;

  constructor(canvas: HTMLCanvasElement, container: HTMLDivElement, render: () => void) {
    this.canvas = canvas;
    this.container = container;
    this.render = render;
  }

  getCanvasRect = () => {
    return this.canvas.getBoundingClientRect();
  }

  screenToWorld = (sx: number, sy: number) => {
    const rect = this.getCanvasRect();
    return {
      x: (sx - rect.left - fcState.panX) / fcState.zoom,
      y: (sy - rect.top - fcState.panY) / fcState.zoom
    };
  }

  snapToGrid = (val: number) => {
    if (!fcState.snapGrid) return val;
    return Math.round(val / fcState.gridSize) * fcState.gridSize;
  }

  isHandleAtPos = (wx: number, wy: number) => {
    if (fcState.selectedIds.length === 1) {
      const shape = fcState.shapes.find(s => s.id === fcState.selectedIds[0]);
      if (shape) {
        const handles = utils.getResizeHandles(shape);
        const hitSize = 24 / fcState.zoom; // Larger touch target
        for (const h of handles) {
          if (utils.pointInRect(wx, wy, h.x - hitSize/2, h.y - hitSize/2, hitSize, hitSize)) {
            return h.id;
          }
        }
      }
    }
    return null;
  }

  getShapeAtPos = (wx: number, wy: number) => {
    for (let i = fcState.shapes.length - 1; i >= 0; i--) {
      const s = fcState.shapes[i];
      if (utils.isPointInShape(s, wx, wy)) return s;
    }
    return null;
  }

  getArrowAtPos = (wx: number, wy: number) => {
    for (let i = fcState.arrows.length - 1; i >= 0; i--) {
      const a = fcState.arrows[i];
      if (utils.isPointNearArrow(a, wx, wy, 8 / fcState.zoom, fcState.shapes)) return a;
    }
    return null;
  }

  isArrowHandleAtPos = (wx: number, wy: number) => {
    if (fcState.selectedIds.length === 1) {
      const arrow = fcState.arrows.find(a => a.id === fcState.selectedIds[0]);
      if (arrow && arrow.points) {
        for (let i = 0; i < arrow.points.length; i++) {
          const p = arrow.points[i];
          // Use 15px for much better touch sensitivity on mobile
          if (utils.distance(wx, wy, p.x, p.y) <= 15 / fcState.zoom) {
            return { arrowId: arrow.id, pointIndex: i };
          }
        }
      }
    }
    return null;
  }

  isArrowGhostHandleAtPos = (wx: number, wy: number) => {
    if (fcState.selectedIds.length === 1) {
      const arrow = fcState.arrows.find(a => a.id === fcState.selectedIds[0]);
      if (arrow) {
        const centers = utils.getArrowSegmentCenters(arrow, fcState.shapes);
        for (const c of centers) {
          // Use 15px for much better touch sensitivity on mobile
          if (utils.distance(wx, wy, c.x, c.y) <= 15 / fcState.zoom) {
            return { arrowId: arrow.id, pointIndex: c.index };
          }
        }
      }
    }
    return null;
  }

  handleMouseDown = (e: MouseEvent) => {
    if (e.target !== this.canvas) return;
    
    // Debounce MUST be at the very top to prevent ghost clicks from triggering anything
    if (Date.now() - this.lastMouseDownTime < 300) return;
    this.lastMouseDownTime = Date.now();

    // Double Tap detection on empty space
    const mx = e.clientX, my = e.clientY;
    const world = this.screenToWorld(mx, my);
    const shape = this.getShapeAtPos(world.x, world.y);
    const arrow = this.getArrowAtPos(world.x, world.y);

    if (!shape && !arrow) {
      const now = Date.now();
      if (now - this.lastTapTime < 300) {
        // Double Tap on Empty Space -> Cancel everything
        fcState.selectedIds = [];
        fcState.arrowStartId = null;
        fcState.arrowTemp = null;
        fcState.arrowPointsTemp = [];
        this.render();
        this.lastTapTime = 0;
        return;
      }
      this.lastTapTime = now;
    } else {
      this.lastTapTime = 0;
    }

    if (fcState.tool === 'hand') {
      fcState.isPanning = true;
      fcState.dragStart = { x: mx, y: my };
      fcState.dragOffset = { x: fcState.panX, y: fcState.panY };
      this.container.style.cursor = 'grabbing';
      return;
    }

    if (fcState.tool === 'arrow' || fcState.tool === 'line') {
      if (shape) {
        if (fcState.arrowStartId) {
          if (fcState.arrowStartId !== shape.id || fcState.arrowPointsTemp.length > 0) {
            // Complete Connection
            const newArrow = {
              id: fcState.generateId(),
              type: 'arrow',
              fromId: fcState.arrowStartId,
              toId: shape.id,
              label: '',
              strokeColor: '#64748b',
              strokeWidth: 2,
              routing: fcState.arrowPointsTemp.length > 0 ? 'straight' : 'orthogonal',
              points: [...fcState.arrowPointsTemp]
            };
            fcState.arrows.push(newArrow as any);
            fcState.selectedIds = [newArrow.id];
            fcState.arrowStartId = null;
            fcState.arrowTemp = null;
            fcState.arrowPointsTemp = [];
            fcState.saveHistory();
            this.render();
            
            // Artificial delay to prevent accidental double-starts
            this.lastMouseDownTime = Date.now() + 100; 
            return;
          }
        } else {
          // Start Connection
          fcState.arrowStartId = shape.id;
          fcState.arrowTemp = { x: world.x, y: world.y };
          fcState.arrowPointsTemp = [];
          this.render();
          return;
        }
      } else {
        if (fcState.arrowStartId) {
          // Add intermediate point
          fcState.arrowPointsTemp.push({ x: world.x, y: world.y });
          this.render();
          return;
        }
      }
    }

    if (['rect', 'roundrect', 'diamond', 'circle', 'parallelogram'].includes(fcState.tool)) {
      const sx = this.snapToGrid(world.x);
      const sy = this.snapToGrid(world.y);
      fcState.creatingShape = { type: fcState.tool as any, x: sx, y: sy, w: 0, h: 0 };
      fcState.isDragging = true;
      this.render();
      return;
    }

    if (fcState.tool === 'eraser') {
      if (shape) {
        fcState.arrows = fcState.arrows.filter(a => a.fromId !== shape.id && a.toId !== shape.id);
        fcState.shapes = fcState.shapes.filter(s => s.id !== shape.id);
        fcState.selectedIds = fcState.selectedIds.filter(id => id !== shape.id);
        fcState.saveHistory();
        this.render();
      } else {
        const arrow = this.getArrowAtPos(world.x, world.y);
        if (arrow) {
          fcState.arrows = fcState.arrows.filter(a => a.id !== arrow.id);
          fcState.saveHistory();
          this.render();
        }
      }
      return;
    }

    if (fcState.tool === 'select') {
      const handle = this.isHandleAtPos(world.x, world.y);
      if (handle && fcState.selectedIds.length === 1) {
        const shape = fcState.shapes.find(s => s.id === fcState.selectedIds[0]);
        if (shape) {
          fcState.isResizing = true;
          fcState.resizeHandle = handle;
          fcState.resizeStart = { x: world.x, y: world.y };
          fcState.resizingShape = { ...shape };
          return;
        }
      }
      
      const arrowHandle = this.isArrowHandleAtPos(world.x, world.y);
      if (arrowHandle) {
        fcState.isResizing = true;
        fcState.resizeHandle = `arrow_${arrowHandle.pointIndex}`;
        fcState.resizingShape = { id: arrowHandle.arrowId, type: 'arrowPoint' } as any;
        return;
      }
      
      const ghostHandle = this.isArrowGhostHandleAtPos(world.x, world.y);
      if (ghostHandle) {
        const arrow = fcState.arrows.find(a => a.id === ghostHandle.arrowId);
        if (arrow) {
          if (!arrow.points) arrow.points = [];
          arrow.points.splice(ghostHandle.pointIndex, 0, { x: world.x, y: world.y });
          fcState.isResizing = true;
          fcState.resizeHandle = `arrow_${ghostHandle.pointIndex}`;
          fcState.resizingShape = { id: arrow.id, type: 'arrowPoint' } as any;
          return;
        }
      }
      
      if (shape) {
        if (!e.shiftKey) {
          if (!fcState.selectedIds.includes(shape.id)) {
            fcState.selectedIds = [shape.id];
          }
        } else {
          const idx = fcState.selectedIds.indexOf(shape.id);
          if (idx >= 0) {
            fcState.selectedIds.splice(idx, 1);
          } else {
            fcState.selectedIds.push(shape.id);
          }
        }
        fcState.isDragging = true;
        fcState.dragStart = { x: world.x, y: world.y };
        fcState.dragOffset = fcState.selectedIds.map(id => {
          const s = fcState.shapes.find(s => s.id === id);
          return s ? { id: s.id, ox: s.x, oy: s.y } : null;
        }).filter(Boolean);
      } else if (arrow) {
        fcState.selectedIds = [arrow.id];
        fcState.isDragging = true;
        fcState.dragStart = { x: world.x, y: world.y };
        fcState.dragOffset = [{ id: arrow.id, ox: 0, oy: 0 }];
      } else {
        fcState.selectedIds = [];
        fcState.isPanning = true;
        fcState.dragStart = { x: mx, y: my };
        fcState.dragOffset = { x: fcState.panX, y: fcState.panY };
      }
      this.render();
    }
  }

  handleMouseMove = (e: MouseEvent) => {
    if (e.target !== this.canvas) return;
    const mx = e.clientX, my = e.clientY;
    const world = this.screenToWorld(mx, my);
    
    if (fcState.isPanning) {
      fcState.panX = fcState.dragOffset.x + (mx - fcState.dragStart!.x);
      fcState.panY = fcState.dragOffset.y + (my - fcState.dragStart!.y);
      this.render();
      return;
    }
    
    if (fcState.isResizing && fcState.resizingShape && fcState.resizeHandle) {
      if ((fcState.resizingShape as any).type === 'arrowPoint') {
        const arrow = fcState.arrows.find(a => a.id === fcState.resizingShape!.id);
        const pointIndex = parseInt(fcState.resizeHandle.split('_')[1]);
        if (arrow && arrow.points && arrow.points[pointIndex]) {
          arrow.points[pointIndex].x = this.snapToGrid(world.x);
          arrow.points[pointIndex].y = this.snapToGrid(world.y);
        }
        this.render();
        return;
      }
      
      if (!fcState.resizeStart) return;

      const shape = fcState.shapes.find(s => s.id === fcState.resizingShape!.id);
      if (!shape) return;
      
      const dx = world.x - fcState.resizeStart.x;
      const dy = world.y - fcState.resizeStart.y;
      const orig = fcState.resizingShape;
      const handle = fcState.resizeHandle;
      
      let newX = orig.x, newY = orig.y, newW = orig.w, newH = orig.h;
      
      if (handle.includes('e')) { newW = Math.max(30, orig.w + dx); }
      if (handle.includes('w')) { newW = Math.max(30, orig.w - dx); newX = orig.x + dx; }
      if (handle.includes('s')) { newH = Math.max(30, orig.h + dy); }
      if (handle.includes('n')) { newH = Math.max(30, orig.h - dy); newY = orig.y + dy; }
      
      if (shape.type === 'circle') {
        shape.r = Math.min(newW, newH) / 2;
        shape.x = newX + newW / 2;
        shape.y = newY + newH / 2;
      } else {
        shape.x = newX; shape.y = newY; shape.w = newW; shape.h = newH;
      }
      this.render();
      return;
    }
    
    if (fcState.isDragging && fcState.tool === 'select' && fcState.dragStart && fcState.dragOffset) {
      const dx = world.x - fcState.dragStart.x;
      const dy = world.y - fcState.dragStart.y;
      
      for (const off of fcState.dragOffset) {
        const shape = fcState.shapes.find(s => s.id === off.id);
        if (shape) {
          shape.x = this.snapToGrid(off.ox + dx);
          shape.y = this.snapToGrid(off.oy + dy);
        }
      }
      this.render();
      return;
    }
    
    if (fcState.isDragging && fcState.creatingShape) {
      const dx = world.x - fcState.creatingShape.x!;
      const dy = world.y - fcState.creatingShape.y!;
      fcState.creatingShape.w = this.snapToGrid(dx);
      fcState.creatingShape.h = this.snapToGrid(dy);
      this.render();
      return;
    }
    
    if ((fcState.isDragging || fcState.arrowStartId) && (fcState.tool === 'arrow' || fcState.tool === 'line')) {
      fcState.arrowTemp = { x: world.x, y: world.y };
      this.render();
      return;
    }
  }

  handleMouseUp = (e: MouseEvent) => {
    if (fcState.isPanning) {
      fcState.isPanning = false;
      fcState.dragStart = null;
      this.container.style.cursor = fcState.tool === 'hand' ? 'grab' : 'default';
    }
    
    if (fcState.isResizing) {
      fcState.isResizing = false;
      fcState.resizeHandle = null;
      fcState.resizeStart = null;
      fcState.resizingShape = null;
      fcState.saveHistory();
    }
    
    if (fcState.isDragging && fcState.tool === 'select') {
      fcState.isDragging = false;
      fcState.dragStart = null;
      fcState.saveHistory();
    }
    
    if (fcState.isDragging && fcState.creatingShape) {
      const s = fcState.creatingShape;
      const aw = Math.abs(s.w!);
      const ah = Math.abs(s.h!);
      
      if (aw > 10 && ah > 10) {
        const newShape = {
          id: fcState.generateId(),
          type: s.type,
          x: s.w! < 0 ? s.x! + s.w! : s.x,
          y: s.h! < 0 ? s.y! + s.h! : s.y,
          w: s.type === 'circle' ? 80 : aw,
          h: s.type === 'circle' ? 80 : ah,
          r: s.type === 'circle' ? Math.min(aw, ah) / 2 : 0,
          text: s.type === 'diamond' ? 'Kondisi?' : '',
          fillColor: '#ffffff',
          strokeColor: '#2563eb',
          strokeWidth: 2
        } as any;
        
        if (s.type === 'circle') {
          newShape.x = s.x! + newShape.r;
          newShape.y = s.y! + newShape.r;
        }
        
        fcState.shapes.push(newShape);
        fcState.selectedIds = [newShape.id];
        fcState.tool = 'select';
        fcState.saveHistory();
      }
      fcState.creatingShape = null;
      fcState.isDragging = false;
      this.render();
    }
    
    if (fcState.isDragging && (fcState.tool === 'arrow' || fcState.tool === 'line')) {
      const mx = e.clientX, my = e.clientY;
      const world = this.screenToWorld(mx, my);
      const toShape = this.getShapeAtPos(world.x, world.y);
      
      if (fcState.arrowStartId && toShape && toShape.id !== fcState.arrowStartId) {
        // Drag-to-Connect completed
        const newArrow = {
          id: fcState.generateId(),
          type: 'arrow',
          fromId: fcState.arrowStartId,
          toId: toShape.id,
          label: '',
          strokeColor: '#64748b',
          strokeWidth: 2,
          routing: 'orthogonal',
          points: []
        } as any;
        fcState.arrows.push(newArrow);
        fcState.selectedIds = [newArrow.id];
        fcState.tool = 'select';
        fcState.saveHistory();
        
        // CRITICAL: Clear these so it doesn't start a new line
        fcState.arrowStartId = null;
        fcState.arrowTemp = null;
        fcState.arrowPointsTemp = [];
      }
      
      fcState.isDragging = false;
      this.render();
    }
  }

  handleDoubleClick = (e: MouseEvent) => {
    if (fcState.tool !== 'select') return;
    const mx = e.clientX, my = e.clientY;
    const world = this.screenToWorld(mx, my);
    const arrowHandle = this.isArrowHandleAtPos(world.x, world.y);
    if (arrowHandle) {
      const arrow = fcState.arrows.find(a => a.id === arrowHandle.arrowId);
      if (arrow && arrow.points) {
        arrow.points.splice(arrowHandle.pointIndex, 1);
        fcState.saveHistory();
        this.render();
      }
    }
  }

  handleWheel = (e: WheelEvent) => {
    e.preventDefault();
    const mx = e.clientX, my = e.clientY;
    const rect = this.getCanvasRect();
    const wx = (mx - rect.left - fcState.panX) / fcState.zoom;
    const wy = (my - rect.top - fcState.panY) / fcState.zoom;
    
    if (e.ctrlKey) {
      const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
      fcState.zoom = Math.max(0.1, Math.min(5, fcState.zoom * zoomFactor));
      fcState.panX = mx - rect.left - wx * fcState.zoom;
      fcState.panY = my - rect.top - wy * fcState.zoom;
    } else {
      fcState.panX -= e.deltaX;
      fcState.panY -= e.deltaY;
    }
    this.render();
  }

  handleTouchStart = (e: TouchEvent) => {
    if (e.target !== this.canvas) return;
    e.preventDefault(); // Prevent ghost clicks
    if (e.touches.length === 1) {
      const touch = e.touches[0];
      this.handleMouseDown({
        clientX: touch.clientX,
        clientY: touch.clientY,
        target: e.target,
        shiftKey: false
      } as any);
    }
  }

  handleTouchMove = (e: TouchEvent) => {
    if (e.target !== this.canvas) return;
    e.preventDefault();
    if (e.touches.length === 1) {
      const touch = e.touches[0];
      this.handleMouseMove({
        clientX: touch.clientX,
        clientY: touch.clientY,
        target: e.target
      } as any);
    }
  }

  handleTouchEnd = (e: TouchEvent) => {
    if (e.target !== this.canvas) return;
    e.preventDefault();
    if (e.changedTouches.length > 0) {
      const touch = e.changedTouches[0];
      this.handleMouseUp({
        clientX: touch.clientX,
        clientY: touch.clientY,
        target: e.target
      } as any);
    }
  }
}
