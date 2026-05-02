<script lang="ts">
  import { fcState } from './flowchartState.svelte';

  let selectedShapes = $derived(fcState.shapes.filter(s => fcState.selectedIds.includes(s.id)));
  let selectedArrows = $derived(fcState.arrows.filter(a => fcState.selectedIds.includes(a.id)));

  let hasSelection = $derived(selectedShapes.length > 0 || selectedArrows.length > 0);
  
  function updateShape(key: string, value: any) {
    selectedShapes.forEach(s => {
      (s as any)[key] = value;
    });
    fcState.saveHistory();
  }

  function updateArrow(key: string, value: any) {
    selectedArrows.forEach(a => {
      (a as any)[key] = value;
    });
    fcState.saveHistory();
  }

  // To handle shared properties nicely
  let sharedFillColor = $derived(selectedShapes.length === 1 ? selectedShapes[0].fillColor : '#ffffff');
  let sharedStrokeColor = $derived(selectedShapes.length === 1 ? selectedShapes[0].strokeColor : (selectedArrows.length === 1 ? selectedArrows[0].strokeColor : '#2563eb'));
  let sharedStrokeWidth = $derived(selectedShapes.length === 1 ? selectedShapes[0].strokeWidth : (selectedArrows.length === 1 ? selectedArrows[0].strokeWidth : 2));
  let sharedText = $derived(selectedShapes.length === 1 ? selectedShapes[0].text : '');
  let sharedArrowLabel = $derived(selectedArrows.length === 1 ? selectedArrows[0].label : '');
  
  let collapsed = $state(false);

  const predefinedColors = [
    '#ffffff', '#f8fafc', '#dbeafe', '#fef2f2', '#f0fdf4', '#fefce8',
    '#1e293b', '#64748b', '#2563eb', '#ef4444', '#22c55e', '#eab308'
  ];
</script>

