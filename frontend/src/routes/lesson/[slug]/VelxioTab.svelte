<script lang="ts">
	let {
		hasArduinoCode,
		velxioError,
		authLoggedIn,
		velxioSaving,
		onSetupBridge
	}: {
		hasArduinoCode: boolean;
		velxioError: boolean;
		authLoggedIn: boolean;
		velxioSaving: boolean;
		onSetupBridge: (iframe: HTMLIFrameElement) => void;
	} = $props();
</script>

{#if velxioError}
	<div class="velxio-fallback">
		Simulator Arduino sedang tidak tersedia.
		Hubungi guru jika masalah berlanjut.
	</div>
{:else}
	{#if authLoggedIn}
		<div class="storage-indicator-inline" title={velxioSaving ? "Menyimpan draf..." : "Draf tersimpan di browser"}>
			<span class="indicator-icon" class:saving={velxioSaving}>
				{velxioSaving ? '●' : '☁'}
			</span>
			<span class="indicator-text">Auto-save</span>
		</div>
	{/if}
	<!-- svelte-ignore a11y_missing_attribute -->
	<iframe
		class="velxio-iframe"
		src="/velxio/editor?embed=true{hasArduinoCode ? '' : '&hideEditor=true'}&lockComponents=true"
		onload={(e) => onSetupBridge(e.currentTarget as HTMLIFrameElement)}
		allow="cross-origin-isolated"
	></iframe>
{/if}
