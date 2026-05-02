<script lang="ts">
  import { onMount } from 'svelte';
  import { fcState } from './flowchartState.svelte';
  import * as utils from './utils';
  import { CanvasController } from './canvasEvents';

  let canvas: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D;
  let container: HTMLDivElement;
  let controller: CanvasController;

  function getCanvasRect() {
    return canvas.getBoundingClientRect();
  }

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

    if (isSelected || isArrowStart) {
      // Draw Ports
      const ports: ('top' | 'bottom' | 'left' | 'right')[] = ['top', 'bottom', 'left', 'right'];
      ctx.fillStyle = '#3b82f6';
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5 / fcState.zoom;
      const portSize = 5 / fcState.zoom;

      for (const p of ports) {
        const pt = utils.getShapePort(shape, p);
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, portSize, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
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

    // Render Label
    if (arrow.label) {
      const midIdx = Math.floor(pts.length / 2) - 1;
      const p1 = pts[midIdx];
      const p2 = pts[midIdx + 1];
      const labelX = (p1.x + p2.x) / 2;
      const labelY = (p1.y + p2.y) / 2;

      ctx.save();
      ctx.font = 'bold 12px sans-serif';
      const metrics = ctx.measureText(arrow.label);
      const padding = 4;
      const bgW = metrics.width + padding * 2;
      const bgH = 18;

      ctx.fillStyle = '#ffffff';
      ctx.strokeStyle = '#e2e8f0';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(labelX - bgW / 2, labelY - bgH / 2, bgW, bgH, 4);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = '#475569';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(arrow.label, labelX, labelY);
      ctx.restore();
    }

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
    controller = new CanvasController(canvas, container, render);
    
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    
    canvas.addEventListener('mousedown', controller.handleMouseDown);
    window.addEventListener('mousemove', controller.handleMouseMove);
    window.addEventListener('mouseup', controller.handleMouseUp);
    canvas.addEventListener('wheel', controller.handleWheel, { passive: false });
    canvas.addEventListener('dblclick', controller.handleDoubleClick);

    canvas.addEventListener('touchstart', controller.handleTouchStart, { passive: false });
    canvas.addEventListener('touchmove', controller.handleTouchMove, { passive: false });
    canvas.addEventListener('touchend', controller.handleTouchEnd, { passive: false });

    const int = setInterval(render, 1000/60);
    return () => {
      window.removeEventListener('resize', resizeCanvas);
      canvas.removeEventListener('mousedown', controller.handleMouseDown);
      window.removeEventListener('mousemove', controller.handleMouseMove);
      window.removeEventListener('mouseup', controller.handleMouseUp);
      canvas.removeEventListener('wheel', controller.handleWheel);
      canvas.removeEventListener('dblclick', controller.handleDoubleClick);
      canvas.removeEventListener('touchstart', controller.handleTouchStart);
      canvas.removeEventListener('touchmove', controller.handleTouchMove);
      canvas.removeEventListener('touchend', controller.handleTouchEnd);
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
