<script lang="ts">
  import { onMount } from 'svelte';
  import { fcState } from './flowchartState.svelte';
  import * as utils from './utils';

  let canvas: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D;
  let container: HTMLDivElement;
  let lastMouseDownTime = 0;
  let lastTapTime = 0;

  function resizeCanvas() {
    if (!canvas || !container) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = container.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    render();
  }

  function getCanvasRect() {
    return canvas.getBoundingClientRect();
  }

  function screenToWorld(sx: number, sy: number) {
    const rect = getCanvasRect();
    return {
      x: (sx - rect.left - fcState.panX) / fcState.zoom,
      y: (sy - rect.top - fcState.panY) / fcState.zoom
    };
  }

  function snapToGrid(val: number) {
    if (!fcState.snapGrid) return val;
    return Math.round(val / fcState.gridSize) * fcState.gridSize;
  }

  function isHandleAtPos(wx: number, wy: number) {
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

  function getShapeAtPos(wx: number, wy: number) {
    for (let i = fcState.shapes.length - 1; i >= 0; i--) {
      const s = fcState.shapes[i];
      if (utils.isPointInShape(s, wx, wy)) return s;
    }
    return null;
  }

  function getArrowAtPos(wx: number, wy: number) {
    for (let i = fcState.arrows.length - 1; i >= 0; i--) {
      const a = fcState.arrows[i];
      if (utils.isPointNearArrow(a, wx, wy, 8 / fcState.zoom, fcState.shapes)) return a;
    }
    return null;
  }

  function isArrowHandleAtPos(wx: number, wy: number) {
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

  function isArrowGhostHandleAtPos(wx: number, wy: number) {
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

  function handleMouseDown(e: MouseEvent) {
    if (e.target !== canvas) return;
    
    // Debounce MUST be at the very top to prevent ghost clicks from triggering anything
    if (Date.now() - lastMouseDownTime < 300) return;
    lastMouseDownTime = Date.now();

    // Double Tap detection on empty space
    const mx = e.clientX, my = e.clientY;
    const world = screenToWorld(mx, my);
    const shape = getShapeAtPos(world.x, world.y);
    const arrow = getArrowAtPos(world.x, world.y);

    if (!shape && !arrow) {
      const now = Date.now();
      if (now - lastTapTime < 300) {
        // Double Tap on Empty Space -> Cancel everything
        fcState.selectedIds = [];
        fcState.arrowStartId = null;
        fcState.arrowTemp = null;
        fcState.arrowPointsTemp = [];
        render();
        lastTapTime = 0;
        return;
      }
      lastTapTime = now;
    } else {
      lastTapTime = 0;
    }

    if (fcState.tool === 'hand') {
      fcState.isPanning = true;
      fcState.dragStart = { x: mx, y: my };
      fcState.dragOffset = { x: fcState.panX, y: fcState.panY };
      container.style.cursor = 'grabbing';
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
            fcState.arrows.push(newArrow);
            fcState.selectedIds = [newArrow.id];
            fcState.arrowStartId = null;
            fcState.arrowTemp = null;
            fcState.arrowPointsTemp = [];
            fcState.saveHistory();
            render();
            
            // Artificial delay to prevent accidental double-starts
            lastMouseDownTime = Date.now() + 100; 
            return;
          }
        } else {
          // Start Connection
          fcState.arrowStartId = shape.id;
          fcState.arrowTemp = { x: world.x, y: world.y };
          fcState.arrowPointsTemp = [];
          render();
          return;
        }
      } else {
        if (fcState.arrowStartId) {
          // Add intermediate point
          fcState.arrowPointsTemp.push({ x: world.x, y: world.y });
          render();
          return;
        }
      }
    }

    if (['rect', 'roundrect', 'diamond', 'circle', 'parallelogram'].includes(fcState.tool)) {
      const sx = snapToGrid(world.x);
      const sy = snapToGrid(world.y);
      fcState.creatingShape = { type: fcState.tool as any, x: sx, y: sy, w: 0, h: 0 };
      fcState.isDragging = true;
      render();
      return;
    }

    if (fcState.tool === 'eraser') {
      if (shape) {
        fcState.arrows = fcState.arrows.filter(a => a.fromId !== shape.id && a.toId !== shape.id);
        fcState.shapes = fcState.shapes.filter(s => s.id !== shape.id);
        fcState.selectedIds = fcState.selectedIds.filter(id => id !== shape.id);
        fcState.saveHistory();
        render();
      } else {
        const arrow = getArrowAtPos(world.x, world.y);
        if (arrow) {
          fcState.arrows = fcState.arrows.filter(a => a.id !== arrow.id);
          fcState.saveHistory();
          render();
        }
      }
      return;
    }

    if (fcState.tool === 'select') {
      const handle = isHandleAtPos(world.x, world.y);
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
      
      const arrowHandle = isArrowHandleAtPos(world.x, world.y);
      if (arrowHandle) {
        fcState.isResizing = true;
        fcState.resizeHandle = `arrow_${arrowHandle.pointIndex}`;
        fcState.resizingShape = { id: arrowHandle.arrowId, type: 'arrowPoint' } as any;
        return;
      }
      
      const ghostHandle = isArrowGhostHandleAtPos(world.x, world.y);
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
      render();
    }
  }

  function handleMouseMove(e: MouseEvent) {
    if (e.target !== canvas) return;
    const mx = e.clientX, my = e.clientY;
    const world = screenToWorld(mx, my);
    
    if (fcState.isPanning) {
      fcState.panX = fcState.dragOffset.x + (mx - fcState.dragStart!.x);
      fcState.panY = fcState.dragOffset.y + (my - fcState.dragStart!.y);
      render();
      return;
    }
    
    if (fcState.isResizing && fcState.resizingShape && fcState.resizeHandle) {
      if ((fcState.resizingShape as any).type === 'arrowPoint') {
        const arrow = fcState.arrows.find(a => a.id === fcState.resizingShape!.id);
        const pointIndex = parseInt(fcState.resizeHandle.split('_')[1]);
        if (arrow && arrow.points && arrow.points[pointIndex]) {
          arrow.points[pointIndex].x = snapToGrid(world.x);
          arrow.points[pointIndex].y = snapToGrid(world.y);
        }
        render();
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
      render();
      return;
    }
    
    if (fcState.isDragging && fcState.tool === 'select' && fcState.dragStart && fcState.dragOffset) {
      const dx = world.x - fcState.dragStart.x;
      const dy = world.y - fcState.dragStart.y;
      
      for (const off of fcState.dragOffset) {
        const shape = fcState.shapes.find(s => s.id === off.id);
        if (shape) {
          shape.x = snapToGrid(off.ox + dx);
          shape.y = snapToGrid(off.oy + dy);
        }
      }
      render();
      return;
    }
    
    if (fcState.isDragging && fcState.creatingShape) {
      const dx = world.x - fcState.creatingShape.x!;
      const dy = world.y - fcState.creatingShape.y!;
      fcState.creatingShape.w = snapToGrid(dx);
      fcState.creatingShape.h = snapToGrid(dy);
      render();
      return;
    }
    
    if ((fcState.isDragging || fcState.arrowStartId) && (fcState.tool === 'arrow' || fcState.tool === 'line')) {
      fcState.arrowTemp = { x: world.x, y: world.y };
      render();
      return;
    }
  }

  function handleMouseUp(e: MouseEvent) {
    if (fcState.isPanning) {
      fcState.isPanning = false;
      fcState.dragStart = null;
      container.style.cursor = fcState.tool === 'hand' ? 'grab' : 'default';
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
      render();
    }
    
    if (fcState.isDragging && (fcState.tool === 'arrow' || fcState.tool === 'line')) {
      const mx = e.clientX, my = e.clientY;
      const world = screenToWorld(mx, my);
      const toShape = getShapeAtPos(world.x, world.y);
      
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
      render();
    }
  }

  function handleDoubleClick(e: MouseEvent) {
    if (fcState.tool !== 'select') return;
    const mx = e.clientX, my = e.clientY;
    const world = screenToWorld(mx, my);
    const arrowHandle = isArrowHandleAtPos(world.x, world.y);
    if (arrowHandle) {
      const arrow = fcState.arrows.find(a => a.id === arrowHandle.arrowId);
      if (arrow && arrow.points) {
        arrow.points.splice(arrowHandle.pointIndex, 1);
        fcState.saveHistory();
        render();
      }
    }
  }

  function handleWheel(e: WheelEvent) {
    e.preventDefault();
    const mx = e.clientX, my = e.clientY;
    const rect = getCanvasRect();
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
    render();
  }

  function handleTouchStart(e: TouchEvent) {
    if (e.target !== canvas) return;
    e.preventDefault(); // Prevent ghost clicks
    if (e.touches.length === 1) {
      const touch = e.touches[0];
      handleMouseDown({
        clientX: touch.clientX,
        clientY: touch.clientY,
        target: e.target,
        shiftKey: false
      } as any);
    }
  }

  function handleTouchMove(e: TouchEvent) {
    if (e.target !== canvas) return;
    e.preventDefault();
    if (e.touches.length === 1) {
      const touch = e.touches[0];
      handleMouseMove({
        clientX: touch.clientX,
        clientY: touch.clientY,
        target: e.target
      } as any);
    }
  }

  function handleTouchEnd(e: TouchEvent) {
    if (e.target !== canvas) return;
    e.preventDefault();
    if (e.changedTouches.length > 0) {
      const touch = e.changedTouches[0];
      handleMouseUp({
        clientX: touch.clientX,
        clientY: touch.clientY,
        target: e.target
      } as any);
    }
  }

  // Basic Rendering
  function render() {
    if (!ctx) return;
    const rect = getCanvasRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
    
    // Draw Grid
    if (fcState.showGrid) {
      ctx.beginPath();
      ctx.strokeStyle = '#f1f5f9';
      ctx.lineWidth = 1;
      const size = fcState.gridSize * fcState.zoom;
      const ox = fcState.panX % size;
      const oy = fcState.panY % size;
      
      for (let x = ox; x < rect.width; x += size) {
        ctx.moveTo(x, 0); ctx.lineTo(x, rect.height);
      }
      for (let y = oy; y < rect.height; y += size) {
        ctx.moveTo(0, y); ctx.lineTo(rect.width, y);
      }
      ctx.stroke();
    }

    ctx.save();
    ctx.translate(fcState.panX, fcState.panY);
    ctx.scale(fcState.zoom, fcState.zoom);

    for (const shape of fcState.shapes) {
      drawShape(shape);
    }

    for (const arrow of fcState.arrows) {
      drawArrow(arrow);
    }
    
    // Draw temp arrow
    if (fcState.arrowStartId) {
      const fromShape = fcState.shapes.find(s => s.id === fcState.arrowStartId);
      if (fromShape) {
        const mouseWorld = fcState.arrowTemp || { x: 0, y: 0 };
        const hasPoints = fcState.arrowPointsTemp.length > 0;
        const firstTarget = hasPoints ? fcState.arrowPointsTemp[0] : mouseWorld;
        const fromBorder = utils.getShapeBorderPoint(fromShape, firstTarget.x, firstTarget.y);
        
        ctx.save();
        ctx.strokeStyle = '#2563eb';
        ctx.lineWidth = 2;
        ctx.lineCap = 'round';
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(fromBorder.x, fromBorder.y);
        
        // Draw through all intermediate points
        for (const p of fcState.arrowPointsTemp) {
          ctx.lineTo(p.x, p.y);
        }
        
        // Current mouse/touch position
        if (fcState.arrowTemp) {
          ctx.lineTo(fcState.arrowTemp.x, fcState.arrowTemp.y);
        }
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Arrowhead at the end
        const last = fcState.arrowTemp;
        if (last) {
          const prev = fcState.arrowPointsTemp.length > 0 
            ? fcState.arrowPointsTemp[fcState.arrowPointsTemp.length - 1] 
            : fromBorder;
          const angle = Math.atan2(last.y - prev.y, last.x - prev.x);
          ctx.beginPath();
          ctx.moveTo(last.x, last.y);
          ctx.lineTo(last.x - 10 * Math.cos(angle - Math.PI / 6), last.y - 10 * Math.sin(angle - Math.PI / 6));
          ctx.lineTo(last.x - 10 * Math.cos(angle + Math.PI / 6), last.y - 10 * Math.sin(angle + Math.PI / 6));
          ctx.closePath();
          ctx.fill();
        }
        ctx.restore();
      }
    }
    
    // Draw creating shape
    if (fcState.creatingShape) {
      const s = fcState.creatingShape;
      ctx.strokeStyle = '#2563eb';
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      if (s.type === 'rect') ctx.strokeRect(s.x!, s.y!, s.w!, s.h!);
      else if (s.type === 'circle') {
        const r = Math.sqrt(s.w!**2 + s.h!**2);
        ctx.beginPath(); ctx.arc(s.x!, s.y!, r, 0, Math.PI*2); ctx.stroke();
      }
      ctx.restore();
    }

    ctx.restore();
  }

  function drawShape(shape: any) {
    ctx.save();
    ctx.fillStyle = shape.fillColor || '#ffffff';
    ctx.strokeStyle = shape.strokeColor || '#2563eb';
    ctx.lineWidth = shape.strokeWidth || 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    
    const isSelected = fcState.selectedIds.includes(shape.id);
    const isArrowStart = fcState.arrowStartId === shape.id;

    if (isSelected) {
      ctx.shadowColor = '#3b82f6';
      ctx.shadowBlur = 8 / fcState.zoom;
    } else if (isArrowStart) {
      ctx.strokeStyle = '#2563eb';
      ctx.lineWidth = (shape.strokeWidth || 2) + 2;
      ctx.shadowColor = '#2563eb';
      ctx.shadowBlur = 12 / fcState.zoom;
    }
    
    switch (shape.type) {
      case 'rect':
        ctx.beginPath();
        ctx.rect(shape.x, shape.y, shape.w, shape.h);
        ctx.fill();
        ctx.stroke();
        break;
      case 'roundrect':
        const r = shape.r || 10;
        ctx.beginPath();
        ctx.roundRect(shape.x, shape.y, shape.w, shape.h, r);
        ctx.fill();
        ctx.stroke();
        break;
      case 'circle':
        ctx.beginPath();
        ctx.arc(shape.x, shape.y, shape.r, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        break;
      case 'diamond':
        ctx.beginPath();
        ctx.moveTo(shape.x + shape.w / 2, shape.y);
        ctx.lineTo(shape.x + shape.w, shape.y + shape.h / 2);
        ctx.lineTo(shape.x + shape.w / 2, shape.y + shape.h);
        ctx.lineTo(shape.x, shape.y + shape.h / 2);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        break;
      case 'parallelogram':
        const skew = shape.w * 0.2;
        ctx.beginPath();
        ctx.moveTo(shape.x + skew, shape.y);
        ctx.lineTo(shape.x + shape.w, shape.y);
        ctx.lineTo(shape.x + shape.w - skew, shape.y + shape.h);
        ctx.lineTo(shape.x, shape.y + shape.h);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        break;
    }

    if (shape.text) {
      ctx.fillStyle = shape.textColor || '#1e293b';
      ctx.font = `${shape.fontSize || 14}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      
      const words = shape.text.split(' ');
      const lines = [];
      let currentLine = '';
      const maxWidth = shape.w * 0.8;
      
      for (const word of words) {
        const test = currentLine ? currentLine + ' ' + word : word;
        if (ctx.measureText(test).width < maxWidth) currentLine = test;
        else { lines.push(currentLine); currentLine = word; }
      }
      lines.push(currentLine);
      
      const lineHeight = (shape.fontSize || 14) * 1.2;
      const totalH = lines.length * lineHeight;
      let startY = (shape.type === 'circle') ? shape.y - totalH / 2 + lineHeight/2 : shape.y + shape.h / 2 - totalH / 2 + lineHeight / 2;
      const startX = (shape.type === 'circle') ? shape.x : shape.x + shape.w / 2;

      for (const line of lines) {
        ctx.fillText(line, startX, startY);
        startY += lineHeight;
      }
    }

    if (isSelected) {
      const handles = utils.getResizeHandles(shape);
      ctx.fillStyle = '#ffffff';
      ctx.strokeStyle = '#2563eb';
      ctx.lineWidth = 1 / fcState.zoom;
      const s = 12 / fcState.zoom; // Visual size (larger for touch friendliness)
      for (const h of handles) {
        ctx.fillRect(h.x - s/2, h.y - s/2, s, s);
        ctx.strokeRect(h.x - s/2, h.y - s/2, s, s);
      }
    }
    ctx.restore();
  }

  function drawArrow(arrow: any) {
    const pts = utils.getArrowPoints(arrow, fcState.shapes);
    if (pts.length < 2) return;
    
    ctx.save();
    ctx.strokeStyle = arrow.strokeColor || '#64748b';
    ctx.fillStyle = arrow.strokeColor || '#64748b';
    ctx.lineWidth = arrow.strokeWidth || 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    
    const isSelected = fcState.selectedIds.includes(arrow.id);
    if (isSelected) {
      ctx.strokeStyle = '#2563eb';
      ctx.fillStyle = '#2563eb';
      ctx.lineWidth = 3;
      ctx.shadowColor = '#3b82f6';
      ctx.shadowBlur = 6 / fcState.zoom;
    }
    
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    
    if (arrow.routing === 'curved' && pts.length >= 2) {
      if (pts.length === 2) {
        // Simple curve between two points
        const midX = (pts[0].x + pts[1].x) / 2;
        const midY = (pts[0].y + pts[1].y) / 2;
        const cp1x = (pts[0].x + midX) / 2;
        const cp1y = pts[0].y;
        const cp2x = (midX + pts[1].x) / 2;
        const cp2y = pts[1].y;
        ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, pts[1].x, pts[1].y);
      } else {
        // Multi-point curve
        for (let i = 0; i < pts.length - 1; i++) {
          const p1 = pts[i];
          const p2 = pts[i+1];
          const midX = (p1.x + p2.x) / 2;
          ctx.bezierCurveTo(midX, p1.y, midX, p2.y, p2.x, p2.y);
        }
      }
    } else {
      for (let i = 1; i < pts.length; i++) {
        ctx.lineTo(pts[i].x, pts[i].y);
      }
    }
    ctx.stroke();

    // Arrowhead logic
    let last, secondLast;
    if (arrow.routing === 'curved' && pts.length >= 2) {
      last = pts[pts.length - 1];
      // For curved, the direction at the end is from the last control point
      const p1 = pts[pts.length - 2];
      const midX = (p1.x + last.x) / 2;
      secondLast = { x: midX, y: last.y };
      // Fallback if they are too close
      if (utils.distance(last.x, last.y, secondLast.x, secondLast.y) < 1) {
          secondLast = p1;
      }
    } else {
      last = pts[pts.length - 1];
      secondLast = pts[pts.length - 2];
    }
    
    const size = 12 / fcState.zoom;
    const angle = Math.atan2(last.y - secondLast.y, last.x - secondLast.x);
    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(last.x - size * Math.cos(angle - Math.PI / 6), last.y - size * Math.sin(angle - Math.PI / 6));
    ctx.lineTo(last.x - size * Math.cos(angle + Math.PI / 6), last.y - size * Math.sin(angle + Math.PI / 6));
    ctx.closePath();
    ctx.fill();

    if (isSelected) {
      drawArrowSelection(arrow);
    }
    ctx.restore();
  }

  function drawArrowSelection(arrow: any) {
    ctx.save();
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth = 2 / fcState.zoom;
    const s = 6 / fcState.zoom; // Increased from 4
    
    // Draw points handles
    if (arrow.points) {
      for (const p of arrow.points) {
        ctx.fillRect(p.x - s, p.y - s, s*2, s*2);
        ctx.strokeRect(p.x - s, p.y - s, s*2, s*2);
      }
    }
    
    // Draw ghost handles
    ctx.fillStyle = 'rgba(255, 255, 255, 0.7)'; // More opaque
    ctx.strokeStyle = 'rgba(59, 130, 246, 0.8)';
    const centers = utils.getArrowSegmentCenters(arrow, fcState.shapes);
    for (const c of centers) {
      ctx.beginPath();
      ctx.arc(c.x, c.y, s + 1, 0, Math.PI * 2); // Larger radius
      ctx.fill();
      ctx.stroke();
    }
    
    ctx.restore();
  }

  onMount(() => {
    ctx = canvas.getContext('2d')!;
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    
    canvas.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('wheel', handleWheel, { passive: false });
    canvas.addEventListener('dblclick', handleDoubleClick);

    canvas.addEventListener('touchstart', handleTouchStart, { passive: false });
    canvas.addEventListener('touchmove', handleTouchMove, { passive: false });
    canvas.addEventListener('touchend', handleTouchEnd, { passive: false });

    const int = setInterval(render, 1000/60);
    return () => {
      window.removeEventListener('resize', resizeCanvas);
      canvas.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      canvas.removeEventListener('wheel', handleWheel);
      canvas.removeEventListener('dblclick', handleDoubleClick);
      canvas.removeEventListener('touchstart', handleTouchStart);
      canvas.removeEventListener('touchmove', handleTouchMove);
      canvas.removeEventListener('touchend', handleTouchEnd);
      clearInterval(int);
    };
  });
</script>

<div id="canvas-container" bind:this={container} role="application" aria-label="Flowchart Canvas" class="tool-{fcState.tool}">
  <canvas bind:this={canvas}></canvas>
</div>

<style>
  #canvas-container {
    position: absolute;
    top: var(--topbar-h);
    left: var(--toolbar-w);
    right: 0;
    bottom: 0;
    overflow: hidden;
    cursor: default;
    touch-action: none;
  }

  #canvas-container.tool-hand {
    cursor: grab;
  }

  #canvas-container.tool-rect,
  #canvas-container.tool-circle,
  #canvas-container.tool-diamond,
  #canvas-container.tool-parallelogram,
  #canvas-container.tool-roundrect,
  #canvas-container.tool-arrow,
  #canvas-container.tool-line,
  #canvas-container.tool-select,
  #canvas-container.tool-text,
  #canvas-container.tool-move {
    cursor: default;
  }
  
  #canvas-container.tool-eraser {
    cursor: pointer;
  }

  canvas {
    position: absolute;
    top: 0;
    left: 0;
  }
</style>
