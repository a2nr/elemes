import dagre from 'dagre';
import type { Shape, Arrow } from './flowchartState.svelte';

export function applyAutoLayout(shapes: Shape[], arrows: Arrow[]): { shapes: Shape[], arrows: Arrow[] } {
  const g = new dagre.graphlib.Graph();

  // Set an object for the graph label
  g.setGraph({
    rankdir: 'TB',
    nodesep: 50,
    ranksep: 70,
    marginx: 50,
    marginy: 50
  });

  // Default to assigning a new object as a label for each edge.
  g.setDefaultEdgeLabel(() => ({}));

  // Add nodes to the graph
  shapes.forEach(shape => {
    // Estimate width based on text length if it's too long
    const estimatedW = Math.max(shape.w, shape.text.length * 8 + 40);
    g.setNode(shape.id, { width: estimatedW, height: shape.h });
    // Update shape width for the canvas
    shape.w = estimatedW;
  });

  // Add edges to the graph
  arrows.forEach(arrow => {
    g.setEdge(arrow.fromId, arrow.toId);
  });

  // Calculate layout
  dagre.layout(g);

  // Update shape coordinates
  shapes.forEach(shape => {
    const node = g.node(shape.id);
    if (node) {
      // Dagre uses center coordinates, we use top-left
      shape.x = node.x - node.width / 2;
      shape.y = node.y - node.height / 2;
    }
  });

  // For arrows, we let the canvas logic or a simple straight line handle it for now
  // unless we want to use dagre's edge points.
  // Straight lines are easier to manage with manual dragging later.
  arrows.forEach(arrow => {
    arrow.points = []; // Reset points for straight lines
    arrow.routing = 'straight';
  });

  return { shapes, arrows };
}
