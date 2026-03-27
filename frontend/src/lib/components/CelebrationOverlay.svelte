<script lang="ts">
	let { visible }: { visible: boolean } = $props();
</script>

{#if visible}
	<div class="celebration-overlay">
		<div class="celebration-content">
			<div class="celebration-icon">&#10003;</div>
			<p class="celebration-text">Selamat! Latihan Selesai!</p>
		</div>
	</div>
{/if}

<style>
	.celebration-overlay {
		position: absolute;
		inset: 0;
		z-index: 10;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(0, 0, 0, 0.4);
		animation: celebFadeIn 0.3s ease-out;
		pointer-events: none;
		border-radius: inherit;
	}
	.celebration-content {
		text-align: center;
		animation: celebPop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
	}
	.celebration-icon {
		width: 80px;
		height: 80px;
		margin: 0 auto 1rem;
		background: var(--color-success);
		color: #fff;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 2.5rem;
		font-weight: 700;
		box-shadow: 0 0 0 0 rgba(25, 135, 84, 0.4);
		animation: celebRing 1.5s ease-out;
	}
	.celebration-text {
		font-size: 1.4rem;
		font-weight: 700;
		color: #fff;
		text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
	}
	@keyframes celebFadeIn {
		from { opacity: 0; }
		to { opacity: 1; }
	}
	@keyframes celebPop {
		0% { transform: scale(0.5); opacity: 0; }
		100% { transform: scale(1); opacity: 1; }
	}
	@keyframes celebRing {
		0% { box-shadow: 0 0 0 0 rgba(25, 135, 84, 0.6); }
		70% { box-shadow: 0 0 0 30px rgba(25, 135, 84, 0); }
		100% { box-shadow: 0 0 0 0 rgba(25, 135, 84, 0); }
	}
</style>
