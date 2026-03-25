<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { themeDark } from '$stores/theme';

	interface Props {
		code?: string;
		language?: string;
		readonly?: boolean;
		onchange?: (value: string) => void;
	}

	let { code = '', language = 'c', readonly = false, onchange }: Props = $props();

	let container: HTMLDivElement;
	let view: any;
	let ready = $state(false);

	// Store module references after dynamic import
	let CM: any;

	async function loadCodeMirror() {
		const [viewMod, stateMod, cmdsMod, langMod, autoMod, cppMod, pyMod, themeMod] =
			await Promise.all([
				import('@codemirror/view'),
				import('@codemirror/state'),
				import('@codemirror/commands'),
				import('@codemirror/language'),
				import('@codemirror/autocomplete'),
				import('@codemirror/lang-cpp'),
				import('@codemirror/lang-python'),
				import('@codemirror/theme-one-dark'),
			]);

		CM = { ...viewMod, ...stateMod, ...cmdsMod, ...langMod, ...autoMod, cpp: cppMod.cpp, python: pyMod.python, oneDark: themeMod.oneDark };
	}

	function getLanguageExtension(lang: string) {
		switch (lang) {
			case 'python': return CM.python();
			default: return CM.cpp();
		}
	}

	function buildExtensions() {
		const exts = [
			CM.lineNumbers(),
			CM.highlightActiveLineGutter(),
			CM.highlightActiveLine(),
			CM.history(),
			CM.bracketMatching(),
			CM.closeBrackets(),
			CM.indentOnInput(),
			CM.syntaxHighlighting(CM.defaultHighlightStyle, { fallback: true }),
			CM.keymap.of([
				...CM.defaultKeymap,
				...CM.historyKeymap,
				...CM.closeBracketsKeymap,
				CM.indentWithTab,
			]),
			getLanguageExtension(language),
			CM.EditorView.lineWrapping,
			CM.EditorState.readOnly.of(readonly),
		];

		if ($themeDark) {
			exts.push(CM.oneDark);
		}

		if (onchange) {
			exts.push(
				CM.EditorView.updateListener.of((update: any) => {
					if (update.docChanged) {
						onchange(update.state.doc.toString());
					}
				})
			);
		}

		return exts;
	}

	function createEditor() {
		if (!CM || !container) return;
		if (view) view.destroy();

		view = new CM.EditorView({
			state: CM.EditorState.create({
				doc: code,
				extensions: buildExtensions(),
			}),
			parent: container,
		});
	}

	onMount(async () => {
		await loadCodeMirror();
		createEditor();
		ready = true;
	});

	onDestroy(() => {
		view?.destroy();
	});

	// Recreate editor when theme changes
	$effect(() => {
		const _dark = $themeDark;
		if (ready && container && view) {
			const currentCode = view.state.doc.toString();
			code = currentCode;
			createEditor();
		}
	});

	/** Replace editor content programmatically (e.g. reset / load solution). */
	export function setCode(newCode: string) {
		if (!view) return;
		view.dispatch({
			changes: { from: 0, to: view.state.doc.length, insert: newCode },
		});
	}

	/** Return current editor content. */
	export function getCode(): string {
		return view?.state.doc.toString() ?? code;
	}
</script>

<div class="editor-wrapper" bind:this={container}>
	{#if !ready}
		<div class="editor-loading">Memuat editor...</div>
	{/if}
</div>

<style>
	.editor-wrapper {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
		font-size: 0.9rem;
	}
	.editor-wrapper :global(.cm-editor) {
		min-height: 200px;
		max-height: 60vh;
	}
	.editor-wrapper :global(.cm-scroller) {
		overflow: auto;
	}
	.editor-loading {
		min-height: 200px;
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--color-text-muted);
		font-size: 0.85rem;
		background: var(--color-bg-secondary);
	}
	@media (max-width: 768px) {
		.editor-wrapper :global(.cm-editor) {
			min-height: 150px;
			max-height: 50vh;
		}
	}
</style>
