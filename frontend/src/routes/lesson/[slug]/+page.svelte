<script lang="ts">
	import { page } from '$app/stores';
	import CodeEditor from '$components/CodeEditor.svelte';
	import OutputPanel from '$components/OutputPanel.svelte';
	import ProgressBadge from '$components/ProgressBadge.svelte';
	import { compileCode, trackProgress, getKeyText } from '$services/api';
	import { auth } from '$stores/auth';
	import type { LessonContent } from '$types/lesson';

	// Data from +page.ts load function (SSR + client)
	let { data: pageData } = $props();
	let data = $state<LessonContent | null>(pageData.lesson);

	// Editor state
	let currentCode = $state(data?.initial_code ?? '');
	let compileOutput = $state('');
	let compileError = $state('');
	let compiling = $state(false);
	let compileSuccess = $state<boolean | null>(null);

	// UI state
	let showSolution = $state(false);
	let activeTab = $state<'editor' | 'output'>('editor');

	let editor: CodeEditor;

	const slug = $derived($page.params.slug);

	// Update data when navigating between lessons (pageData changes)
	$effect(() => {
		const lesson = pageData.lesson;
		if (lesson) {
			data = lesson;
			currentCode = lesson.initial_code ?? '';
			compileOutput = '';
			compileError = '';
			compileSuccess = null;
			showSolution = false;
			activeTab = 'editor';
		}
	});

	async function handleRun() {
		if (!data) return;
		compiling = true;
		compileOutput = '';
		compileError = '';
		compileSuccess = null;
		activeTab = 'output';

		try {
			const code = editor?.getCode() ?? currentCode;
			const res = await compileCode({ code, language: data.language });

			if (res.success) {
				compileOutput = res.output;
				compileSuccess = true;

				// Check if output matches expected output for auto-completion
				if (data.expected_output && auth.isLoggedIn) {
					const actual = res.output.trim();
					const expected = data.expected_output.trim();
					if (actual === expected) {
						const lessonName = slug.replace('.md', '');
						await trackProgress(auth.token, lessonName);
						data.lesson_completed = true;
					}
				}
			} else {
				compileError = res.error || 'Compilation failed';
				compileSuccess = false;
			}
		} catch {
			compileError = 'Gagal terhubung ke server';
			compileSuccess = false;
		} finally {
			compiling = false;
		}
	}

	function handleReset() {
		if (!data) return;
		currentCode = data.initial_code;
		editor?.setCode(data.initial_code);
		compileOutput = '';
		compileError = '';
		compileSuccess = null;
	}

	function handleShowSolution() {
		if (!data?.solution_code) return;
		showSolution = !showSolution;
		if (showSolution) {
			editor?.setCode(data.solution_code);
		} else {
			editor?.setCode(currentCode);
		}
	}
</script>

<svelte:head>
	<title>{data?.lesson_title ?? 'Pelajaran'} - Elemes LMS</title>
</svelte:head>

