<script lang="ts">
  import Icons from './lib/Icons.svelte';
  import Topbar from './lib/Topbar.svelte';
  import Toolbar from './lib/Toolbar.svelte';
  import Properties from './lib/Properties.svelte';
  import Canvas from './lib/Canvas.svelte';
  import { fcState } from './lib/flowchartState.svelte';
  import { parseFlowchartText, exportToFlowchartText } from './lib/parser';
  import { applyAutoLayout } from './lib/layout';
  import { onMount } from 'svelte';

  onMount(() => {
    // Listen for initial data or load from localStorage
    const params = new URLSearchParams(window.location.search);
    if (params.get('draft') === 'true') {
      fcState.loadDraft();
    }
    if (params.get('iframe') === 'true') {
      fcState.isIframeMode = true;
    }
    if (params.get('readonly') === 'true') {
      fcState.isReadonly = true;
    }
    
    // Listen to messages from parent window
    window.addEventListener('message', (event) => {
      if (event.data?.type === 'FLOWCHART_LOAD') {
        try {
          const payload = typeof event.data.payload === 'string' ? JSON.parse(event.data.payload) : event.data.payload;
          
          function processData(data: any) {
            if (typeof data === 'string' && !data.trim().startsWith('{')) {
              const { shapes, arrows } = parseFlowchartText(data);
              return applyAutoLayout(shapes, arrows);
            }
            return data;
          }

          // Legacy format (just data object)
          if (!payload.initialData && !payload.draftData && (payload.shapes || typeof payload === 'string')) {
            const data = processData(payload);
            fcState.initialData = data;
            fcState.loadData(data);
          } else {
            // New format { initialData, draftData }
            if (payload.initialData) {
              fcState.initialData = processData(payload.initialData);
            }
            if (payload.draftData) {
              fcState.loadData(processData(payload.draftData));
            } else if (payload.initialData) {
              fcState.loadData(processData(payload.initialData));
            }
          }
        } catch(e) {
          console.error("Invalid data format", e);
        }
      } else if (event.data?.type === 'FLOWCHART_GET_TEXT') {
        const text = exportToFlowchartText(fcState.shapes, fcState.arrows);
        window.parent.postMessage({
          type: 'FLOWCHART_TEXT_RESPONSE',
          requestId: event.data.requestId,
          payload: text
        }, '*');
      }
    });

    // Notify parent window that we are ready to receive messages
    if (window.parent && window.parent !== window) {
      window.parent.postMessage({ type: 'FLOWCHART_READY' }, '*');
    }
  });

</script>

<main>
  <Icons />
  {#if !fcState.isReadonly}
  <Topbar />
  <Toolbar />
  {/if}
  
  <Canvas />
  
  {#if !fcState.isReadonly}
  <Properties />
  
  <div id="zoom-controls">
    <button class="topbar-btn" title="Perkecil" onclick={() => fcState.zoom = Math.max(0.1, fcState.zoom - 0.1)}>
      <svg><use href="#icon-zoomout"/></svg>
    </button>
    <span class="zoom-label" id="zoom-label">{Math.round(fcState.zoom * 100)}%</span>
    <button class="topbar-btn" title="Perbesar" onclick={() => fcState.zoom = Math.min(5, fcState.zoom + 0.1)}>
      <svg><use href="#icon-zoomin"/></svg>
    </button>
    <button class="topbar-btn" title="Sesuaikan" onclick={() => {fcState.zoom = 1; fcState.panX = 0; fcState.panY = 0;}}>
      <svg><use href="#icon-fit"/></svg>
    </button>
  </div>
  {/if}
</main>

<style>
  main {
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    position: relative;
    font-family: 'Nunito', sans-serif;
  }

  #zoom-controls {
    position: fixed;
    bottom: 16px;
    left: calc(var(--toolbar-w) + 16px);
    display: flex;
    align-items: center;
    gap: 4px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 4px;
    z-index: 100;
    box-shadow: var(--shadow-lg);
  }

  #zoom-controls .topbar-btn {
    width: 36px;
    height: 36px;
    padding: 0;
    font-size: 16px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    border-radius: var(--radius);
    cursor: pointer;
  }

  #zoom-controls .topbar-btn:hover { background: #f1f5f9; }
  #zoom-controls .topbar-btn svg { width: 18px; height: 18px; color: var(--text); }

  #zoom-controls .zoom-label {
    font-size: 12px;
    font-weight: 700;
    color: var(--text-muted);
    min-width: 44px;
    text-align: center;
  }

  @media (max-width: 768px) {
    #zoom-controls {
      bottom: 12px;
      left: calc(var(--toolbar-w) + 8px);
    }
  }
</style>
