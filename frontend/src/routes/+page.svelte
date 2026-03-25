<script lang="ts">
	import LessonCard from '$components/LessonCard.svelte';

	let { data } = $props();
</script>

<svelte:head>
	<title>Elemes LMS</title>
</svelte:head>

{#if data.homeContent}
	<section class="home-intro">
		{@html data.homeContent}
	</section>
{/if}

{#if data.lessons.length === 0}
	<p class="empty">Belum ada pelajaran yang tersedia.</p>
{:else}
	<section class="lesson-grid">
		{#each data.lessons as lesson (lesson.filename)}
			<LessonCard {lesson} />
		{/each}
	</section>
{/if}

<style>
	.home-intro {
		margin-bottom: 2rem;
	}
	.lesson-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: 1rem;
	}
	.empty {
		text-align: center;
		padding: 3rem;
		color: var(--color-text-muted);
	}
</style>
