<script lang="ts">
	import type { Lesson } from '$types/lesson';

	interface Props {
		lessons: Lesson[];
		currentSlug: string;
	}

	let { lessons, currentSlug }: Props = $props();
</script>

{#if lessons.length}
	<div class="all-lessons">
		<h3 class="all-lessons-heading">Semua Pelajaran</h3>
		<div class="all-lessons-list">
			{#each lessons as lesson (lesson.filename)}
				<a href="/lesson/{lesson.filename}"
					class="lesson-item"
					class:lesson-item-active={lesson.filename === currentSlug}>
					{#if lesson.completed}
						<span class="lesson-check">&#10003;</span>
					{/if}
					<span class="lesson-item-title">{lesson.title}</span>
				</a>
			{/each}
		</div>
	</div>
{/if}

<style>
	.all-lessons {
		margin-top: 2rem;
		padding-top: 1.5rem;
		border-top: 1px solid var(--color-border);
	}
	.all-lessons-heading {
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		margin-bottom: 0.5rem;
	}
	.all-lessons-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.lesson-item {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.45rem 0.6rem;
		border-radius: 6px;
		font-size: 0.82rem;
		color: var(--color-text);
		text-decoration: none;
		transition: background 0.12s;
	}
	.lesson-item:hover {
		background: var(--color-bg-secondary);
		text-decoration: none;
		color: var(--color-text);
	}
	.lesson-item-active {
		background: var(--color-primary);
		color: #fff;
		font-weight: 600;
	}
	.lesson-item-active:hover {
		background: var(--color-primary-dark);
		color: #fff;
	}
	.lesson-check {
		color: var(--color-success);
		font-size: 0.75rem;
		flex-shrink: 0;
	}
	.lesson-item-active .lesson-check {
		color: #fff;
	}
	.lesson-item-title {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
