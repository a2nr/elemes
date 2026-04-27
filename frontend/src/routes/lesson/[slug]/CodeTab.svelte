<script lang="ts">
	import CodeEditor from '$components/CodeEditor.svelte';
	import type { LessonContent } from '$types/lesson';

	let {
		data,
		currentLanguage = $bindable(),
		currentCode = $bindable(),
		editor = $bindable(),
		compiling,
		authLoggedIn,
		lessonCompleted,
		showSolution,
		slug,
		onRun,
		onReset,
		onShowSolution
	}: {
		data: LessonContent;
		currentLanguage: string;
		currentCode: string;
		editor: CodeEditor | null;
		compiling: boolean;
		authLoggedIn: boolean;
		lessonCompleted: boolean;
		showSolution: boolean;
		slug: string;
		onRun: () => void;
		onReset: () => void;
		onShowSolution: () => void;
	} = $props();
</script>

<div class="toolbar">
	<button type="button" class="btn btn-success" onclick={onRun} disabled={compiling}>
		{compiling ? 'Compiling...' : '▶ Run'}
	</button>
	<button type="button" class="btn btn-secondary" onclick={onReset}>Reset</button>
	{#if data.solution_code && authLoggedIn && lessonCompleted}
		<button type="button" class="btn btn-secondary" onclick={onShowSolution}>
			{showSolution ? 'Sembunyikan Solusi' : 'Lihat Solusi'}
		</button>
	{/if}
	<span class="lang-label">{currentLanguage === 'python' ? 'Python' : 'C'}</span>
</div>

<div class="panel">
	{#key currentLanguage}
	<CodeEditor
		bind:this={editor}
		code={currentCode}
		language={currentLanguage}
		noPaste={true}
		storageKey={(authLoggedIn && !showSolution) ? `elemes_draft_${slug}_${currentLanguage}` : undefined}
		onchange={(val) => { if (!showSolution) currentCode = val; }}
	/>
	{/key}
</div>

{#if data.expected_output}
	<details class="expected-output">
		<summary>Expected Output</summary>
		<pre>{data.expected_output}</pre>
	</details>
{/if}
