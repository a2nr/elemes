<script lang="ts">
  import { fcState } from './flowchartState.svelte';

  let fileInput: HTMLInputElement;

  const allTools = [
    { id: 'select', icon: '#icon-pointer', label: 'Pilih' },
    { id: 'hand', icon: '#icon-hand', label: 'Geser' },
    { id: 'rect', icon: '#icon-rect', label: 'Persegi' },
    { id: 'roundrect', icon: '#icon-roundrect', label: 'Persegi Bulat' },
    { id: 'diamond', icon: '#icon-diamond', label: 'Belah Ketupat' },
    { id: 'circle', icon: '#icon-circle', label: 'Lingkaran' },
    { id: 'parallelogram', icon: '#icon-parallelogram', label: 'Jajar Genjang' },
    { id: 'arrow', icon: '#icon-arrow', label: 'Panah' },
    { id: 'line', icon: '#icon-line', label: 'Garis' },
    { id: 'text', icon: '#icon-text', label: 'Teks' },
    { id: 'eraser', icon: '#icon-eraser', label: 'Penghapus' }
  ];
  let isMenuOpen = $state(false);

  // Close menus when clicking outside
  function handleOutsideClick(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest('.dropdown-container')) {
      isMenuOpen = false;
    }
  }

  function handleNew() {
    if (fcState.isIframeMode && fcState.initialData) {
      if (confirm('Kembalikan flowchart ke kondisi awal? Perubahan yang belum disimpan akan hilang.')) {
        fcState.loadData(fcState.initialData);
      }
    } else {
      if (confirm('Buat flowchart baru? Perubahan yang belum disimpan akan hilang.')) {
        fcState.shapes = [];
        fcState.arrows = [];
        fcState.selectedIds = [];
        fcState.zoom = 1;
        fcState.panX = 0;
        fcState.panY = 0;
        fcState.history = [];
        fcState.historyIndex = -1;
        fcState.saveHistory();
      }
    }
  }

  function handleExport() {
    const data = JSON.stringify({
      shapes: fcState.shapes,
      arrows: fcState.arrows,
      zoom: fcState.zoom,
      panX: fcState.panX,
      panY: fcState.panY
    });
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'flowchart.flow';
    a.click();
    URL.revokeObjectURL(url);
  }

  function triggerImport() {
    fileInput.click();
  }

  function handleFileImport(e: Event) {
    const target = e.target as HTMLInputElement;
    if (target.files && target.files[0]) {
      const file = target.files[0];
      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const content = ev.target?.result as string;
          const data = JSON.parse(content);
          fcState.loadData(data);
        } catch (err) {
          alert("Format file tidak valid!");
        }
      };
      reader.readAsText(file);
    }
    // reset
    target.value = '';
  }

</script>

<svelte:window onclick={handleOutsideClick}/>