{#if hasSelection}
<div id="properties-panel" class="visible">
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="panel-header" onclick={() => collapsed = !collapsed}>
    <h3>Properti</h3>
    <span class="toggle-icon">{collapsed ? '▲' : '▼'}</span>
  </div>
  
  {#if !collapsed}
  <div class="panel-content">
    {#if selectedShapes.length > 0}
    <label class="prop-row">
      <span class="label-text">Teks</span>
      <input type="text" value={sharedText} oninput={(e) => updateShape('text', (e.target as HTMLInputElement).value)} />
    </label>
    <div class="prop-group">
      <span class="label-text">Warna Isi</span>
      <div class="color-palette">
        {#each predefinedColors as color}
          <button class="color-btn" title={color} style="background: {color};" class:active={sharedFillColor === color} onclick={() => updateShape('fillColor', color)}></button>
        {/each}
      </div>
    </div>
    {/if}

    {#if selectedArrows.length > 0}
    <label class="prop-row">
      <span class="label-text">Label Panah</span>
      <input type="text" value={sharedArrowLabel} oninput={(e) => updateArrow('label', (e.target as HTMLInputElement).value)} />
    </label>

    <div class="prop-group">
      <span class="label-text">Gaya Garis</span>
      <div class="routing-options">
        <button class="route-btn" class:active={selectedArrows[0].routing !== 'orthogonal' && selectedArrows[0].routing !== 'curved'} onclick={() => updateArrow('routing', 'straight')}>
          Lurus
        </button>
        <button class="route-btn" class:active={selectedArrows[0].routing === 'orthogonal'} onclick={() => updateArrow('routing', 'orthogonal')}>
          Siku
        </button>
        <button class="route-btn" class:active={selectedArrows[0].routing === 'curved'} onclick={() => updateArrow('routing', 'curved')}>
          Lengkung
        </button>
      </div>
    </div>
    {/if}

    <div class="prop-group">
      <span class="label-text">Warna Garis</span>
      <div class="color-palette">
        {#each predefinedColors as color}
          <button class="color-btn" title={color} style="background: {color};" class:active={sharedStrokeColor === color} onclick={() => {
            if (selectedShapes.length) updateShape('strokeColor', color);
            if (selectedArrows.length) updateArrow('strokeColor', color);
          }}></button>
        {/each}
      </div>
    </div>
    
    <label class="prop-row">
      <span class="label-text">Tebal Garis</span>
      <input type="number" min="1" max="10" value={sharedStrokeWidth} oninput={(e) => {
        const val = parseInt((e.target as HTMLInputElement).value);
        if (!isNaN(val)) {
          if (selectedShapes.length) updateShape('strokeWidth', val);
          if (selectedArrows.length) updateArrow('strokeWidth', val);
        }
      }} />
    </label>
    
    <div style="margin-top: 16px;">
      <button class="btn-danger" onclick={() => fcState.deleteSelected()}>
        <svg><use href="#icon-delete"/></svg>
        Hapus Terpilih
      </button>
    </div>
  </div>
  {/if}
</div>
{/if}

<style>
  #properties-panel {
    position: fixed;
    top: calc(var(--topbar-h) + 12px);
    right: 12px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0;
    z-index: 100;
    box-shadow: var(--shadow-lg);
    min-width: 240px;
    max-width: 240px;
    display: none;
  }

  #properties-panel.visible { display: block; }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
    user-select: none;
    -webkit-tap-highlight-color: transparent;
    background: var(--primary);
    padding: 10px 16px;
    color: white;
    border-top-left-radius: calc(var(--radius) - 1px);
    border-top-right-radius: calc(var(--radius) - 1px);
  }

  .panel-content {
    padding: 16px;
    background: var(--surface);
    border-bottom-left-radius: calc(var(--radius) - 1px);
    border-bottom-right-radius: calc(var(--radius) - 1px);
  }

  #properties-panel h3 {
    font-size: 13px;
    font-weight: 700;
    color: white;
    margin: 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .toggle-icon {
    font-size: 10px;
    color: white;
    font-weight: bold;
  }

  .prop-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
    gap: 8px;
  }

  .prop-row .label-text {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-muted);
  }

  .prop-group {
    margin-bottom: 12px;
  }

  .prop-group .label-text {
    display: block;
    margin-bottom: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-muted);
  }

  .color-palette {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 6px;
  }

  .color-btn {
    width: 100%;
    aspect-ratio: 1;
    border-radius: 4px;
    border: 1px solid var(--border);
    cursor: pointer;
    padding: 0;
    transition: transform 0.1s;
  }

  .color-btn.active {
    border: 2px solid var(--primary);
    transform: scale(1.15);
    box-shadow: 0 0 0 1px white inset;
  }

  .routing-options {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 4px;
    background: #f1f5f9;
    padding: 3px;
    border-radius: 8px;
  }

  .route-btn {
    padding: 6px 4px;
    border: none;
    background: transparent;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;
  }

  .route-btn.active {
    background: white;
    color: var(--primary);
    shadow: var(--shadow-sm);
  }

  .prop-row input[type="number"],
  .prop-row input[type="text"] {
    width: 120px;
    padding: 6px 8px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
  }

  .btn-danger {
    width: 100%;
    padding: 8px 12px;
    background: #fef2f2;
    color: #ef4444;
    border: 1px solid #fca5a5;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    transition: all 0.15s;
  }
  .btn-danger:hover {
    background: #fee2e2;
    border-color: #f87171;
  }
  .btn-danger svg {
    width: 16px;
    height: 16px;
    color: #ef4444;
  }

  @media (max-width: 768px) {
    #properties-panel {
      top: auto;
      bottom: 48px; /* Above the auto-save indicator */
      right: 8px;
      min-width: 220px;
    }
    
    .panel-header {
      padding: 10px 12px;
    }

    .panel-content {
      padding: 12px;
    }
  }
</style>
