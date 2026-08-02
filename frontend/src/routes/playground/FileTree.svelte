<script lang="ts">
	import { playgroundStore } from '$stores/playground';
	import {
		uniqueDefaultName,
		validateFileName,
		type PlaygroundLanguage
	} from '$services/playground-files';

	interface Props {
		language?: PlaygroundLanguage;
		onselect?: (id: string) => void;
	}

	let { language = 'c', onselect }: Props = $props();

	const langLabel = $derived(language === 'python' ? 'Python' : 'C');

	const filteredFiles = $derived(
		$playgroundStore.files.filter((f) => {
			const ext = f.name.includes('.') ? f.name.slice(f.name.lastIndexOf('.')) : '';
			return language === 'python' ? ext === '.py' : ext === '.c' || ext === '.h';
		})
	);

	let renamingId = $state<string | null>(null);
	let renameValue = $state('');
	let renameError = $state<string | null>(null);
	let renameInput = $state<HTMLInputElement | null>(null);

	/** Nama file lain (untuk deteksi duplikat saat rename). */
	function otherNames(currentId: string | null): string[] {
		return $playgroundStore.files
			.filter((f) => f.id !== currentId)
			.map((f) => f.name);
	}

	function selectFile(id: string) {
		playgroundStore.setActiveFile(id);
		onselect?.(id);
	}

	function beginRename(id: string, initialName: string) {
		renamingId = id;
		renameValue = initialName;
		renameError = null;
		// Fokus + select nama (tanpa ekstensi) di tick berikutnya
		queueMicrotask(() => {
			renameInput?.focus();
			const dot = initialName.lastIndexOf('.');
			renameInput?.setSelectionRange(0, dot > 0 ? dot : initialName.length);
		});
	}

	/** Rename kosong/Enter → batal (tanpa menghapus file). */
	function cancelRename() {
		renamingId = null;
		renameError = null;
	}

	function commitRename(id: string) {
		const res = validateFileName(renameValue, language, otherNames(id));
		if (!res.ok) {
			renameError = res.reason;
			return; // input tetap terbuka — JANGAN commit nama invalid
		}
		playgroundStore.renameFile(id, res.name);
		renamingId = null;
		renameError = null;
	}

	/** Tambah file baru dengan nama unik, langsung mode rename. */
	function addFile() {
		const base = 'untitled';
		const name = uniqueDefaultName(base, language, $playgroundStore.files.map((f) => f.name));
		const id = playgroundStore.addFile(name);
		beginRename(id, name);
	}

	function getFileIcon(name: string): string {
		const ext = name.split('.').pop()?.toLowerCase();
		switch (ext) {
			case 'c':
			case 'h':
				return '◼';
			case 'py':
				return '🐍';
			case 'cpp':
			case 'hpp':
				return '▲';
			case 'txt':
				return '📄';
			case 'md':
				return '📝';
			default:
				return '📁';
		}
	}
</script>

