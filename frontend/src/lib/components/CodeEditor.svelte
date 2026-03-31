<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { themeDark } from '$stores/theme';

	interface Props {
		code?: string;
		language?: string;
		readonly?: boolean;
		noPaste?: boolean;
		storageKey?: string;
		onchange?: (value: string) => void;
	}

	let { code = '', language = 'c', readonly = false, noPaste = false, storageKey, onchange }: Props = $props();

	let container: HTMLDivElement;
	let view: any;
	let ready = $state(false);
	let saving = $state(false);
	let lastThemeDark: boolean | undefined;
	let lastStorageKey = $state<string | undefined>(undefined);

	// Store module references after dynamic import
	let CM: any;
	let cleanupNoPaste: (() => void) | undefined;
	let saveTimeout: any;

	function saveToStorage(value: string) {
		if (!storageKey) return;
		saving = true;
		clearTimeout(saveTimeout);
		saveTimeout = setTimeout(() => {
			sessionStorage.setItem(storageKey, value);
			saving = false;
		}, 1000);
	}

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

		if (onchange || storageKey) {
			exts.push(
				CM.EditorView.updateListener.of((update: any) => {
					if (update.docChanged) {
						const val = update.state.doc.toString();
						onchange?.(val);
						saveToStorage(val);
					}
				})
			);
		}

		if (noPaste) {
			// Layer 1: DOM event handlers (catches standard paste/drop on desktop)
			exts.push(
				CM.EditorView.domEventHandlers({
					paste(event: ClipboardEvent) {
						event.preventDefault();
						return true;
					},
					drop(event: DragEvent) {
						event.preventDefault();
						return true;
					},
					// Mobile browsers may use beforeinput with insertFromPaste/Drop
					beforeinput(event: InputEvent) {
						if (event.inputType === 'insertFromPaste' ||
							event.inputType === 'insertFromDrop' ||
							event.inputType === 'insertFromPasteAsQuotation') {
							event.preventDefault();
							return true;
						}
						return false;
					},
				})
			);

			// Layer A: Transaction filter — blocks paste at CM6 abstraction level.
			// 1) Blocks transactions explicitly tagged 'input.paste' / 'input.drop'
			//    (standard long-press → "Paste" on Android, and all desktop paste).
			// 2) Heuristic for GBoard clipboard panel: GBoard injects clipboard
			//    text through the IME as 'input.type.compose', indistinguishable
			//    from regular typing at the event level. We detect it by checking
			//    for unusually large insertions (multi-line or long single chunk)
			//    that cannot come from normal keyboard input.
			exts.push(
				CM.EditorState.transactionFilter.of((tr: any) => {
					if (tr.isUserEvent('input.paste') || tr.isUserEvent('input.drop')) {
						return [];
					}
					// Heuristic: detect paste disguised as typing via mobile IME
					if (tr.isUserEvent('input.type') || tr.isUserEvent('input.type.compose')) {
						let dominated = false;
						tr.changes.iterChanges(
							(_fA: number, _tA: number, _fB: number, _tB: number, inserted: any) => {
								// 3+ lines → definitely paste
								// 2 lines with >20 chars → likely paste (Enter+indent is ~5-10 chars)
								if (inserted.lines > 2 || (inserted.lines > 1 && inserted.length > 20)) {
									dominated = true;
								}
							}
						);
						if (dominated) return [];
					}
					return tr;
				})
			);

			// Layer C: Clipboard input filter — replaces clipboard text with ''
			// before CM6 processes it (available since @codemirror/view 6.17.0)
			if (CM.EditorView.clipboardInputFilter) {
				exts.push(
					CM.EditorView.clipboardInputFilter.of(() => '')
				);
			}

			// Layer D: Input handler — intercepts text from DOM mutations.
			// GBoard clipboard panel injects text via DOM mutations tagged as
			// 'input.type.compose'. inputHandler fires for these mutations and
			// can block them if the text looks like paste (multi-line).
			exts.push(
				CM.EditorView.inputHandler.of(
					(_view: any, _from: number, _to: number, text: string) => {
						if (text.includes('\n') && text.length > 20) {
							return true; // block: multi-line insertion = paste
						}
						return false; // allow normal typing
					}
				)
			);
		}

		return exts;
	}

	function createEditor() {
		if (!CM || !container) return;
		if (view) view.destroy();

		let initialCode = code;
		if (storageKey) {
			const saved = sessionStorage.getItem(storageKey);
			if (saved !== null) {
				initialCode = saved;
			}
		}

		view = new CM.EditorView({
			state: CM.EditorState.create({
				doc: initialCode,
				extensions: buildExtensions(),
			}),
			parent: container,
		});
	}

	function setupNoPasteListeners() {
		if (!noPaste || !container) return;
		const prevent = (e: Event) => { e.preventDefault(); e.stopPropagation(); };
		container.addEventListener('paste', prevent, true);
		container.addEventListener('copy', prevent, true);
		container.addEventListener('cut', prevent, true);
		container.addEventListener('contextmenu', prevent, true);
		container.addEventListener('drop', prevent, true);

		// Layer B: Post-hoc paste revert via input event.
		// The 'input' event fires AFTER content has been inserted, making it
		// reliable on mobile where beforeinput may be non-cancelable.
		// If Layer A (transactionFilter) blocks the paste, no input event fires,
		// so there is no double-undo risk.
		const revertPaste = (e: Event) => {
			const ie = e as InputEvent;
			if (ie.inputType === 'insertFromPaste' ||
				ie.inputType === 'insertFromDrop' ||
				ie.inputType === 'insertFromPasteAsQuotation') {
				if (view && CM) {
					CM.undo(view);
				}
			}
		};
		container.addEventListener('input', revertPaste, true);

		cleanupNoPaste = () => {
			container.removeEventListener('paste', prevent, true);
			container.removeEventListener('copy', prevent, true);
			container.removeEventListener('cut', prevent, true);
			container.removeEventListener('contextmenu', prevent, true);
			container.removeEventListener('drop', prevent, true);
			container.removeEventListener('input', revertPaste, true);
		};
	}

	onMount(async () => {
		await loadCodeMirror();
		lastThemeDark = $themeDark;
		createEditor();
		setupNoPasteListeners();
		ready = true;
	});

	onDestroy(() => {
		cleanupNoPaste?.();
		view?.destroy();
	});

	// Recreate editor ONLY when theme actually changes (not on ready/container changes)
	$effect(() => {
		const dark = $themeDark;
		if (!ready || !container || !view) return;
		if (lastThemeDark === dark) return;
		lastThemeDark = dark;
		const currentCode = view.state.doc.toString();
		code = currentCode;
		createEditor();
		// Restore focus after theme-driven recreation
		requestAnimationFrame(() => view?.focus());
	});

	// Handle navigation (change of slug/storageKey)
	$effect(() => {
		if (storageKey !== lastStorageKey) {
			lastStorageKey = storageKey;
			if (!ready || !view || !storageKey) return;

			const saved = sessionStorage.getItem(storageKey);
			if (saved !== null) {
				setCode(saved);
			} else {
				setCode(code);
			}
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
<div class="editor-wrapper" class:no-paste={noPaste} bind:this={container}>
	{#if !ready}
		<div class="editor-loading">Memuat editor...</div>
	{/if}
	{#if storageKey}
		<div class="storage-indicator" title={saving ? "Menyimpan draf..." : "Draf tersimpan di browser"}>
			<span class="indicator-icon" class:saving>
				{saving ? '●' : '☁'}
			</span>
			<span class="indicator-text">Auto-save</span>
		</div>
	{/if}
</div>

<style>
	.editor-wrapper {
		position: relative;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
		font-size: 0.9rem;
		-webkit-touch-callout: none;
	}
	.storage-indicator {
		position: absolute;
		bottom: 8px;
		right: 12px;
		z-index: 10;
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 4px 8px;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 12px;
		font-size: 0.7rem;
		color: var(--color-text-muted);
		pointer-events: none;
		opacity: 0.8;
		box-shadow: 0 2px 4px rgba(0,0,0,0.1);
	}
	.indicator-icon {
		line-height: 1;
		font-size: 0.8rem;
		color: var(--color-success);
	}
	.indicator-icon.saving {
		color: var(--color-primary);
		animation: pulse 1s infinite;
	}
	@keyframes pulse {
		0% { opacity: 1; }
		50% { opacity: 0.4; }
		100% { opacity: 1; }
	}
	.indicator-text {
		font-weight: 500;
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
	.editor-wrapper.no-paste :global(.cm-content) {
		-webkit-touch-callout: none;
	}
	@media (max-width: 768px) {
		.editor-wrapper :global(.cm-editor) {
			min-height: 150px;
			max-height: 50vh;
		}
	}
</style>
