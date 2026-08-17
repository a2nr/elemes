<script lang="ts">
	import { env } from '$env/dynamic/public';
	import { renderMath } from '$lib/actions/renderMath';
	import { tick } from 'svelte';

	export let data: {
		docs: import('$types/docs').DocsIndexEntry[]
	};

	let selectedDoc = data.docs[0];
	let searchQuery = '';
	let docContent: { title: string; html: string } | null = null;
	let docError = false;

	$: filteredDocs = data.docs.filter(d =>
		d.title.toLowerCase().includes(searchQuery.toLowerCase())
	);

	async function selectDoc(doc: import('$types/docs').DocsIndexEntry) {
		selectedDoc = doc;
		searchQuery = '';
		docError = false;
		docContent = null;

		try {
			const res = await fetch(`/api/docs/${doc.slug}`);
			if (!res.ok) throw new Error('Failed to load doc');
			docContent = await res.json();
		} catch {
			docError = true;
		}
	}
</script>

<svelte:head>
	<title>{selectedDoc?.title || 'Dokumentasi'} - Elemes LMS</title>
</svelte:head>

<div class="docs-layout">
	<aside class="docs-sidebar">
		<div class="docs-search">
			<input
				type="text"
				placeholder="Cari dokumentasi..."
				bind:value={searchQuery}
				class="search-input"
			/>
		</div>
		<nav class="docs-nav">
			{#each filteredDocs as doc (doc.slug)}
				<button
					class:selected={selectedDoc?.slug === doc.slug}
					onclick={() => selectDoc(doc)}
				>
					<span class="doc-order">#{doc.order}</span>
					<span class="doc-title">{doc.title}</span>
					<span class="doc-category">{doc.category}</span>
				</button>
			{/each}
		</nav>
	</aside>

	<main class="docs-content">
		{#if docError}
			<p class="error">Gagal memuat dokumen.</p>
		{:else if !docContent}
			<p class="loading">Pilih dokumen dari sidebar untuk memulai.</p>
		{:else}
			<article class="docs-article prose" use:renderMath>
				<h1>{docContent.title}</h1>
				{@html docContent.html}
			</article>
		{/if}
	</main>
</div>

<style>
	.docs-layout {
		display: flex;
		gap: 0;
		max-width: var(--max-width, 1200px);
		margin: 0 auto;
		padding: 1.5rem;
		height: calc(100vh - 80px);
	}

	.docs-sidebar {
		width: 280px;
		min-width: 240px;
		max-width: 320px;
		border-right: 1px solid var(--color-border);
		overflow-y: auto;
		flex-shrink: 0;
	}

	.docs-search {
		padding: 1rem;
		border-bottom: 1px solid var(--color-border);
	}

	.search-input {
		width: 100%;
		padding: 0.5rem 0.75rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius, 6px);
		background: var(--color-bg);
		color: var(--color-text);
		font-size: 0.9rem;
	}

	.docs-nav {
		display: flex;
		flex-direction: column;
	}

	.docs-nav button {
		text-align: left;
		padding: 0.75rem 1rem;
		border: none;
		background: none;
		cursor: pointer;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		transition: background-color 0.15s;
	}

	.docs-nav button:hover {
		background: var(--color-bg-secondary, #f5f5f5);
	}

	.docs-nav button.selected {
		background: var(--color-bg-accent, #e8f0fe);
		border-left: 3px solid var(--color-accent, #2563eb);
	}

	.doc-order {
		font-size: 0.7rem;
		color: var(--color-text-muted, #888);
	}

	.doc-title {
		font-size: 0.9rem;
		font-weight: 500;
		color: var(--color-text);
	}

	.doc-category {
		font-size: 0.7rem;
		color: var(--color-text-muted, #888);
		text-transform: uppercase;
	}

	.docs-content {
		flex: 1;
		overflow-y: auto;
		padding: 2rem;
	}

	.docs-article {
		max-width: 760px;
	}

	.docs-article h1 {
		font-size: 2rem;
		margin-bottom: 1.5rem;
		border-bottom: 1px solid var(--color-border);
		padding-bottom: 0.5rem;
	}

	.loading,
	.error {
		color: var(--color-text-muted, #888);
	}

	@media (max-width: 768px) {
		.docs-layout {
			flex-direction: column;
			height: auto;
			padding: 1rem;
		}

		.docs-sidebar {
			width: 100%;
			max-width: none;
			height: 200px;
		}
	}
</style>
