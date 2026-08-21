<script lang="ts">
	import { onMount } from 'svelte';
	import { authIsTeacher, authLoggedIn } from '$stores/auth';
	import { createFloatingPanel } from '$actions/floatingPanel.svelte';
	import CodeEditor from '$components/CodeEditor.svelte';
	import ContentFileTree from '$components/ContentFileTree.svelte';
	import LessonContentView from '$components/LessonContentView.svelte';
	import QuizPreviewReadonly from '$components/QuizPreviewReadonly.svelte';
	import { ContentEditorManager } from '$services/contentEditor.svelte';
	import { getTree, createFolder, createFile, renameEntry, deleteEntry, uploadAsset } from '$services/contentEditor';
	import type { TreeNode } from '$services/contentEditor';

	const mgr = new ContentEditorManager();
	const float = createFloatingPanel();

	let editorRef = $state<any>(null);

	// Load trees on mount
	onMount(async () => {
		await loadTrees();
	});

	// Mobile behavior for floating panel
	$effect(() => {
		if (mgr.isMobile) {
			float.floating = false;
			float.minimized = false;
		}
	});

	async function loadTrees() {
		mgr.treeLoading = true;
		try {
			const [content, assets] = await Promise.all([
				getTree('content'),
				getTree('assets'),
			]);
			mgr.contentTree = content;
			mgr.assetsTree = assets;
		} catch {
			mgr.contentTree = [];
			mgr.assetsTree = [];
		} finally {
			mgr.treeLoading = false;
		}
	}

	function handleSelect(path: string) {
		if (mgr.dirty && !window.confirm('Ada perubahan yang belum disimpan. Lanjut buka file lain?')) {
			return;
		}
		mgr.loadDraft(path);
	}

	function handleEditorChange(value: string) {
		mgr.onBodyChange(value);
	}

	function handleEditorMount() {
		if (editorRef && mgr.body) {
			editorRef.setCode(mgr.body);
		}
	}

	// Tree operations
	async function handleCreateFolder(parentPath: string) {
		const name = window.prompt('Nama folder baru:');
		if (!name) return;
		const path = parentPath ? `${parentPath}/${name}` : name;
		const res = await createFolder(mgr.treeRoot, path);
		if (res.success) {
			await loadTrees();
		} else {
			alert(res.message || 'Gagal membuat folder');
		}
	}

	async function handleCreateFile(parentPath: string) {
		const name = window.prompt('Nama file (.md):');
		if (!name) return;
		const path = parentPath ? `${parentPath}/${name}` : name;
		const res = await createFile(path);
		if (res.success) {
			await loadTrees();
			await mgr.loadDraft(path);
		} else {
			alert(res.message || 'Gagal membuat file');
		}
	}

	async function handleRename(oldPath: string) {
		const oldName = oldPath.split('/').pop() || oldPath;
		const newName = window.prompt('Nama baru:', oldName);
		if (!newName || newName === oldName) return;
		const parentPath = oldPath.substring(0, oldPath.lastIndexOf('/'));
		const newPath = parentPath ? `${parentPath}/${newName}` : newName;
		const res = await renameEntry(mgr.treeRoot, oldPath, newPath);
		if (res.success) {
			await loadTrees();
			if (mgr.activePath === oldPath) {
				await mgr.loadDraft(newPath);
			}
		} else {
			alert(res.message || 'Gagal rename');
		}
	}

	async function handleDelete(path: string) {
		const name = path.split('/').pop() || path;
		if (!window.confirm(`Hapus "${name}"?`)) return;
		const res = await deleteEntry(mgr.treeRoot, path);
		if (res.success) {
			await loadTrees();
			if (mgr.activePath === path) {
				mgr.activePath = null;
				mgr.body = '';
				mgr.draftId = null;
			}
		} else if (res.needs_force) {
			if (window.confirm(`Folder "${name}" tidak kosong. Hapus semua isi?`)) {
				const forceRes = await deleteEntry(mgr.treeRoot, path, true);
				if (forceRes.success) {
					await loadTrees();
					if (mgr.activePath === path) {
						mgr.activePath = null;
						mgr.body = '';
						mgr.draftId = null;
					}
				} else {
					alert(forceRes.message || 'Gagal menghapus');
				}
			}
		} else {
			alert(res.message || 'Gagal menghapus');
		}
	}

	async function handleUpload() {
		const input = document.createElement('input');
		input.type = 'file';
		input.accept = '.png,.jpg,.jpeg,.gif,.webp,.svg';
		input.onchange = async () => {
			const file = input.files?.[0];
			if (!file) return;
			const folder = window.prompt('Folder tujuan (opsional, kosongkan untuk root assets):', '') ?? '';
			const res = await uploadAsset(file, folder);
			if (res.success) {
				await loadTrees();
				const path = res.path;
				if (window.confirm(`Gambar "${file.name}" berhasil diunggah. Salin path ke clipboard?`)) {
					navigator.clipboard.writeText(`/assets/${path}`);
				}
			} else {
				alert(res.message || 'Gagal mengunggah');
			}
		};
		input.click();
	}

	function handleCopyAssetPath(path: string) {
		navigator.clipboard.writeText(`/assets/${path}`);
		const toast = document.createElement('div');
		toast.textContent = 'Path disalin';
		toast.style.cssText = 'position:fixed;bottom:1rem;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:6px 16px;border-radius:8px;font-size:0.8rem;z-index:10000;';
		document.body.appendChild(toast);
		setTimeout(() => toast.remove(), 1500);
	}

	let activeFileName = $derived(mgr.activePath?.split('/').pop() ?? '');
