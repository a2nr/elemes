<script lang="ts">
  import { fcState } from './flowchartState.svelte';
</script>

<div id="toolbar">
  <button class="tool-btn" class:active={fcState.tool === 'select'} onclick={() => fcState.tool = 'select'} title="Pilih (V)">
    <svg><use href="#icon-pointer"/></svg>
  </button>
  <button class="tool-btn" class:active={fcState.tool === 'hand'} onclick={() => fcState.tool = 'hand'} title="Geser (H)">
    <svg><use href="#icon-hand"/></svg>
  </button>
  <div class="tool-divider"></div>
  <button class="tool-btn" class:active={fcState.tool === 'rect'} onclick={() => fcState.tool = 'rect'} title="Persegi (R)">
    <svg><use href="#icon-rect"/></svg>
  </button>
  <button class="tool-btn" class:active={fcState.tool === 'roundrect'} onclick={() => fcState.tool = 'roundrect'} title="Persegi Bulat">
    <svg><use href="#icon-roundrect"/></svg>
  </button>
  <button class="tool-btn" class:active={fcState.tool === 'diamond'} onclick={() => fcState.tool = 'diamond'} title="Belah Ketupat (D)">
    <svg><use href="#icon-diamond"/></svg>
  </button>
  <button class="tool-btn" class:active={fcState.tool === 'circle'} onclick={() => fcState.tool = 'circle'} title="Lingkaran (C)">
    <svg><use href="#icon-circle"/></svg>
  </button>
  <button class="tool-btn" class:active={fcState.tool === 'parallelogram'} onclick={() => fcState.tool = 'parallelogram'} title="Jajar Genjang">
    <svg><use href="#icon-parallelogram"/></svg>
  </button>
  <div class="tool-divider"></div>
  <button class="tool-btn" class:active={fcState.tool === 'arrow'} onclick={() => fcState.tool = 'arrow'} title="Panah (A)">
    <svg><use href="#icon-arrow"/></svg>
  </button>
  <button class="tool-btn" class:active={fcState.tool === 'line'} onclick={() => fcState.tool = 'line'} title="Garis (L)">
    <svg><use href="#icon-line"/></svg>
  </button>
  <button class="tool-btn" class:active={fcState.tool === 'text'} onclick={() => fcState.tool = 'text'} title="Teks (T)">
    <svg><use href="#icon-text"/></svg>
  </button>
  <div class="tool-divider"></div>
  <button class="tool-btn" class:active={fcState.tool === 'eraser'} onclick={() => fcState.tool = 'eraser'} title="Penghapus (E)">
    <svg><use href="#icon-eraser"/></svg>
  </button>
</div>

<style>
  #toolbar {
    position: fixed;
    top: 0; left: 0; bottom: 0;
    width: 64px;
    background: var(--surface);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 8px 6px;
    gap: 4px;
    z-index: 1000;
    box-shadow: var(--shadow);
    overflow-y: auto;
    transition: all 0.3s;
  }

  .tool-btn {
    width: 50px;
    height: 50px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    border-radius: var(--radius);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .tool-btn:hover { background: #f1f5f9; color: var(--text); }
  .tool-btn.active { background: #dbeafe; color: var(--primary); }
  .tool-btn svg { width: 24px; height: 24px; }

  .tool-divider {
    width: 36px;
    height: 1px;
    background: var(--border);
    margin: 4px 0;
    flex-shrink: 0;
  }

  @media (max-width: 768px) {
    #toolbar {
      display: none !important;
    }
  }
</style>
