<script lang="ts">
	import { onMount } from 'svelte';
	import CodeEditor from '$components/CodeEditor.svelte';

	interface Props {
		code?: string;
		fileName?: string;
		initialCursorPos?: number;
		initialLine?: number;
		onchange: (value: string) => void;
		onclose: () => void;
	}

	let {
		code = '',
		fileName = '',
		initialCursorPos,
		initialLine,
		onchange,
		onclose
	}: Props = $props();

	let containerEl: HTMLDivElement;
	let editorRef = $state<any>(null);

	onMount(() => {
		// Handle Escape key to return to preview
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === 'Escape') {
				e.preventDefault();
				e.stopPropagation();
				onclose();
			} else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'e') {
				e.preventDefault();
				e.stopPropagation();
				onclose();
			}
		};

		// Handle click outside editor container to return to preview.
		// Clicks inside the workspace (editor-area) or on focus-preserving
		// controls must NOT close the editor — otherwise picking a tool
		// from the workspace would drop focus / exit edit mode.
		const handleDocumentClick = (e: MouseEvent) => {
			if (!containerEl) return;
			const target = e.target as Node | null;
			if (!target) return;
			const el = target instanceof Element ? target : target.parentElement;
			if (el && (el.closest('.editor-area') || el.closest('[data-preserve-editor-focus]'))) return;
			if (!containerEl.contains(target)) {
				onclose();
			}
		};

		window.addEventListener('keydown', handleKeyDown, true);
		// Delay attaching click-outside listener to avoid triggering on the click that opened the editor
		const timer = setTimeout(() => {
			window.addEventListener('click', handleDocumentClick, true);
		}, 100);

		return () => {
			clearTimeout(timer);
			window.removeEventListener('keydown', handleKeyDown, true);
			window.removeEventListener('click', handleDocumentClick, true);
		};
	});

	export function focus() {
		editorRef?.focus();
	}

	export function scrollToLine(line: number) {
		editorRef?.scrollToLine(line);
	}

	export function setCursorPos(pos: number) {
		editorRef?.setCursorPos(pos);
	}

	export function insertAtCursor(text: string) {
		editorRef?.insertAtCursor(text);
	}

	export function setCode(newCode: string) {
		editorRef?.setCode(newCode);
	}
</script>

<div class="inline-editor-container" bind:this={containerEl}>
	<div class="inline-editor-header">
		<div class="header-left">
			<span class="mode-badge">✏️ Mode Edit</span>
			{#if fileName}
				<span class="file-title">{fileName}</span>
			{/if}
			<span class="help-text">Tekan <kbd>Esc</kbd> atau klik di luar untuk preview</span>
		</div>
		<div class="header-right">
			<button type="button" class="btn-preview-mode" onclick={onclose} title="Kembali ke preview (Esc)">
				👁️ Kembali ke Preview
			</button>
		</div>
	</div>
	<div class="inline-editor-body">
		<CodeEditor
			bind:this={editorRef}
			{code}
			language="markdown"
			{initialCursorPos}
			{initialLine}
			{onchange}
		/>
	</div>
</div>

<style>
	.inline-editor-container {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 500px;
		background: var(--color-bg);
		border-radius: var(--radius);
		overflow: hidden;
		border: 1px solid var(--color-primary, #339af0);
		box-shadow: 0 0 0 1px var(--color-primary, #339af0);
	}

	.inline-editor-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0.4rem 0.75rem;
		background: var(--color-bg-secondary);
		border-bottom: 1px solid var(--color-border);
		flex-shrink: 0;
	}

	.header-left {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-width: 0;
		overflow: hidden;
	}

	.mode-badge {
		font-size: 0.75rem;
		font-weight: 700;
		color: var(--color-primary, #339af0);
		background: color-mix(in srgb, var(--color-primary, #339af0) 15%, transparent);
		padding: 2px 6px;
		border-radius: 4px;
		white-space: nowrap;
	}

	.file-title {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--color-text);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.help-text {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		white-space: nowrap;
	}

	.help-text kbd {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 3px;
		padding: 1px 4px;
		font-size: 0.7rem;
		font-family: inherit;
	}

	.btn-preview-mode {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		color: var(--color-text);
		border-radius: 4px;
		padding: 0.25rem 0.6rem;
		font-size: 0.78rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.15s;
		white-space: nowrap;
	}

	.btn-preview-mode:hover {
		background: var(--color-border);
		color: var(--color-primary, #339af0);
	}

	.inline-editor-body {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
	}

	.inline-editor-body :global(.editor-wrapper) {
		flex: 1;
		min-height: 0;
		border: none;
		border-radius: 0;
	}

	.inline-editor-body :global(.cm-editor) {
		height: 100% !important;
		min-height: 0 !important;
		max-height: none !important;
	}

	.inline-editor-body :global(.cm-scroller) {
		height: 100%;
	}
</style>