<div id="topbar">
  <div class="topbar-brand">
    <svg><use href="#icon-logo"/></svg>
    <span>FlowLearn</span>
  </div>
  
  <div class="topbar-divider desktop-only"></div>

  <!-- MOBILE TOOLS (Horizontal Scroll) -->
  <div class="mobile-tools-bar mobile-only">
    {#each allTools as tool}
      <button class="tool-icon-btn" class:active={fcState.tool === tool.id} onclick={() => fcState.tool = tool.id} title={tool.label}>
        <svg><use href={tool.icon}/></svg>
      </button>
    {/each}
  </div>

  <!-- DESKTOP ACTIONS -->
  <div class="topbar-actions desktop-only">
    <button class="topbar-btn" title="Baru" onclick={handleNew}>
      <svg><use href="#icon-new"/></svg>
      <span class="label">Baru</span>
    </button>
    {#if !fcState.isIframeMode}
    <button class="topbar-btn" title="Simpan" onclick={() => fcState.saveDraft()}>
      <svg><use href="#icon-save"/></svg>
      <span class="label">Simpan</span>
    </button>
    <button class="topbar-btn" title="Muat" onclick={() => fcState.loadDraft()}>
      <svg><use href="#icon-import"/></svg>
      <span class="label">Muat</span>
    </button>
    <div class="topbar-divider"></div>
    {/if}
    <button class="topbar-btn" title="Undo" disabled={!fcState.canUndo} onclick={() => fcState.undo()}>
      <svg><use href="#icon-undo"/></svg>
      <span class="label">Undo</span>
    </button>
    <button class="topbar-btn" title="Redo" disabled={!fcState.canRedo} onclick={() => fcState.redo()}>
      <svg><use href="#icon-redo"/></svg>
      <span class="label">Redo</span>
    </button>
    {#if !fcState.isIframeMode}
    <div class="topbar-divider"></div>
    <button class="topbar-btn primary" title="Ekspor" onclick={handleExport}>
      <svg><use href="#icon-export"/></svg>
      <span class="label">Ekspor</span>
    </button>
    <button class="topbar-btn primary" title="Impor" onclick={triggerImport}>
      <svg><use href="#icon-import"/></svg>
      <span class="label">Impor</span>
    </button>
    {/if}
  </div>

  <!-- MOBILE MENU ACTION -->
  <div class="topbar-actions mobile-only">
    <div class="dropdown-container">
      <button class="topbar-btn" onclick={(e) => { e.stopPropagation(); isMenuOpen = !isMenuOpen; }}>
        <svg><use href="#icon-menu"/></svg>
      </button>
      {#if isMenuOpen}
      <div class="dropdown-menu">
        <button class="dropdown-item" onclick={() => { handleNew(); isMenuOpen = false; }}><svg><use href="#icon-new"/></svg><span>Baru</span></button>
        {#if !fcState.isIframeMode}
        <button class="dropdown-item" onclick={() => { fcState.saveDraft(); isMenuOpen = false; }}><svg><use href="#icon-save"/></svg><span>Simpan</span></button>
        <button class="dropdown-item" onclick={() => { fcState.loadDraft(); isMenuOpen = false; }}><svg><use href="#icon-import"/></svg><span>Muat</span></button>
        <div class="dropdown-divider"></div>
        {/if}
        <button class="dropdown-item" disabled={!fcState.canUndo} onclick={() => { fcState.undo(); isMenuOpen = false; }}><svg><use href="#icon-undo"/></svg><span>Undo</span></button>
        <button class="dropdown-item" disabled={!fcState.canRedo} onclick={() => { fcState.redo(); isMenuOpen = false; }}><svg><use href="#icon-redo"/></svg><span>Redo</span></button>
        {#if !fcState.isIframeMode}
        <div class="dropdown-divider"></div>
        <button class="dropdown-item primary-text" onclick={() => { handleExport(); isMenuOpen = false; }}><svg><use href="#icon-export"/></svg><span>Ekspor</span></button>
        <button class="dropdown-item primary-text" onclick={() => { triggerImport(); isMenuOpen = false; }}><svg><use href="#icon-import"/></svg><span>Impor</span></button>
        {/if}
      </div>
      {/if}
    </div>
  </div>
</div>

<input type="file" bind:this={fileInput} accept=".json,.flow" style="display:none" onchange={handleFileImport}>

<style>
  #topbar {
    position: fixed;
    top: 0; left: var(--toolbar-w); right: 0;
    height: var(--topbar-h);
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    padding: 0 16px;
    z-index: 1100;
    gap: 8px;
    box-shadow: var(--shadow);
  }

  .topbar-brand {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-right: 8px;
    font-weight: 700;
    font-size: 18px;
    color: var(--primary);
    white-space: nowrap;
    flex-shrink: 0;
  }
  
  .topbar-brand svg { width: 28px; height: 28px; }

  .topbar-divider {
    width: 1px;
    height: 28px;
    background: var(--border);
    margin: 0 8px;
  }

  .topbar-actions {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: nowrap;
    flex-shrink: 0;
  }

  .topbar-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 8px 12px;
    border: none;
    border-radius: var(--radius);
    background: transparent;
    color: var(--text);
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }

  .topbar-btn:hover { background: #f1f5f9; }
  .topbar-btn svg { width: 18px; height: 18px; flex-shrink: 0; }
  
  .topbar-btn.primary {
    background: var(--primary);
    color: white;
  }
  
  .topbar-btn:disabled {
    opacity: 0.4;
    pointer-events: none;
  }

  /* MOBILE TOOLS BAR */
  .mobile-tools-bar {
    display: flex;
    align-items: center;
    gap: 2px;
    overflow-x: auto;
    flex: 1;
    min-width: 0; /* CRITICAL for flexbox horizontal scroll */
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    padding: 0 12px;
    touch-action: pan-x; /* Allow swiping horizontally but not vertically */
    flex-wrap: nowrap;
    user-select: none;
    -webkit-tap-highlight-color: transparent;
  }
  .mobile-tools-bar::-webkit-scrollbar { display: none; }

  .tool-icon-btn {
    width: 38px;
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted);
    flex-shrink: 0;
  }
  .tool-icon-btn.active {
    background: #dbeafe;
    color: var(--primary);
  }
  .tool-icon-btn svg { width: 20px; height: 20px; }

  .mobile-only { display: none; }

  /* Dropdown Styles */
  .dropdown-container {
    position: relative;
  }

  .dropdown-menu {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: var(--shadow-lg);
    min-width: 180px;
    padding: 8px 0;
    display: flex;
    flex-direction: column;
    z-index: 2000;
  }

  .dropdown-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    width: 100%;
    border: none;
    background: transparent;
    color: var(--text);
    font-size: 14px;
    font-family: inherit;
    font-weight: 600;
    cursor: pointer;
    text-align: left;
  }

  .dropdown-item svg { width: 18px; height: 18px; color: var(--text-muted); }
  .dropdown-item:hover { background: #f1f5f9; }
  
  @media (max-width: 768px) {
    #topbar { left: 0; padding: 0 8px; height: 56px; }
    .topbar-brand { margin-right: 4px; font-size: 0; flex-shrink: 0; } /* Hide text on mobile brand */
    .topbar-brand svg { width: 32px; height: 32px; }
    
    .desktop-only { display: none; }
    .mobile-only { display: flex; }
  }
</style>
