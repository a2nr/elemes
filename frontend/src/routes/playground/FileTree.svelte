<script lang="ts">
	import { playgroundStore } from '$stores/playground';

	interface Props {
		onselect?: (id: string) => void;
	}

	let { onselect }: Props = $props();

	let renamingId = $state<string | null>(null);
	let renameValue = $state('');

	function selectFile(id: string) {
		playgroundStore.setActiveFile(id);
		onselect?.(id);
	}

	function startRename(id: string, currentName: string) {
		renamingId = id;
		renameValue = currentName;
	}

	function commitRename(id: string) {
		const name = renameValue.trim();
		if (name) playgroundStore.renameFile(id, name);
		renamingId = null;
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
		<span class="ft-title">File</span>
		<button class="ft-new-btn" onclick={() => playgroundStore.addFile('main.c')} title="Buat file baru">
			+
		</button>
	</div>

	{#if $playgroundStore.files.length === 0}
		<div class="ft-empty">Belum ada file. Klik + untuk membuat.</div>
	{:else}
		<div class="ft-list">
			{#each $playgroundStore.files as file (file.id)}
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
						<input
							class="ft-rename"
							bind:value={renameValue}
							onkeydown={(e) => {
								if (e.key === 'Enter') commitRename(file.id);
								if (e.key === 'Escape') renamingId = null;
							}}
							onclick={(e) => e.stopPropagation()}
						/>
					{:else}
						<span class="ft-name">{file.name}</span>
					{/if}
					{#if file.modified}
						<span class="ft-dot" title="Belum tersimpan">·</span>
					{/if}
					<span class="ft-actions">
						<button
							class="ft-action"
							title="Ubah nama"
							onclick={(e) => {
								e.stopPropagation();
								startRename(file.id, file.name);
							}}
						>
							✎
						</button>
						<button
							class="ft-action"
							title="Hapus"
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

	.ft-rename {
		flex: 1;
		min-width: 0;
		font-size: 0.8rem;
		padding: 0.15rem 0.3rem;
		border: 1px solid var(--color-primary);
		border-radius: 4px;
		background: var(--color-bg);
		color: var(--color-text);
		outline: none;
	}

	.ft-dot {
		color: var(--color-warning);
		font-size: 0.9rem;
		flex-shrink: 0;
	}

	.ft-actions {
		display: flex;
		gap: 0.15rem;
		flex-shrink: 0;
		opacity: 0;
		transition: opacity 0.15s;
	}

	.ft-item:hover .ft-actions {
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

	::-webkit-scrollbar {
		width: 6px;
	}

	::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 3px;
	}
</style>