{#if data}
	<!-- Navigation breadcrumb -->
	<div class="lesson-nav">
		<a href="/">&larr; Semua Pelajaran</a>
		{#if data.lesson_completed}
			<ProgressBadge completed={true} />
		{/if}
	</div>

	<h1 class="lesson-title">{data.lesson_title}</h1>

	<!-- Lesson info (collapsible) -->
	{#if data.lesson_info}
		<details class="lesson-info">
			<summary>Informasi Pelajaran</summary>
			<div class="info-content">{@html data.lesson_info}</div>
		</details>
	{/if}

	<!-- Main content area: 2-col on desktop, stacked on mobile -->
	<div class="lesson-layout">
		<!-- Left: Lesson content -->
		<div class="lesson-content">
			<div class="prose">{@html data.lesson_content}</div>

			{#if data.exercise_content}
				<div class="exercise-section">
					<h2>Latihan</h2>
					<div class="prose">{@html data.exercise_content}</div>
				</div>
			{/if}
		</div>

		<!-- Right: Editor + Output -->
		<div class="editor-area">
			<!-- Mobile tabs -->
			<div class="mobile-tabs">
				<button
					class="tab"
					class:active={activeTab === 'editor'}
					onclick={() => (activeTab = 'editor')}
				>
					Editor
				</button>
				<button
					class="tab"
					class:active={activeTab === 'output'}
					onclick={() => (activeTab = 'output')}
				>
					Output
				</button>
			</div>

			<!-- Toolbar -->
			<div class="toolbar">
				<button class="btn btn-success" onclick={handleRun} disabled={compiling}>
					{compiling ? 'Compiling...' : '&#9654; Run'}
				</button>
				<button class="btn btn-secondary" onclick={handleReset}>Reset</button>
				{#if data.solution_code}
					<button class="btn btn-secondary" onclick={handleShowSolution}>
						{showSolution ? 'Sembunyikan Solusi' : 'Lihat Solusi'}
					</button>
				{/if}
				<span class="lang-label">{data.language_display_name}</span>
			</div>

			<!-- Editor panel -->
			<div class="panel" class:hidden-mobile={activeTab !== 'editor'}>
				<CodeEditor
					bind:this={editor}
					code={currentCode}
					language={data.language}
					onchange={(val) => (currentCode = val)}
				/>
			</div>

			<!-- Output panel -->
			<div class="panel" class:hidden-mobile={activeTab !== 'output'}>
				<OutputPanel
					output={compileOutput}
					error={compileError}
					loading={compiling}
					success={compileSuccess}
				/>
			</div>

			<!-- Expected output hint -->
			{#if data.expected_output}
				<details class="expected-output">
					<summary>Expected Output</summary>
					<pre>{data.expected_output}</pre>
				</details>
			{/if}
		</div>
	</div>

	<!-- Prev / Next navigation -->
	<div class="lesson-footer-nav">
		{#if data.prev_lesson}
			<a href="/lesson/{data.prev_lesson.filename}" class="btn btn-secondary">
				&larr; {data.prev_lesson.title}
			</a>
		{:else}
			<span></span>
		{/if}
		{#if data.next_lesson}
			<a href="/lesson/{data.next_lesson.filename}" class="btn btn-primary">
				{data.next_lesson.title} &rarr;
			</a>
		{/if}
	</div>
{/if}

<style>
	.lesson-nav {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.5rem;
		font-size: 0.85rem;
	}

	.lesson-title {
		font-size: 1.5rem;
		margin-bottom: 1rem;
	}

	.lesson-info {
		margin-bottom: 1rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.75rem;
		background: var(--color-bg-secondary);
	}
	.lesson-info summary {
		cursor: pointer;
		font-weight: 600;
		font-size: 0.9rem;
	}
	.info-content {
		margin-top: 0.75rem;
		font-size: 0.85rem;
	}

	/* ── Two-column layout ─────────────────────────────────── */
	.lesson-layout {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1.5rem;
		align-items: start;
	}

	.lesson-content {
		overflow-y: auto;
		max-height: 80vh;
		padding-right: 0.5rem;
	}

	.prose :global(pre) {
		background: var(--color-bg-secondary);
		padding: 0.75rem;
		border-radius: var(--radius);
		overflow-x: auto;
	}
	.prose :global(code) {
		font-family: var(--font-mono);
		font-size: 0.85rem;
	}
	.prose :global(p) {
		margin-bottom: 0.75rem;
	}
	.prose :global(h2),
	.prose :global(h3) {
		margin-top: 1.25rem;
		margin-bottom: 0.5rem;
	}

	.exercise-section {
		margin-top: 1.5rem;
		padding-top: 1rem;
		border-top: 2px solid var(--color-primary);
	}
	.exercise-section h2 {
		color: var(--color-primary);
		font-size: 1.1rem;
	}

	/* ── Editor area ───────────────────────────────────────── */
	.editor-area {
		position: sticky;
		top: 4rem;
	}

	.toolbar {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
		flex-wrap: wrap;
	}
	.btn-secondary {
		background: var(--color-bg-secondary);
		color: var(--color-text);
		border: 1px solid var(--color-border);
	}
	.btn-secondary:hover {
		background: var(--color-border);
	}
	.lang-label {
		margin-left: auto;
		font-size: 0.75rem;
		color: var(--color-text-muted);
		font-weight: 600;
		text-transform: uppercase;
	}

	.panel {
		margin-bottom: 0.75rem;
	}

	.expected-output {
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}
	.expected-output pre {
		background: var(--color-bg-secondary);
		padding: 0.5rem;
		border-radius: var(--radius);
		margin-top: 0.5rem;
	}

	/* ── Footer nav ────────────────────────────────────────── */
	.lesson-footer-nav {
		display: flex;
		justify-content: space-between;
		margin-top: 2rem;
		padding-top: 1rem;
		border-top: 1px solid var(--color-border);
	}

	/* ── Mobile tabs (hidden on desktop) ───────────────────── */
	.mobile-tabs {
		display: none;
	}

	/* ── Mobile responsive ─────────────────────────────────── */
	@media (max-width: 768px) {
		.lesson-layout {
			grid-template-columns: 1fr;
		}
		.lesson-content {
			max-height: none;
			padding-right: 0;
		}
		.editor-area {
			position: static;
		}
		.mobile-tabs {
			display: flex;
			gap: 0;
			margin-bottom: 0.5rem;
			border: 1px solid var(--color-border);
			border-radius: var(--radius);
			overflow: hidden;
		}
		.tab {
			flex: 1;
			padding: 0.5rem;
			border: none;
			background: var(--color-bg-secondary);
			cursor: pointer;
			font-weight: 500;
			font-size: 0.85rem;
		}
		.tab.active {
			background: var(--color-primary);
			color: #fff;
		}
		.hidden-mobile {
			display: none;
		}
	}
</style>
