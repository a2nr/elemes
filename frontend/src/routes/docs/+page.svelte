<script lang="ts">
	import { env } from '$env/dynamic/public';
	import { renderMath } from '$lib/actions/renderMath';
	import { tick } from 'svelte';
	import type { ApiReferenceEntry } from '$types/docs';

	export let data: {
		docs: import('$types/docs').DocsIndexEntry[]
	};

	let selectedDoc = data.docs[0];
	let searchQuery = '';
	let docContent: { title: string; html: string } | null = null;
	let docError = false;

	let apiRefMode = false;
	let apiRefEntries: ApiReferenceEntry[] | null = null;
	let apiRefError = false;

	$: filteredDocs = data.docs.filter(d =>
		d.title.toLowerCase().includes(searchQuery.toLowerCase())
	);

	async function selectDoc(doc: import('$types/docs').DocsIndexEntry) {
		apiRefMode = false;
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

	async function selectApiReference() {
		apiRefMode = true;
		selectedDoc = data.docs[0];
		searchQuery = '';
		docError = false;
		docContent = null;

		if (apiRefEntries) return; // sudah pernah dimuat — reuse
		apiRefError = false;
		try {
			const res = await fetch('/api/docs/api-reference');
			if (!res.ok) throw new Error('Failed to load API reference');
			const payload = await res.json();
			apiRefEntries = payload.endpoints;
		} catch {
			apiRefError = true;
		}
	}
</script>

<svelte:head>
	<title>{apiRefMode ? 'API Reference' : selectedDoc?.title || 'Dokumentasi'} - Elemes LMS</title>
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
			<button
				class:selected={apiRefMode}
				class="api-ref-entry"
				onclick={selectApiReference}
			>
				<span class="doc-order">⚙</span>
				<span class="doc-title">API Reference</span>
				<span class="doc-category">endpoints</span>
			</button>
			{#each filteredDocs as doc (doc.slug)}
				<button
					class:selected={!apiRefMode && selectedDoc?.slug === doc.slug}
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
		{#if apiRefMode}
			{#if apiRefError}
				<p class="error">Gagal memuat API Reference.</p>
			{:else if !apiRefEntries}
				<p class="loading">Memuat API Reference…</p>
			{:else}
				<article class="api-ref">
					<h1>API Reference</h1>
					<p class="api-ref-subtitle">
						Daftar endpoint Flask yang terdaftar ({apiRefEntries.length} endpoint).
					</p>
					<div class="api-ref-list">
						{#each apiRefEntries as entry (entry.path + entry.method.join(','))}
							<section class="endpoint">
								<header class="endpoint-header">
									<div class="endpoint-methods">
										{#each entry.method as m}
											<span class="method method-{m.toLowerCase()}">{m}</span>
										{/each}
									</div>
									<code class="endpoint-path">{entry.path}</code>
									<span class="endpoint-auth" class:auth-required={entry.auth}>
										{entry.auth ? 'Auth: guru' : 'Publik'}
									</span>
								</header>
								{#if entry.doc}
									<p class="endpoint-doc">{entry.doc}</p>
								{/if}
							</section>
						{/each}
					</div>
				</article>
			{/if}
		{:else if docError}
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

	.docs-nav .api-ref-entry {
		border-bottom: 1px solid var(--color-border);
		margin-bottom: 0.5rem;
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

	/* ── API Reference ─────────────────────────────────────────── */

	.api-ref {
		max-width: 860px;
	}

	.api-ref h1 {
		font-size: 2rem;
		margin-bottom: 0.25rem;
		border-bottom: 1px solid var(--color-border);
		padding-bottom: 0.5rem;
	}

	.api-ref-subtitle {
		color: var(--color-text-muted, #888);
		margin: 0.5rem 0 1.5rem;
	}

	.api-ref-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.endpoint {
		border: 1px solid var(--color-border);
		border-radius: var(--radius, 6px);
		padding: 0.75rem 1rem;
	}

	.endpoint-header {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.endpoint-methods {
		display: flex;
		gap: 0.25rem;
	}

	.method {
		font-size: 0.7rem;
		font-weight: 700;
		padding: 0.15rem 0.45rem;
		border-radius: 4px;
		letter-spacing: 0.03em;
	}

	.method-get { background: #e6f4ea; color: #137333; }
	.method-post { background: #e8f0fe; color: #1a73e8; }
	.method-put { background: #fef7e0; color: #b06000; }
	.method-patch { background: #f3e8fd; color: #7627bb; }
	.method-delete { background: #fce8e6; color: #c5221f; }

	.endpoint-path {
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--color-text);
		word-break: break-all;
	}

	.endpoint-auth {
		margin-left: auto;
		font-size: 0.7rem;
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
		background: #e6f4ea;
		color: #137333;
	}

	.endpoint-auth.auth-required {
		background: #fce8e6;
		color: #c5221f;
	}

	.endpoint-doc {
		margin: 0.5rem 0 0;
		font-size: 0.85rem;
		color: var(--color-text-muted, #555);
		white-space: pre-wrap;
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
