<script lang="ts">
	import CircuitEditor from '$components/CircuitEditor.svelte';
	import type { LessonContent } from '$types/lesson';

	let {
		data,
		circuitEditor = $bindable(),
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
		circuitEditor: CircuitEditor | null;
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
		{compiling ? 'Mengevaluasi...' : '▶ Cek Rangkaian'}
	</button>
	<button type="button" class="btn btn-secondary" onclick={onReset}>Reset</button>
	{#if data.solution_code && authLoggedIn && lessonCompleted}
		<button type="button" class="btn btn-secondary" onclick={onShowSolution}>
			{showSolution ? 'Sembunyikan Solusi' : 'Lihat Solusi'}
		</button>
	{/if}
</div>
<div class="panel">
	<CircuitEditor
		bind:this={circuitEditor}
		initialCircuit={data.initial_circuit || data.initial_code}
		storageKey={(authLoggedIn && !showSolution) ? `elemes_circuit_${slug}` : undefined}
	/>
</div>
