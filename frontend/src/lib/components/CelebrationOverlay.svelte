<script lang="ts">
	import { fade } from 'svelte/transition';

	let { visible = $bindable() }: { visible: boolean } = $props();

	function dismiss() {
		visible = false;
	}

	// Auto dismiss after 3 seconds
	$effect(() => {
		if (visible) {
			const timer = setTimeout(() => {
				visible = false;
			}, 3000);
			return () => clearTimeout(timer);
		}
	});
</script>

{#if visible}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="celebration-overlay" onclick={dismiss} transition:fade={{ duration: 300 }}>
		<div class="celebration-content">
			<div class="celebration-icon">✓</div>
			<p class="celebration-text">Selamat! Latihan Selesai!</p>
			<p class="celebration-hint">(Klik untuk menutup)</p>
		</div>
	</div>
{/if}

<style>
	.celebration-overlay {
		position: absolute;
		inset: 0;
		z-index: 9999;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(0, 0, 0, 0.7);
		cursor: pointer;
		border-radius: inherit;
	}
	.celebration-content {
		text-align: center;
		animation: celebPop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
		pointer-events: none;
	}
	.celebration-icon {
		width: 100px;
		height: 100px;
		margin: 0 auto 1.5rem;
		background: #198754;
		color: #fff;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 3rem;
		font-weight: 700;
		box-shadow: 0 0 20px rgba(25, 135, 84, 0.5);
	}
	.celebration-text {
		font-size: 1.8rem;
		font-weight: 700;
		color: #ffffff;
		text-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
		margin-bottom: 0.5rem;
	}
	.celebration-hint {
		font-size: 0.9rem;
		color: rgba(255, 255, 255, 0.7);
		font-style: italic;
	}
	@keyframes celebPop {
		0% { transform: scale(0.5); opacity: 0; }
		100% { transform: scale(1); opacity: 1; }
	}
</style>