</script>

<svelte:head>
	<title>Editor Konten - Elemes LMS</title>
</svelte:head>

{#if !$authIsTeacher}
	<div class="access-denied">
		<h2>Akses Ditolak</h2>
		<p>Halaman ini hanya untuk guru.</p>
	</div>
{:else}
	<div class="content-editor-layout" class:single-col={float.floating || mgr.isMobile}>
		<!-- Preview Panel -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="preview-panel"
			class:full-width={float.floating || mgr.isMobile}
			onselectstart={(e) => e.preventDefault()}
			oncopy={(e) => e.preventDefault()}
			oncut={(e) => e.preventDefault()}
			oncontextmenu={(e) => e.preventDefault()}
		>
			{#if mgr.previewLoading}
				<div class="preview-loading">Memuat preview...</div>
			{:else if mgr.previewError}
				<div class="preview-error">{mgr.previewError}</div>
			{:else if mgr.previewHtml}
				<LessonContentView
					lessonHtml={mgr.previewHtml}
					exerciseHtml={mgr.previewExerciseHtml}
					quizData={mgr.previewQuizData as any}
					slides={mgr.previewSlides}
					activeTabs={mgr.previewActiveTabs}
				/>
				{#if mgr.previewQuizData.length > 0}
					<QuizPreviewReadonly quizData={mgr.previewQuizData as any} />
				{/if}
			{:else}
				<div class="preview-empty">
					<p>Pilih file dari tree untuk mulai mengedit.</p>
				</div>
			{/if}
		</div>

		<!-- Floating restore button -->
		{#if float.floating && float.minimized && !mgr.isMobile}
			<button type="button" class="float-restore-btn" onclick={float.restore}>&#9654; Editor</button>
		{/if}

		<!-- Workspace Panel (edit) -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="editor-area"
			class:floating={float.floating && !mgr.isMobile && !float.minimized}
			class:floating-hidden={float.floating && float.minimized && !mgr.isMobile}
			class:mobile-sheet={mgr.isMobile}
			class:mobile-hidden={mgr.isMobile && mgr.mobileMode === 'hidden'}
			class:mobile-h30={mgr.isMobile && mgr.mobileMode === 'h30'}
			class:mobile-h50={mgr.isMobile && mgr.mobileMode === 'h50'}
			class:mobile-h70={mgr.isMobile && mgr.mobileMode === 'h70'}
			class:mobile-full={mgr.isMobile && mgr.mobileMode === 'full'}
			style={float.style}
		>
			<!-- Editor Header -->
			<div class="editor-header">
				<span class="editor-filename">{activeFileName || 'Editor'}</span>
				<div class="editor-actions">
					<button
						class="btn btn-sm btn-secondary"
						onclick={() => mgr.handleSave()}
						disabled={mgr.saving || !mgr.dirty || !mgr.activePath}
					>
						{mgr.saving ? 'Menyimpan...' : '💾 Simpan Draft'}
					</button>
					<button
						class="btn btn-sm btn-primary"
						onclick={() => mgr.handlePublish()}
						disabled={mgr.publishing || !mgr.draftId}
					>
						{mgr.publishing ? 'Mempublikasikan...' : '🚀 Publish'}
					</button>
					{#if mgr.isMobile}
						<div class="mobile-mode-toggle">
							<button class="btn btn-sm btn-secondary" onclick={() => mgr.mobileMode = mgr.mobileMode === 'hidden' ? 'h50' : 'hidden'}>
								{mgr.mobileMode === 'hidden' ? '▲' : '▼'}
							</button>
						</div>
					{/if}
				</div>
			</div>

			<!-- Editor Body -->
			<div class="editor-body">
				<!-- File Tree -->
				<div class="tree-panel">
					<div class="tree-header">
						<div class="tree-tabs">
							<button
								class="tree-tab"
								class:active={mgr.treeRoot === 'content'}
								onclick={() => mgr.treeRoot = 'content'}
							>Materi</button>
							<button
								class="tree-tab"
								class:active={mgr.treeRoot === 'assets'}
								onclick={() => mgr.treeRoot = 'assets'}
							>Assets</button>
						</div>
						<div class="tree-actions-header">
							{#if mgr.treeRoot === 'content'}
								<button class="action-btn-sm" title="Buat file baru" onclick={() => handleCreateFile('')}>📄+</button>
							{/if}
							<button class="action-btn-sm" title="Buat folder baru" onclick={() => handleCreateFolder('')}>📁+</button>
							{#if mgr.treeRoot === 'assets'}
								<button class="action-btn-sm" title="Upload gambar" onclick={handleUpload}>⬆️</button>
							{/if}
						</div>
					</div>
					<div class="tree-content">
						{#if mgr.treeLoading}
							<div class="tree-loading">Memuat...</div>
						{:else}
							<ContentFileTree
								nodes={mgr.treeRoot === 'content' ? mgr.contentTree : mgr.assetsTree}
								activePath={mgr.activePath}
								root={mgr.treeRoot}
								onselect={handleSelect}
								oncreate={mgr.treeRoot === 'content' ? (type, parentPath) => type === 'file' ? handleCreateFile(parentPath) : handleCreateFolder(parentPath) : undefined}
								onrename={handleRename}
								ondelete={handleDelete}
							/>
						{/if}
					</div>
				</div>

				<!-- Code Editor -->
				<div class="code-panel">
					{#if mgr.activePath}
						<CodeEditor
							bind:this={editorRef}
							code={mgr.body}
							language="markdown"
							onchange={handleEditorChange}
						/>
					{:else}
						<div class="code-empty">
							<p>Pilih file dari tree untuk mulai mengedit.</p>
						</div>
					{/if}
				</div>
			</div>

			<!-- Status bar -->
			{#if mgr.lastMessage}
				<div class="status-bar" class:success={mgr.lastMessage.type === 'success'} class:error={mgr.lastMessage.type === 'error'}>
					{mgr.lastMessage.text}
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.content-editor-layout {
		display: grid;
		grid-template-columns: 1fr 1.2fr;
		gap: 1rem;
		align-items: start;
		min-height: calc(100vh - 4rem);
		padding: 1rem;
	}

	.content-editor-layout.single-col {
		grid-template-columns: 1fr;
	}

	.access-denied {
		text-align: center;
		padding: 4rem 2rem;
		color: var(--color-text-muted);
	}

	/* Preview Panel */
	.preview-panel {
		overflow-y: auto;
		max-height: 90vh;
		padding: 1rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
	}
	.preview-panel.full-width {
		max-height: none;
	}
	.preview-loading, .preview-empty {
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 200px;
		color: var(--color-text-muted);
	}
	.preview-error {
		padding: 1rem;
		background: #fff5f5;
		border: 1px solid #ffc9c9;
		border-radius: var(--radius);
		color: #c92a2a;
	}

	/* Editor Area */
	.editor-area {
		position: sticky;
		top: 3.5rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
		display: flex;
		flex-direction: column;
		overflow: hidden;
		height: 70vh;
	}

	.editor-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.5rem 1rem;
		border-bottom: 1px solid var(--color-border);
		background: var(--color-bg-secondary);
	}
	.editor-filename {
		font-weight: 600;
		font-size: 0.9rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		flex: 1;
	}
	.editor-actions {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}

	.editor-body {
		flex: 1;
		display: flex;
		overflow: hidden;
		min-height: 0;
	}

	/* Tree Panel */
	.tree-panel {
		width: 220px;
		min-width: 180px;
		border-right: 1px solid var(--color-border);
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}
	.tree-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.4rem 0.5rem;
		border-bottom: 1px solid var(--color-border);
		background: var(--color-bg-secondary);
	}
	.tree-tabs {
		display: flex;
		gap: 0;
	}
	.tree-tab {
		padding: 4px 10px;
		font-size: 0.75rem;
		font-weight: 600;
		border: 1px solid var(--color-border);
		background: var(--color-bg);
		cursor: pointer;
		transition: all 0.15s;
	}
	.tree-tab:first-child {
		border-radius: 4px 0 0 4px;
	}
	.tree-tab:last-child {
		border-radius: 0 4px 4px 0;
		border-left: none;
	}
	.tree-tab.active {
		background: var(--color-primary, #339af0);
		color: white;
		border-color: var(--color-primary, #339af0);
	}
	.tree-actions-header {
		display: flex;
		gap: 2px;
	}
	.action-btn-sm {
		background: none;
		border: none;
		cursor: pointer;
		padding: 2px 4px;
		font-size: 0.75rem;
		border-radius: 4px;
		transition: background 0.15s;
	}
	.action-btn-sm:hover {
		background: var(--color-border, #ddd);
	}
	.tree-content {
		flex: 1;
		overflow-y: auto;
	}
	.tree-loading {
		padding: 1rem;
		text-align: center;
		color: var(--color-text-muted);
		font-size: 0.8rem;
	}

	/* Code Panel */
	.code-panel {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		min-width: 0;
	}
	.code-empty {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
		color: var(--color-text-muted);
	}

	/* Status Bar */
	.status-bar {
		padding: 0.4rem 1rem;
		font-size: 0.8rem;
		font-weight: 500;
		text-align: center;
		border-top: 1px solid var(--color-border);
	}
	.status-bar.success {
		background: #ebfbee;
		color: #2b8a3e;
	}
	.status-bar.error {
		background: #fff5f5;
		color: #c92a2a;
	}

	/* Mobile modes (reuse lesson.css patterns) */
	.editor-area.mobile-sheet {
		position: fixed;
		top: auto;
		bottom: 0;
		left: 0;
		right: 0;
		z-index: 9999;
		background: var(--color-bg);
		border-top: 2px solid var(--color-primary);
		border-radius: 12px 12px 0 0;
		box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
		display: flex;
		flex-direction: column;
		overflow-y: auto;
		overflow-x: hidden;
		transition: height 0.3s cubic-bezier(0.4, 0, 0.2, 1), border-radius 0.2s ease;
	}
	.editor-area.mobile-hidden { height: 52px; }
	.editor-area.mobile-h30 { height: 30vh; }
	.editor-area.mobile-h50 { height: 50vh; }
	.editor-area.mobile-h70 { height: 70vh; }
	.editor-area.mobile-full { height: 100dvh; border-radius: 0; max-height: none; }

	/* Floating mode */
	.editor-area.floating {
		position: fixed;
		bottom: 1rem;
		right: 1rem;
		top: auto;
		width: 45vw;
		height: 70vh;
		min-width: 320px;
		max-width: 100vw;
		max-height: 100vh;
		z-index: 9999;
	}
	.editor-area.floating-hidden { display: none !important; }

	.float-restore-btn {
		position: fixed;
		bottom: 1rem;
		right: 1rem;
		z-index: 9999;
		background: var(--color-primary);
		color: #fff;
		border: none;
		border-radius: var(--radius);
		padding: 0.6rem 1rem;
		font-size: 0.85rem;
		font-weight: 600;
		cursor: pointer;
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
	}

	/* Buttons */
	.btn {
		padding: 0.3rem 0.75rem;
		font-size: 0.8rem;
		border-radius: var(--radius);
		cursor: pointer;
		text-decoration: none;
		transition: all 0.15s;
		border: 1px solid transparent;
	}
	.btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}
	.btn-sm { padding: 0.25rem 0.6rem; font-size: 0.75rem; }
	.btn-secondary {
		background: var(--color-bg);
		border-color: var(--color-border);
		color: var(--color-text);
	}
	.btn-secondary:hover:not(:disabled) {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}
	.btn-primary {
		background: var(--color-primary);
		color: #fff;
		border-color: var(--color-primary);
	}
	.btn-primary:hover:not(:disabled) {
		opacity: 0.9;
	}

	@media (max-width: 768px) {
		.content-editor-layout {
			grid-template-columns: 1fr;
			padding: 0;
		}
		.tree-panel {
			display: none;
		}
	}
</style>
