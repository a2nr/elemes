<script lang="ts">
  let {
    storageKey,
    initialData,
    onRun,
    compiling
  }: {
    storageKey?: string;
    initialData?: any;
    onRun?: () => void;
    compiling?: boolean;
  } = $props();

  let iframe = $state<HTMLIFrameElement>(null!);
  let saving = $state(false);

  // Setup message listener to sync storage from iframe and wait for ready
  $effect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.data?.type === 'FLOWCHART_SAVE') {
        saving = true;
        if (storageKey) {
          localStorage.setItem(storageKey, event.data.payload);
        }
        setTimeout(() => saving = false, 1000);
      } else if (event.data?.type === 'FLOWCHART_RESET') {
        if (storageKey) {
          localStorage.removeItem(storageKey);
        }
        handleLoad(true);
      } else if (event.data?.type === 'FLOWCHART_READY') {
        // If READY is received, it means the iframe just loaded or was reset.
        // We check if the last message from iframe was a request to reset.
        // For simplicity, we can just send the data.
        handleLoad();
      }
    }
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  });

  export function handleLoad(ignoreDraft = false) {
    if (iframe && iframe.contentWindow) {
      let draftData = null;
      if (storageKey && !ignoreDraft) {
        const draft = localStorage.getItem(storageKey);
        if (draft) {
          try {
            draftData = JSON.parse(draft);
          } catch(e) {}
        }
      }
      
      iframe.contentWindow.postMessage({
        type: 'FLOWCHART_LOAD',
        payload: JSON.stringify({
          initialData: initialData,
          draftData: draftData
        })
      }, '*');
    }
  }
  // Gunakan cache-busting sederhana agar tidak membuka Nginx default yang tersimpan di cache
  let cb = $state(Date.now());
  export function getFlowchartText(): Promise<string> {
    return new Promise((resolve) => {
      const requestId = Math.random().toString(36).substring(7);
      const handler = (event: MessageEvent) => {
        if (event.data?.type === 'FLOWCHART_TEXT_RESPONSE' && event.data?.requestId === requestId) {
          window.removeEventListener('message', handler);
          resolve(event.data.payload);
        }
      };
      window.addEventListener('message', handler);
      
      if (iframe && iframe.contentWindow) {
        iframe.contentWindow.postMessage({
          type: 'FLOWCHART_GET_TEXT',
          requestId: requestId
        }, '*');
      } else {
        window.removeEventListener('message', handler);
        resolve('');
      }
      
      // Timeout fallback
      setTimeout(() => {
        window.removeEventListener('message', handler);
        resolve('');
      }, 2000);
    });
  }
</script>

<div class="flowchart-container">
  {#if onRun}
  <button 
    type="button" 
    class="floating-action-btn" 
    onclick={onRun} 
    disabled={compiling}
    title="Evaluasi alur logika Anda"
  >
    <span class="btn-icon">{compiling ? '⌛' : '▶'}</span>
    <span class="btn-text">{compiling ? 'Mengevaluasi...' : 'Cek Flowchart'}</span>
  </button>
  {/if}

  {#if storageKey}
    <div class="storage-indicator-inline" title={saving ? "Menyimpan draf..." : "Draf tersimpan di browser"}>
      <span class="indicator-icon" class:saving>
        {saving ? '●' : '☁'}
      </span>
      <span class="indicator-text">Auto-save</span>
    </div>
  {/if}
  
  <iframe
    bind:this={iframe}
    class="flowchart-iframe"
    src="/flowchart/?iframe=true&cb={cb}"
    title="Flowchart Editor"
  ></iframe>
</div>

<style>
  .flowchart-container {
    position: relative;
    width: 100%;
    flex: 1;
    min-height: 400px;
    border: none;
    border-radius: var(--radius);
    overflow: hidden;
    background: #fff;
    display: flex;
    flex-direction: column;
  }

  .flowchart-iframe {
    width: 100%;
    flex: 1;
    border: none;
  }

  .floating-action-btn {
    position: absolute;
    top: 64px;
    left: 12px;
    z-index: 10;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: #10b981;
    color: white;
    border: none;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .floating-action-btn:hover:not(:disabled) {
    background: #059669;
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(16, 185, 129, 0.4);
  }

  .floating-action-btn:active:not(:disabled) {
    transform: translateY(0);
  }

  .floating-action-btn:disabled {
    background: #9ca3af;
    cursor: not-allowed;
    box-shadow: none;
  }

  .btn-icon {
    font-size: 1rem;
    line-height: 1;
  }

  .storage-indicator-inline {
    position: absolute;
    bottom: 1rem;
    right: 1.5rem;
    z-index: 10;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 12px;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    pointer-events: none;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
    opacity: 0.8;
  }
  
  .indicator-icon {
    line-height: 1;
    font-size: 0.8rem;
    color: var(--color-success);
  }
  
  .indicator-icon.saving {
    color: var(--color-primary);
    animation: pulse 1s infinite;
  }
  
  .indicator-text {
    font-weight: 500;
  }

  @keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.4; }
    100% { opacity: 1; }
  }
</style>
