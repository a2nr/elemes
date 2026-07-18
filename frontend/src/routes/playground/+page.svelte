<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import DeployFAB from '$components/DeployFAB.svelte';

	let velxioIframe = $state<HTMLIFrameElement | null>(null);
	type DeployFABHandle = { setHex: (hex: string | null) => void };
	let fabComponent = $state<DeployFABHandle | null>(null);

	const iframeSrc = '/velxio/editor?embed=true&desktopLayout=true';

	function handleMessage(e: MessageEvent) {
		if (!e.data?.type) return;
		if (e.data.type === 'velxio:hex_ready') {
			fabComponent?.setHex(e.data.hex);
		}
	}

	function pushSerialToIframe(text: string) {
		if (!velxioIframe?.contentWindow) return;
		velxioIframe.contentWindow.postMessage({
			type: 'elemes:push_serial',
			text,
			boardId: null
		}, window.location.origin);
	}

	function notifySerialStart() {
		velxioIframe?.contentWindow?.postMessage({ type: 'elemes:start_hardware_serial' }, window.location.origin);
	}

	function notifySerialStop() {
		velxioIframe?.contentWindow?.postMessage({ type: 'elemes:stop_hardware_serial' }, window.location.origin);
	}

	onMount(() => {
		window.addEventListener('message', handleMessage);
	});

	onDestroy(() => {
		window.removeEventListener('message', handleMessage);
	});
</script>

<svelte:head>
	<title>Developer Playground — Velxio</title>
</svelte:head>

<div class="playground-page">
	<iframe
		bind:this={velxioIframe}
		src={iframeSrc}
		title="Velxio Editor"
		allow="bluetooth; clipboard-read; clipboard-write; fullscreen"
		class="velxio-iframe"
		allowfullscreen
	></iframe>

	<DeployFAB
		bind:this={fabComponent}
		{velxioIframe}
		onPushSerial={pushSerialToIframe}
		onSerialStart={notifySerialStart}
		onStopSerial={notifySerialStop}
	/>
</div>

<style>
	.playground-page {
		width: 100%;
		height: 100dvh;
		overflow-y: auto;
		overflow-x: hidden;
		display: flex;
		flex-direction: column;
	}

	.velxio-iframe {
		width: 100%;
		flex: 1;
		min-height: 0;           /* critical: allows flex child to shrink below content size */
		border: none;
		display: block;
		touch-action: pan-y;     /* allow vertical pan inside iframe */
	}

	@media (max-width: 768px) {
		.playground-page {
			overflow-y: auto;
			height: auto;        /* allow page to grow */
			min-height: 100dvh;  /* but always at least fill viewport */
		}
		.velxio-iframe {
			max-height: none;    /* iframe can grow taller than viewport */
			height: auto;
		}
	}
</style>
