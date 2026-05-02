import type { Shape, Arrow } from './flowchartState.svelte';

export interface ParsedData {
  shapes: Shape[];
  arrows: Arrow[];
}

export function parseFlowchartText(text: string): ParsedData {
  const lines = text.split('\n');
  const shapes: Shape[] = [];
  const arrows: Arrow[] = [];
  const shapeMap = new Map<string, Shape>();

  // Regex patterns
  // Node: id[type] "Label"
  const nodeRegex = /^(\w+)(?:\[(\w+)\])?(?:\s+"([^"]+)")?$/;
  // Edge: from --> to "Label"
  const edgeRegex = /^(\w+)\s*-->\s*(\w+)(?:\s+"([^"]+)")?$/;

  let nextAutoId = 1;

  function getOrCreateShape(id: string, typeStr?: string, label?: string): Shape {
    if (shapeMap.has(id)) {
      const existing = shapeMap.get(id)!;
      if (typeStr) existing.type = typeStr as any;
      if (label) existing.text = label;
      return existing;
    }

    const shape: Shape = {
      id,
      type: (typeStr as any) || 'rect',
      x: 0,
      y: 0,
      w: 180,
      h: 50,
      r: typeStr === 'roundrect' ? 25 : 0,
      text: label || id,
      fillColor: '#ffffff',
      strokeColor: '#000000',
      strokeWidth: 2
    };

    // Adjust defaults based on type
    if (shape.type === 'circle') {
      shape.w = 80;
      shape.h = 80;
    } else if (shape.type === 'diamond') {
      shape.w = 150;
      shape.h = 80;
    }

    shapes.push(shape);
    shapeMap.set(id, shape);
    return shape;
  }

  for (let line of lines) {
    line = line.trim();
    if (!line || line.startsWith('#') || line.startsWith('//')) continue;

    const edgeMatch = line.match(edgeRegex);
    if (edgeMatch) {
      const [, fromId, toId, label] = edgeMatch;
      getOrCreateShape(fromId);
      getOrCreateShape(toId);

      arrows.push({
        id: `a_${nextAutoId++}`,
        type: 'arrow',
        fromId,
        toId,
        label: label || '',
        strokeColor: '#000000',
        strokeWidth: 2,
        routing: 'straight',
        points: []
      });
      continue;
    }

    const nodeMatch = line.match(nodeRegex);
    if (nodeMatch) {
      const [, id, type, label] = nodeMatch;
      getOrCreateShape(id, type, label);
    }
  }

  return { shapes, arrows };
}

export function exportToFlowchartText(shapes: Shape[], arrows: Arrow[]): string {
  let text = "";
  
  // Export Nodes
  shapes.forEach(s => {
    text += `${s.id}[${s.type}] "${s.text.replace(/"/g, '\\"')}"\n`;
  });

  if (shapes.length > 0) text += "\n";

  // Export Edges
  arrows.forEach(a => {
    const label = a.label ? ` "${a.label.replace(/"/g, '\\"')}"` : "";
    text += `${a.fromId} --> ${a.toId}${label}\n`;
  });

  return text;
}