<div class="file-tree">
	<div class="ft-header">
		<span class="ft-title">{langLabel} Files</span>
		<div class="ft-header-actions">
			<button
				class="ft-new-btn"
				onclick={addFile}
				title={`Buat file ${language === 'python' ? '.py' : '.c/.h'} baru`}
				aria-label="Tambah file baru"
			>
				+
			</button>
		</div>
	</div>

	{#if filteredFiles.length === 0}
		<div class="ft-empty">Belum ada file. Klik + untuk membuat.</div>
	{:else}
		<div class="ft-list">
			{#each filteredFiles as file (file.id)}
				<div
					class="ft-item"
					class:active={file.id === $playgroundStore.activeFileId}
					role="button"
					tabindex="0"
					onclick={() => selectFile(file.id)}
					onkeydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') {
							e.preventDefault();
							selectFile(file.id);
						}
					}}
				>
					<span class="ft-icon">{getFileIcon(file.name)}</span>
					{#if renamingId === file.id}
						<span class="ft-rename-wrap">
							<input
								bind:this={renameInput}
								class="ft-rename"
								class:invalid={!!renameError}
								value={renameValue}
								oninput={(e) => {
									renameValue = e.currentTarget.value;
									renameError = null;
								}}
								onkeydown={(e) => {
									if (e.key === 'Enter') {
										e.preventDefault();
										commitRename(file.id);
									}
									if (e.key === 'Escape') {
										e.preventDefault();
										cancelRename();
									}
								}}
								onclick={(e) => e.stopPropagation()}
								aria-label="Nama file baru"
							/>
							{#if renameError}
								<span class="ft-rename-error" role="alert">{renameError}</span>
							{/if}
						</span>
					{:else}
						<span class="ft-name">{file.name}</span>
					{/if}
					{#if file.modified}
						<span class="ft-dot" title="Belum tersimpan">·</span>
					{/if}
					<span class="ft-row-actions">
						<button
							class="ft-action"
							title="Ubah nama"
							aria-label={`Ubah nama ${file.name}`}
							onclick={(e) => {
								e.stopPropagation();
								beginRename(file.id, file.name);
							}}
						>
							✎
						</button>
						<button
							class="ft-action"
							title="Hapus"
							aria-label={`Hapus ${file.name}`}
							onclick={(e) => {
								e.stopPropagation();
								playgroundStore.deleteFile(file.id);
							}}
						>
							🗑
						</button>
					</span>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.file-tree {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		background: var(--color-bg-secondary);
		border-right: 1px solid var(--color-border);
	}

	.ft-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--color-border);
		background: var(--color-bg);
		flex-shrink: 0;
	}

	.ft-title {
		font-weight: 600;
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--color-text-muted);
	}

	.ft-header-actions {
		display: flex;
		gap: 0.25rem;
	}

	.ft-new-btn {
		background: var(--color-primary);
		border: none;
		color: #fff;
		width: 22px;
		height: 22px;
		border-radius: 4px;
		cursor: pointer;
		font-size: 15px;
		line-height: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		transition: opacity 0.15s;
	}

	.ft-new-btn:hover {
		opacity: 0.85;
	}

	.ft-empty {
		padding: 1rem;
		color: var(--color-text-muted);
		font-size: 0.78rem;
		text-align: center;
		margin-top: 1rem;
	}

	.ft-list {
		flex: 1;
		overflow-y: auto;
		min-height: 0;
	}

	.ft-item {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.4rem 0.75rem;
		cursor: pointer;
		transition: background 0.15s;
		border-left: 2px solid transparent;
	}

	.ft-item:hover {
		background: var(--color-bg);
	}

	.ft-item.active {
		background: var(--color-bg);
		border-left-color: var(--color-primary);
	}

	.ft-icon {
		font-size: 0.95rem;
		flex-shrink: 0;
	}

	.ft-name {
		font-size: 0.8rem;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		color: var(--color-text);
		flex: 1;
		min-width: 0;
	}

	.ft-rename-wrap {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.ft-rename {
		width: 100%;
		font-size: 0.8rem;
		padding: 0.15rem 0.3rem;
		border: 1px solid var(--color-primary);
		border-radius: 4px;
		background: var(--color-bg);
		color: var(--color-text);
		outline: none;
	}

	.ft-rename.invalid {
		border-color: var(--color-danger);
	}

	.ft-rename-error {
		font-size: 0.68rem;
		color: var(--color-danger);
		line-height: 1.3;
	}

	.ft-dot {
		color: var(--color-warning);
		font-size: 0.9rem;
		flex-shrink: 0;
	}

	.ft-row-actions {
		display: flex;
		gap: 0.15rem;
		flex-shrink: 0;
		opacity: 0;
		transition: opacity 0.15s;
	}

	.ft-item:hover .ft-row-actions,
	.ft-item:focus-within .ft-row-actions,
	.ft-item:focus .ft-row-actions {
		opacity: 1;
	}

	.ft-action {
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		font-size: 0.85rem;
		padding: 0.15rem;
		border-radius: 4px;
		transition: background 0.15s, color 0.15s;
	}

	.ft-action:hover {
		background: var(--color-bg-secondary);
		color: var(--color-primary);
	}

	.ft-action:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 1px;
	}

	.file-tree ::-webkit-scrollbar {
		width: 6px;
	}

	.file-tree ::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 3px;
	}
</style>
