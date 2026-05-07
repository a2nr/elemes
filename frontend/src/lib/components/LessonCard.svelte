<script lang="ts">
	import type { Lesson } from '$types/lesson';

	let { lesson }: { lesson: Lesson } = $props();
</script>

<a href="/lesson/{lesson.filename}" class="card lesson-card" class:is-locked={lesson.locked}>
	<div class="card-body">
		<h3 class="card-title">
			{#if lesson.completed}
				<span class="badge-done" title="Selesai">&#10003;</span>
			{:else if lesson.locked}
				<span class="badge-locked" title="Terkunci">&#128274;</span>
			{/if}
			{lesson.title}
		</h3>
		<p class="card-desc">{lesson.description}</p>
	</div>
</a>

<style>
	.lesson-card {
		display: block;
		text-decoration: none;
		color: var(--color-text);
		transition: transform 0.15s, box-shadow 0.15s;
	}
	.lesson-card:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
		text-decoration: none;
	}
	.lesson-card.is-locked {
		background-color: var(--color-bg-muted);
	}
	.lesson-card.is-locked .card-title {
		color: var(--color-text-muted);
	}
	.card-body {
		padding: 1.25rem;
	}
	.card-title {
		font-size: 1rem;
		font-weight: 600;
		margin-bottom: 0.5rem;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.card-desc {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		line-height: 1.4;
	}
	.badge-done {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.4rem;
		height: 1.4rem;
		background: var(--color-success);
		color: #fff;
		border-radius: 50%;
		font-size: 0.75rem;
		flex-shrink: 0;
	}
	.badge-locked {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.25rem;
		height: 1.25rem;
		background: var(--color-border);
		color: var(--color-text-muted);
		border-radius: 50%;
		font-size: 0.7rem;
		flex-shrink: 0;
		line-height: 1;
	}
</style>
