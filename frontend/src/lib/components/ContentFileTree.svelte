<script lang="ts">
	import type { TreeNode } from '$services/contentEditor';

	interface Props {
		nodes: TreeNode[];
		activePath: string | null;
		root: 'content' | 'assets';
		onselect: (path: string) => void;
		oncreate?: (type: 'file' | 'folder', parentPath: string) => void;
		onrename?: (path: string) => void;
		ondelete?: (path: string) => void;
		level?: number;
	}

	let {
		nodes,
		activePath,
		root,
		onselect,
		oncreate,
		onrename,
		ondelete,
		level = 0
	}: Props = $props();

	let expandedFolders = $state<Set<string>>(new Set());
	let renamingPath = $state<string | null>(null);
	let renameValue = $state('');
	let hoveredPath = $state<string | null>(null);

	function toggleFolder(path: string) {
		if (expandedFolders.has(path)) {
			expandedFolders.delete(path);
			expandedFolders = new Set(expandedFolders);
		} else {
			expandedFolders.add(path);
			expandedFolders = new Set(expandedFolders);
		}
	}

	function handleSelect(node: TreeNode) {
		if (node.type === 'folder') {
			toggleFolder(node.path);
		} else {
			onselect(node.path);
		}
	}

	function handleCopyPath(path: string) {
		const fullPath = root === 'assets' ? `/assets/${path}` : path;
		navigator.clipboard.writeText(fullPath);
		// Simple toast feedback
		const toast = document.createElement('div');
		toast.textContent = 'Path disalin';
		toast.style.cssText = 'position:fixed;bottom:1rem;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:6px 16px;border-radius:8px;font-size:0.8rem;z-index:10000;';
		document.body.appendChild(toast);
		setTimeout(() => toast.remove(), 1500);
	}

	function startRename(path: string, currentValue: string) {
		renamingPath = path;
		renameValue = currentValue;
	}

	function confirmRename(node: TreeNode) {
		if (renameValue && renameValue !== node.name && onrename) {
			const parentPath = node.path.substring(0, node.path.lastIndexOf('/'));
			const newPath = parentPath ? `${parentPath}/${renameValue}` : renameValue;
			onrename(newPath);
		}
		renamingPath = null;
	}

	function getIcon(node: TreeNode): string {
		if (node.type === 'folder') return expandedFolders.has(node.path) ? '📂' : '📁';
		switch (node.ext) {
			case '.md': return '📝';
			case '.png': case '.jpg': case '.jpeg': case '.gif': case '.webp': return '🖼️';
			case '.svg': return '🎨';
			default: return '📄';
		}
	}
</script>

<ul class="file-tree" class:tree-root={level === 0}>
	{#each nodes as node (node.path)}
		<li
			class="tree-item"
			class:active={activePath === node.path}
			class:folder={node.type === 'folder'}
			onmouseenter={() => hoveredPath = node.path}
			onmouseleave={() => hoveredPath = null}
		>
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="tree-row"
				style:padding-left="{level * 16 + 8}px"
				onclick={() => handleSelect(node)}
				role="treeitem"
				tabindex="0"
				onkeydown={(e) => { if (e.key === 'Enter') handleSelect(node); }}
			>
				<span class="tree-icon">{getIcon(node)}</span>
				{#if renamingPath === node.path}
					<input
						class="rename-input"
						type="text"
						value={renameValue}
						onchange={(e) => { renameValue = (e.target as HTMLInputElement).value; }}
						onblur={() => confirmRename(node)}
						onkeydown={(e) => {
							if (e.key === 'Enter') confirmRename(node);
							if (e.key === 'Escape') renamingPath = null;
						}}
						onclick={(e) => e.stopPropagation()}
					/>
				{:else}
					<span class="tree-name">{node.name}</span>
				{/if}					{#if hoveredPath === node.path && renamingPath !== node.path}
						<span class="tree-actions">
							{#if node.type === 'file' && root === 'assets'}
								<button
									type="button"
									class="action-btn"
									title="Copy path"
									onclick={(e) => { e.stopPropagation(); handleCopyPath(node.path); }}
								>📋</button>
							{/if}
							{#if onrename}
								<button
									type="button"
									class="action-btn"
									title="Rename"
									onclick={(e) => { e.stopPropagation(); startRename(node.path, node.name); }}
								>✏️</button>
							{/if}
							{#if ondelete}
								<button
									type="button"
									class="action-btn"
									title="Delete"
									onclick={(e) => { e.stopPropagation(); ondelete!(node.path); }}
								>🗑️</button>
							{/if}
						</span>
					{/if}
			</div>
			{#if node.type === 'folder' && node.children && expandedFolders.has(node.path)}
				<svelte:self
					nodes={node.children}
					{activePath}
					{root}
					{onselect}
					{oncreate}
					{onrename}
					{ondelete}
					level={level + 1}
				/>
			{/if}
		</li>
	{/each}
</ul>

<style>
	.file-tree {
		list-style: none;
		margin: 0;
		padding: 0;
		font-size: 0.85rem;
	}
	.tree-root {
		overflow-y: auto;
		max-height: 100%;
	}
	.tree-item {
		border-bottom: 1px solid var(--color-border, #eee);
	}
	.tree-row {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 6px 8px;
		cursor: pointer;
		transition: background 0.1s;
		user-select: none;
	}
	.tree-row:hover {
		background: var(--color-bg-secondary, #f5f5f5);
	}
	.active .tree-row {
		background: color-mix(in srgb, var(--color-primary, #339af0) 12%, var(--color-bg, #fff));
		border-left: 3px solid var(--color-primary, #339af0);
	}
	.tree-icon {
		flex-shrink: 0;
		font-size: 0.9rem;
	}
	.tree-name {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.tree-actions {
		display: flex;
		gap: 2px;
		flex-shrink: 0;
	}
	.action-btn {
		background: none;
		border: none;
		cursor: pointer;
		padding: 2px 4px;
		font-size: 0.75rem;
		border-radius: 4px;
		transition: background 0.15s;
	}
	.action-btn:hover {
		background: var(--color-border, #ddd);
	}
	.rename-input {
		flex: 1;
		padding: 2px 6px;
		border: 1px solid var(--color-primary, #339af0);
		border-radius: 4px;
		font-size: 0.85rem;
		outline: none;
	}
</style>
