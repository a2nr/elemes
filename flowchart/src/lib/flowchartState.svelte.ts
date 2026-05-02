export interface Shape {
  id: string;
  type: 'rect' | 'roundrect' | 'diamond' | 'circle' | 'parallelogram';
  x: number;
  y: number;
  w: number;
  h: number;
  r: number;
  text: string;
  fillColor: string;
  strokeColor: string;
  strokeWidth: number;
}

export interface Arrow {
  id: string;
  type: 'arrow';
  fromId: string;
  toId: string;
  label: string;
  strokeColor: string;
  strokeWidth: number;
  routing?: 'straight' | 'orthogonal' | 'curved';
  points: {x: number, y: number}[];
}

export class FlowchartState {
  shapes = $state<Shape[]>([]);
  arrows = $state<Arrow[]>([]);
  selectedIds = $state<string[]>([]);
  tool = $state<string>('select');
  zoom = $state<number>(1);
  panX = $state<number>(0);
  panY = $state<number>(0);
  
  isIframeMode = $state<boolean>(false);
  isReadonly = $state<boolean>(false);
  initialData = $state<any>(null);
  
  isDragging = $state<boolean>(false);
  isPanning = $state<boolean>(false);
  dragStart = $state<{x: number, y: number} | null>(null);
  dragOffset = $state<any>(null);
  
  creatingShape = $state<Partial<Shape> | null>(null);
  creatingArrow = $state<{x: number, y: number} | null>(null);
  
  isResizing = $state<boolean>(false);
  resizeHandle = $state<string | null>(null);
  resizeStart = $state<{x: number, y: number} | null>(null);
  resizingShape = $state<Shape | null>(null);
  
  arrowStartId = $state<string | null>(null);
  arrowTemp = $state<{x: number, y: number} | null>(null);
  arrowPointsTemp = $state<{x: number, y: number}[]>([]);
  
  history = $state<string[]>([]);
  historyIndex = $state<number>(-1);
  maxHistory = 50;
  
  snapGrid = $state<boolean>(true);
  gridSize = $state<number>(20);

  nextId = 1;

  generateId() {
    return 's_' + (this.nextId++);
  }

  saveHistory() {
    this.history = this.history.slice(0, this.historyIndex + 1);
    this.history.push(JSON.stringify({ shapes: this.shapes, arrows: this.arrows }));
    if (this.history.length > this.maxHistory) {
      this.history.shift();
    }
    this.historyIndex = this.history.length - 1;
    this.saveDraft();
  }

  undo() {
    if (this.historyIndex <= 0) return;
    this.historyIndex--;
    const data = JSON.parse(this.history[this.historyIndex]);
    this.shapes = data.shapes;
    this.arrows = data.arrows;
    this.selectedIds = [];
    this.saveDraft();
  }

  redo() {
    if (this.historyIndex >= this.history.length - 1) return;
    this.historyIndex++;
    const data = JSON.parse(this.history[this.historyIndex]);
    this.shapes = data.shapes;
    this.arrows = data.arrows;
    this.selectedIds = [];
    this.saveDraft();
  }

  get canUndo() { return this.historyIndex > 0; }
  get canRedo() { return this.historyIndex < this.history.length - 1; }

  loadData(data: { shapes: Shape[], arrows: Arrow[], zoom?: number, panX?: number, panY?: number }) {
    // Deep copy to prevent mutating the source (like initialData) when editing
    const clonedData = JSON.parse(JSON.stringify(data));
    this.shapes = clonedData.shapes || [];
    this.arrows = (clonedData.arrows || []).map((a: Arrow) => ({
      ...a,
      routing: a.routing || 'straight'
    }));
    this.zoom = clonedData.zoom || 1;
    this.panX = clonedData.panX || 0;
    this.panY = clonedData.panY || 0;
    
    // Update nextId
    let maxId = 0;
    this.shapes.concat(this.arrows as any).forEach((item) => {
      if (item.id && item.id.startsWith('s_')) {
        const num = parseInt(item.id.substring(2));
        if (!isNaN(num) && num > maxId) maxId = num;
      }
    });
    this.nextId = maxId + 1;
    
    // Initial history
    this.history = [];
    this.historyIndex = -1;
    this.saveHistory();
  }

  saveDraft() {
    const data = JSON.stringify({
      shapes: this.shapes,
      arrows: this.arrows,
      zoom: this.zoom,
      panX: this.panX,
      panY: this.panY
    });
    localStorage.setItem('flowchart_draft', data);
    
    // Notify parent window (if in iframe)
    if (window.parent && window.parent !== window) {
      window.parent.postMessage({
        type: 'FLOWCHART_SAVE',
        payload: data
      }, '*');
    }
  }

  loadDraft() {
    const draft = localStorage.getItem('flowchart_draft');
    if (draft) {
      try {
        const data = JSON.parse(draft);
        this.loadData(data);
      } catch (e) {
        console.error("Failed to load draft", e);
      }
    }
  }

  deleteSelected() {
    this.shapes = this.shapes.filter(s => !this.selectedIds.includes(s.id));
    this.arrows = this.arrows.filter(a => 
      !this.selectedIds.includes(a.id) && 
      !this.selectedIds.includes(a.fromId) && 
      !this.selectedIds.includes(a.toId)
    );
    this.selectedIds = [];
    this.saveHistory();
  }
}

export const fcState = new FlowchartState();
