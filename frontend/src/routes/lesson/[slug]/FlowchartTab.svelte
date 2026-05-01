<script lang="ts">
  let {
    storageKey,
    initialData,
  }: {
    storageKey?: string;
    initialData?: any;
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
      } else if (event.data?.type === 'FLOWCHART_READY') {
        handleLoad();
      }
    }
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  });

  function handleLoad() {
    if (iframe && iframe.contentWindow) {
      let draftData = null;
      if (storageKey) {
        const draft = localStorage.getItem(storageKey);
        if (draft) {
          try {
            draftData = JSON.parse(draft);
          } catch(e) {}
        }
      }
      
      if (initialData || draftData) {
        iframe.contentWindow.postMessage({
          type: 'FLOWCHART_LOAD',
          payload: JSON.stringify({
            initialData: initialData,
            draftData: draftData
          })
        }, '*');
      }
    }
  }
  // Gunakan cache-busting sederhana agar tidak membuka Nginx default yang tersimpan di cache
  let cb = $state(Date.now());
</script>

<div class="flowchart-container">
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
