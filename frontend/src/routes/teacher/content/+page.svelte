<script lang="ts">
	import { onMount } from 'svelte';
	import { authIsTeacher } from '$stores/auth';
	import { createFloatingPanel } from '$actions/floatingPanel.svelte';
	import CodeEditor from '$components/CodeEditor.svelte';
	import CircuitEditor from '$components/CircuitEditor.svelte';
	import ContentFileTree from '$components/ContentFileTree.svelte';
	import LessonContentView from '$components/LessonContentView.svelte';
	import QuizPreviewReadonly from '$components/QuizPreviewReadonly.svelte';
	import { ContentEditorManager } from '$services/contentEditor.svelte';
	import { getTree, createFolder, createFile, renameEntry, deleteEntry, uploadAsset } from '$services/contentEditor';
	import type { TreeNode } from '$services/contentEditor';

	const mgr = new ContentEditorManager();
	const float = createFloatingPanel();

	let editorRef = $state<any>(null);
	let circuitEditorRef = $state<any>(null);

	// Mobile: show tree or editor
	let mobileShowTree = $state(true);

	// Load trees on mount
	onMount(async () => {
		await loadTrees();
	});

	// When mobile & no file selected, default to tree view
	$effect(() => {
		if (mgr.isMobile && !mgr.activePath) {
			mobileShowTree = true;
		}
	});

	// Mobile behavior for floating panel
	$effect(() => {
		if (mgr.isMobile) {
			float.floating = false;
			float.minimized = false;
		}
	});

	// Available tabs based on preview data
	let hasExercise = $derived(!!mgr.previewExerciseHtml);
	let hasQuiz = $derived(mgr.previewQuizData.length > 0);

	// Dynamic tabs from previewActiveTabs (e.g. 'c', 'python', 'circuit', 'velxio', 'flowchart')
	type DynamicTab = { id: string; label: string; show?: boolean };
	const TAB_LABELS: Record<string, string> = {
		c: 'C',
		python: 'Python',
		circuit: 'Circuit',
		velxio: 'Arduino',
		flowchart: 'Flowchart',
	};
	let dynamicTabs = $derived(
		(mgr.previewActiveTabs ?? [])
			.filter((t) => !['quiz'].includes(t)) // quiz handled separately
			.map((t): DynamicTab => ({ id: t, label: TAB_LABELS[t] ?? t }))
	);

	// Extract code blocks from raw markdown body for dynamic tabs
	function extractCode(body: string, marker: string): string {
		const startTag = `---${marker}---`;
		const endTag = `---END_${marker}---`;
		const startIdx = body.indexOf(startTag);
		if (startIdx === -1) return '';
		const codeStart = startIdx + startTag.length;
		const endIdx = body.indexOf(endTag, codeStart);
		if (endIdx === -1) return body.substring(codeStart).trim();
		return body.substring(codeStart, endIdx).trim();
	}

	let extractedCodes = $derived((() => {
		const codes: Record<string, string> = {};
		for (const tab of dynamicTabs) {
			if (tab.id === 'c') codes.c = extractCode(mgr.body, 'INITIAL_CODE');
			else if (tab.id === 'python') codes.python = extractCode(mgr.body, 'INITIAL_PYTHON');
			else if (tab.id === 'circuit') codes.circuit = extractCode(mgr.body, 'INITIAL_CIRCUIT');
			else if (tab.id === 'velxio') codes.velxio = extractCode(mgr.body, 'INITIAL_CODE_ARDUINO');
			else if (tab.id === 'flowchart') codes.flowchart = extractCode(mgr.body, 'INITIAL_FLOWCHART');
		}
		return codes;
	})());

	// Tab label map for chrome tabs
	let allTabs = $derived([
		{ id: 'editor', label: 'Editor' },
		...dynamicTabs,
		{ id: 'exercise', label: 'Exercise', show: hasExercise },
		{ id: 'quiz', label: 'Quiz', show: hasQuiz },
	].filter((t) => t.show !== false));

	// Auto-switch to editor tab when switching files
	$effect(() => {
		if (mgr.activePath) {
			mgr.activeTab = 'editor';
		}
	});

	// Auto-switch away from a tab that's no longer available
	$effect(() => {
		const validIds = allTabs.map((t) => t.id);
		if (!validIds.includes(mgr.activeTab)) {
			mgr.activeTab = 'editor';
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
		if (mgr.treeRoot === 'assets') {
			// Asset file: load for preview only, don't go through draft system
			mgr.activePath = path;
			mgr.body = '';
			mgr.draftId = null;
			mgr.dirty = false;
			// Clear preview since assets don't have markdown
			mgr.previewHtml = '';
			mgr.previewExerciseHtml = '';
			mgr.previewQuizData = [];
			mgr.previewSlides = [];
			mgr.previewActiveTabs = [];
			mgr.previewError = null;
			mgr.activeTab = 'editor';
		} else {
			mgr.loadDraft(path);
		}
		if (mgr.isMobile) {
			mobileShowTree = false;
			mgr.mobileMode = 'h50';
		}
	}

	function handleMobileBackToTree() {
		if (mgr.dirty && !window.confirm('Ada perubahan yang belum disimpan. Kembali ke tree?')) {
			return;
		}
		mobileShowTree = true;
	}

	function handleEditorChange(value: string) {
		mgr.onBodyChange(value);
	}

	function handleEditorMount() {
		if (editorRef && mgr.body) {
			editorRef.setCode(mgr.body);
		}
	}

	function handleTabClick(tab: string) {
		mgr.activeTab = tab;
		if (mgr.isMobile && mgr.mobileMode === 'hidden') {
			mgr.mobileMode = 'h50';
		}
	}

	// ── Feature template sidebar ──────────────────────────────────────
	// Insert a feature section template at the editor cursor. Works in all
	// layout modes (desktop docked, floating, mobile). Shown in a hide-able
	// right sidebar grouped into "Konten" and "Penilaian".
	type FeatureTemplate = { id: string; label: string; group: 'konten' | 'penilaian'; snippet: string };

	let featureSidebarOpen = $state(true);
	let featureSidebarNarrow = $state(false);

	// Desktop: panel fitur terbuka by default. Mobile: default tersembunyi (drawer).
	$effect(() => {
		if (mgr.isMobile) featureSidebarOpen = false;
	});

	const FEATURE_TEMPLATES: FeatureTemplate[] = [
		// ── Konten ──
		{
			id: 'info',
			label: 'Info',
			group: 'konten',
			snippet:
				'---LESSON_INFO---\n' +
				'**Learning Objectives:**\n- \n\n' +
				'**Prerequisites:**\n- \n' +
				'---END_LESSON_INFO---\n',
		},
		{
			id: 'c',
			label: 'C',
			group: 'konten',
			snippet:
				'\n---INITIAL_CODE---\n' +
				'#include <stdio.h>\n\nint main() {\n    \n    return 0;\n}\n' +
				'---END_INITIAL_CODE---\n',
		},
		{
			id: 'python',
			label: 'Python',
			group: 'konten',
			snippet:
				'\n---INITIAL_PYTHON---\n' +
				'# Tulis kode Python di sini\n' +
				'---END_INITIAL_PYTHON---\n',
		},
		{
			id: 'circuit',
			label: 'Circuit Tab',
			group: 'konten',
			snippet:
				'\n---INITIAL_CIRCUIT---\n' +
				'<cir f="1" ts="0.000005" ic="10.20027730826997" cb="50" pb="50" vr="5" mts="5e-11">\n' +
				'  <v x="80 200 80 112" f="0" wf="0" maxv="5"/>\n' +
				'  <r x="80 112 176 112" f="0" r="1000"/>\n' +
				'  <w x="176 200 80 200" f="0"/>\n' +
				'</cir>\n' +
				'---END_INITIAL_CIRCUIT---\n',
		},
		{
			id: 'arduino',
			label: 'Arduino',
			group: 'konten',
			snippet:
				'\n---INITIAL_CODE_ARDUINO---\n' +
				'void setup() {\n  \n}\n\n' +
				'void loop() {\n  \n}\n' +
				'---END_INITIAL_CODE_ARDUINO---\n',
		},
		{
			id: 'velxio-circuit',
			label: 'Velxio',
			group: 'konten',
			snippet:
				'\n---VELXIO_CIRCUIT---\n' +
				'{\n  "board": "arduino:avr:uno",\n  "components": [],\n  "wires": []\n}\n' +
				'---END_VELXIO_CIRCUIT---\n',
		},
		{
			id: 'flowchart',
			label: 'Flowchart Tab',
			group: 'konten',
			snippet:
				'\n---INITIAL_FLOWCHART---\n' +
				'start[roundrect] "Mulai"\n' +
				'init[rect] "Inisialisasi"\n' +
				'start --> init\n' +
				'---END_INITIAL_FLOWCHART---\n',
		},
		{
			id: 'quiz',
			label: 'Quiz',
			group: 'konten',
			snippet:
				'\n---QUIZ_FLASHCARD---\n' +
				'### Pertanyaan contoh?\n' +
				'- [] Pilihan A\n- [x] Pilihan B\n' +
				'> Penjelasan: tulis penjelasan di sini.\n' +
				'---END_QUIZ_FLASHCARD---\n',
		},
		{
			id: 'exercise',
			label: 'Exercise',
			group: 'konten',
			snippet:
				'\n---EXERCISE---\n' +
				'### Tantangan\n' +
				'Tulis deskripsi latihan di sini.\n' +
				'---\n',
		},
		{
			id: 'slide',
			label: 'Slide',
			group: 'konten',
			snippet:
				'\n---slide-start---\n' +
				'# Judul Slide 1\nTulis konten slide pertama di sini.\n\n' +
				'```embed\n<iframe src="https://www.canva.com/design/XXXX/view?embed"></iframe>\n```\n' +
				'---\n' +
				'# Judul Slide 2\nTulis konten slide kedua.\n' +
				'---slide-end---\n',
		},
		{
			id: 'circuit-inline',
			label: 'Circuit',
			group: 'konten',
			snippet:
				'\n```circuit\n' +
				'<cir f="1" ts="0.000005" ic="10.20027730826997" cb="50" pb="50" vr="5" mts="5e-11">\n' +
				'  <v x="80 200 80 112" f="0" wf="0" maxv="5"/>\n' +
				'  <r x="80 112 176 112" f="0" r="1000"/>\n' +
				'  <w x="176 200 80 200" f="0"/>\n' +
				'</cir>\n' +
				'```\n',
		},
		{
			id: 'flowchart-inline',
			label: 'Flowchart',
			group: 'konten',
			snippet:
				'\n```flowchart,100%,300px\n' +
				'start[roundrect] "Mulai"\n' +
				'init[rect] "Inisialisasi"\n' +
				'start --> init\n' +
				'```\n',
		},
		{
			id: 'embed',
			label: 'Embed',
			group: 'konten',
			snippet:
				'\n```embed\n' +
				'<div style="position: relative; width: 100%; height: 0; padding-top: 56.25%; overflow: hidden; border-radius: 8px;">\n' +
				'  <iframe loading="lazy" style="position: absolute; inset: 0; width: 100%; height: 100%; border: none;" src="https://www.canva.com/design/XXXX/view?embed" allowfullscreen="allowfullscreen" allow="fullscreen"></iframe>\n' +
				'</div>\n' +
				'```\n',
		},
		// ── Penilaian ──
		{
			id: 'expected-c',
			label: 'Exp C',
			group: 'penilaian',
			snippet:
				'\n---EXPECTED_OUTPUT---\n' +
				'Output yang diharapkan\n' +
				'---END_EXPECTED_OUTPUT---\n',
		},
		{
			id: 'expected-py',
			label: 'Exp Py',
			group: 'penilaian',
			snippet:
				'\n---EXPECTED_OUTPUT_PYTHON---\n' +
				'Output yang diharapkan\n' +
				'---END_EXPECTED_OUTPUT_PYTHON---\n',
		},
		{
			id: 'expected-circuit',
			label: 'Exp Circuit',
			group: 'penilaian',
			snippet:
				'\n---EXPECTED_CIRCUIT_OUTPUT---\n' +
				'{\n  "nodes": {\n    "Vout": { "voltage": 2.5, "tolerance": 0.2 }\n  }\n}\n' +
				'---END_EXPECTED_CIRCUIT_OUTPUT---\n',
		},
		{
			id: 'expected-serial',
			label: 'Exp Serial',
			group: 'penilaian',
			snippet:
				'\n---EXPECTED_SERIAL_OUTPUT---\n' +
				'LED ON\nLED OFF\n' +
				'---END_EXPECTED_SERIAL_OUTPUT---\n',
		},
		{
			id: 'expected-flowchart',
			label: 'Exp Flow',
			group: 'penilaian',
			snippet:
				'\n---EXPECTED_FLOWCHART---\n' +
				'start[roundrect] "mulai"\ninit[rect] "inisialisasi"\nstart --> init\n' +
				'---END_EXPECTED_FLOWCHART---\n',
		},
		{
			id: 'solution-c',
			label: 'Sol C',
			group: 'penilaian',
			snippet:
				'\n---SOLUTION_CODE---\n' +
				'#include <stdio.h>\n\nint main() {\n    \n    return 0;\n}\n' +
				'---END_SOLUTION_CODE---\n',
		},
		{
			id: 'solution-py',
			label: 'Sol Py',
			group: 'penilaian',
			snippet:
				'\n---SOLUTION_PYTHON---\n' +
				'# Solusi Python\n' +
				'---END_SOLUTION_PYTHON---\n',
		},
		{
			id: 'solution-circuit',
			label: 'Sol Circuit',
			group: 'penilaian',
			snippet:
				'\n---SOLUTION_CIRCUIT---\n' +
				'<cir f="1" ts="0.000005" ic="10.20027730826997" cb="50" pb="50" vr="5" mts="5e-11">\n' +
				'  <v x="80 200 80 112" f="0" wf="0" maxv="5"/>\n' +
				'  <r x="80 112 176 112" f="0" r="1000"/>\n' +
				'  <w x="176 200 80 200" f="0"/>\n' +
				'</cir>\n' +
				'---END_SOLUTION_CIRCUIT---\n',
		},
		{
			id: 'key-text',
			label: 'Key Text',
			group: 'penilaian',
			snippet:
				'\n---KEY_TEXT---\n' +
				'kata_kunci1\nkata_kunci2\n' +
				'---END_KEY_TEXT---\n',
		},
		{
			id: 'key-text-circuit',
			label: 'Key Circuit',
			group: 'penilaian',
			snippet:
				'\n---KEY_TEXT_CIRCUIT---\n' +
				'Vout\n' +
				'---END_KEY_TEXT_CIRCUIT---\n',
		},
	];

	function insertTemplate(tpl: FeatureTemplate) {
		if (!mgr.activePath || isAssetFile) return;
		editorRef?.insertAtCursor(tpl.snippet);
		// Ensure editor tab is visible so the user sees the insertion
		mgr.activeTab = 'editor';
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
			if (mgr.isMobile) {
				mobileShowTree = false;
			}
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
				mgr.previewSlides = [];
				mgr.previewActiveTabs = [];
				if (mgr.isMobile) mobileShowTree = true;
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
						if (mgr.isMobile) mobileShowTree = true;
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

	function handleCopyAssetPath() {
		const path = mgr.activePath;
		if (!path) return;
		navigator.clipboard.writeText(`/assets/${path}`);
		const toast = document.createElement('div');
		toast.textContent = 'Path disalin ke clipboard';
		toast.style.cssText = 'position:fixed;bottom:1rem;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:6px 16px;border-radius:8px;font-size:0.8rem;z-index:10000;';
		document.body.appendChild(toast);
		setTimeout(() => toast.remove(), 1500);
	}

	let activeFileName = $derived(mgr.activePath?.split('/').pop() ?? '');
	let isAssetFile = $derived(mgr.treeRoot === 'assets' && mgr.activePath !== null && !mgr.activePath.endsWith('/'));
	let isImageFile = $derived(isAssetFile && /\.(png|jpe?g|gif|webp|svg|bmp|ico)$/i.test(mgr.activePath ?? ''));
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
	<div class="content-editor-layout"
		class:single-col={float.floating || mgr.isMobile}
		class:has-floating={float.floating && !mgr.isMobile}
	>
		<!-- Preview Panel (always behind editor) -->
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
			{:else if isImageFile && mgr.activePath}
				<div class="preview-asset">
					<img src="/assets/{mgr.activePath}" alt={activeFileName} style="max-width:100%;border-radius:var(--radius);" loading="lazy" />
					<p class="preview-asset-meta">/assets/{mgr.activePath}</p>
				</div>
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
			<!-- Save / Publish actions (shared across all header modes) -->
		{#snippet saveActions()}
			{#if mgr.activePath && !isAssetFile}
				<button class="panel-btn toolbar-toggle" class:active={featureSidebarOpen} onclick={() => featureSidebarOpen = !featureSidebarOpen} title="Tampilkan/sembunyikan panel Fitur">🧩</button>
				<button class="panel-btn save-btn" onclick={() => mgr.handleSave()} disabled={mgr.saving || !mgr.dirty} title="Simpan">
					{mgr.saving ? '⏳' : '💾'}
				</button>
				<button class="panel-btn publish-btn" onclick={() => mgr.handlePublish()} disabled={mgr.publishing || !mgr.draftId} title="Publish">
					{mgr.publishing ? '⏳' : '🚀'}
				</button>
			{/if}
		{/snippet}

		<!-- Panel Header (floating drag handle) -->
			{#if float.floating && !mgr.isMobile}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="panel-header draggable" onmousedown={float.onDragStart} ontouchstart={float.onTouchDragStart}>
					<span class="resize-handle" onmousedown={(e) => { e.stopPropagation(); float.onResizeStart(e); }} ontouchstart={float.onTouchResizeStart}>&#x25F3;</span>
					<div class="chrome-tabs">
						{#each allTabs as tab}
							<button class="chrome-tab" class:active={mgr.activeTab === tab.id} onclick={() => handleTabClick(tab.id)}>{tab.label}</button>
						{/each}
					</div>
					<div class="panel-actions">
						{@render saveActions()}
						<button class="panel-btn" title="Minimize" onclick={float.minimize}>▽</button>
						<button class="panel-btn" title="Kembali ke dock (inline)" onclick={float.toggle}>&#x229E;</button>
					</div>
				</div>
			{:else if mgr.isMobile}
				<!-- Mobile: panel header with tabs + swipe -->
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="panel-header" ontouchstart={(e) => { /* future swipe support */ }}>
					{#if !mobileShowTree && mgr.activePath}
						<button class="panel-btn mobile-back-btn" onclick={handleMobileBackToTree} title="Kembali ke tree">◀</button>
					{/if}
					<div class="chrome-tabs">
						{#if !mobileShowTree}
							{#each allTabs as tab}
								<button class="chrome-tab" class:active={mgr.activeTab === tab.id} onclick={() => handleTabClick(tab.id)}>{tab.label}</button>
							{/each}
						{:else}
							<span class="chrome-tab active">File Tree</span>
						{/if}
					</div>
					<div class="panel-actions">
						{@render saveActions()}
						<button class="panel-btn" onclick={() => { if (mgr.mobileMode !== 'hidden') mgr.mobileMode = mgr.mobileMode === 'full' ? 'h50' : 'hidden'; else mgr.mobileMode = 'h50'; }} title="Minimize" disabled={mgr.mobileMode === 'hidden'}>▽</button>
						<button class="panel-btn" onclick={() => { if (mgr.mobileMode !== 'full') mgr.mobileMode = mgr.mobileMode === 'hidden' ? 'h50' : 'full'; else mgr.mobileMode = 'h50'; }} title="Maximize" disabled={mgr.mobileMode === 'full'}>△</button>
					</div>
				</div>
			{:else}
				<!-- Desktop: panel header with tabs + actions -->
				<div class="panel-header">
					{#if mgr.activePath && !isAssetFile}
						<button class="panel-btn mobile-back-btn" onclick={handleMobileBackToTree} title="Kembali ke tree">◀</button>
					{/if}
					<div class="chrome-tabs">
						{#if mgr.activePath}
							{#each allTabs as tab}
								<button class="chrome-tab" class:active={mgr.activeTab === tab.id} onclick={() => handleTabClick(tab.id)}>{tab.label}</button>
							{/each}
						{/if}
					</div>
					<div class="panel-actions">
						{@render saveActions()}
						<button type="button" class="btn-float-toggle" onclick={float.toggle} title={float.floating ? 'Dock ke layout' : 'Float (detach)'}>
							&#x229E;
						</button>
					</div>
				</div>
				{/if}

				<!-- Editor main: tab panels + feature sidebar -->
			<div class="editor-main">
			<div class="editor-body">
				{#if mgr.isMobile && mobileShowTree}
					<!-- MOBILE: Show full-width tree -->
					<div class="tree-panel mobile-tree-full">
						<div class="tree-header">
							<div class="tree-tabs">
								<button class="tree-tab" class:active={mgr.treeRoot === 'content'} onclick={() => mgr.treeRoot = 'content'}>Materi</button>
								<button class="tree-tab" class:active={mgr.treeRoot === 'assets'} onclick={() => mgr.treeRoot = 'assets'}>Assets</button>
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
				{:else}
					<!-- DESKTOP or MOBILE: Tree + Tab panels side by side -->
					<!-- File Tree -->
					<div class="tree-panel" class:mobile-tree-hidden={mgr.isMobile}>
						<div class="tree-header">
							<div class="tree-tabs">
								<button class="tree-tab" class:active={mgr.treeRoot === 'content'} onclick={() => mgr.treeRoot = 'content'}>Materi</button>
								<button class="tree-tab" class:active={mgr.treeRoot === 'assets'} onclick={() => mgr.treeRoot = 'assets'}>Assets</button>
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

					<!-- Tab Panels -->
					<div class="tab-panels">
						<!-- Editor Tab -->
						<div class="tab-panel" class:tab-hidden={mgr.activeTab !== 'editor'}>
							{#if mgr.activePath}
								{#if isImageFile}
									<div class="asset-preview">
										<div class="asset-preview-image">
											<img src="/assets/{mgr.activePath}" alt={activeFileName} loading="lazy" />
										</div>
										<div class="asset-preview-info">
											<span class="asset-name">{activeFileName}</span>
											<span class="asset-path">/assets/{mgr.activePath}</span>
											<div class="asset-actions">
												<button class="panel-btn" onclick={handleCopyAssetPath}>📋 Salin Path</button>
											</div>
										</div>
									</div>
								{:else}
									<div class="code-tab-content">
										<CodeEditor
											bind:this={editorRef}
											code={mgr.body}
											language="markdown"
											onchange={handleEditorChange}
										/>
									</div>
								{/if}
							{:else}
								<div class="tab-empty">
									<p>Pilih file dari tree untuk mulai mengedit.</p>
								</div>
							{/if}
						</div>

						<!-- Exercise Tab -->
						<div class="tab-panel" class:tab-hidden={mgr.activeTab !== 'exercise'}>
							{#if mgr.previewExerciseHtml}
								<div class="tab-content prose">
									<h2 class="tab-heading">Latihan</h2>
									{@html mgr.previewExerciseHtml}
								</div>
							{:else}
								<div class="tab-empty">
									<p>Tidak ada exercise untuk file ini.</p>
								</div>
							{/if}
						</div>

						<!-- Quiz Tab -->
						<div class="tab-panel" class:tab-hidden={mgr.activeTab !== 'quiz'}>
							{#if mgr.previewQuizData.length > 0}
								<QuizPreviewReadonly quizData={mgr.previewQuizData as any} />
							{:else}
								<div class="tab-empty">
									<p>Tidak ada quiz untuk file ini.</p>
								</div>
							{/if}
						</div>

						<!-- Dynamic tabs (C, Python, Circuit, Velxio, Flowchart) -->
						{#each dynamicTabs as dynTab}
							<div class="tab-panel" class:tab-hidden={mgr.activeTab !== dynTab.id}>
								{#if dynTab.id === 'circuit'}
									<div class="circuit-tab-content">
										{#if extractedCodes.circuit}
										<CircuitEditor
											bind:this={circuitEditorRef}
											initialCircuit={extractedCodes.circuit}
										/>
									{:else}
										<div class="tab-empty"><p>Belum ada data circuit.</p></div>
									{/if}
								</div>
								{:else if dynTab.id === 'velxio'}
									<div class="velxio-tab-content">
										<iframe
											class="velxio-iframe"
											src="/velxio/editor?embed=true&hideEditor=true&lockComponents=true"
											allow="cross-origin-isolated; fullscreen"
											allowfullscreen
										></iframe>
									</div>
								{:else if dynTab.id === 'flowchart'}
									<div class="flowchart-tab-content">
										<iframe
											class="flowchart-iframe"
											src="/flowchart/?iframe=true"
											title="Flowchart Editor"
										></iframe>
									</div>
								{:else if extractedCodes[dynTab.id]}
									<div class="code-tab-content">
										<CodeEditor
											code={extractedCodes[dynTab.id]}
											language={dynTab.id === 'c' ? 'c' : dynTab.id === 'python' ? 'python' : 'plaintext'}
											onchange={() => {}}
									/>
									</div>
								{:else}
									<div class="tab-empty">
										<p>Belum ada konten {dynTab.label}.</p>
									</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Feature sidebar (right, hide-able) -->
			{#if featureSidebarOpen && mgr.activePath && !isAssetFile}
				<aside class="feature-sidebar" class:mobile-drawer={mgr.isMobile} class:narrow={featureSidebarNarrow}>
					<div class="feature-sidebar-header">
						<span>Fitur</span>
					</div>
					<div class="feature-sidebar-body">
						<div class="feature-group-label">Konten</div>
						{#each FEATURE_TEMPLATES.filter((t) => t.group === 'konten') as tpl}
							<button class="feature-btn" title={"Sisipkan template " + tpl.label} onclick={() => insertTemplate(tpl)}>
								{tpl.label}
							</button>
						{/each}
						<div class="feature-group-label">Penilaian</div>
						{#each FEATURE_TEMPLATES.filter((t) => t.group === 'penilaian') as tpl}
							<button class="feature-btn" title={"Sisipkan template " + tpl.label} onclick={() => insertTemplate(tpl)}>
								{tpl.label}
							</button>
						{/each}
					</div>
				</aside>
			{/if}
			</div>

			<!-- Status bar -->
			{#if mgr.lastMessage}
				<div class="status-bar" class:success={mgr.lastMessage.type === 'success'} class:error={mgr.lastMessage.type === 'error'}>
					{mgr.lastMessage.text}
				</div>
			{/if}

			<!-- Resize handle (floating mode) -->
			{#if float.floating && !mgr.isMobile && !float.minimized}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="resize-handle" onmousedown={float.onResizeStart} ontouchstart={float.onTouchResizeStart}>&#x25F3;</div>
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

	.content-editor-layout.has-floating .preview-panel {
		grid-column: 1 / -1;
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
	.preview-asset {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 1rem;
	}
	.preview-asset-meta {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		word-break: break-all;
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

	/* Panel header (shared with WorkspaceHeader) */
	.panel-header {
		display: flex;
		align-items: flex-end;
		gap: 0.25rem;
		padding: 4px 8px 0;
		background: var(--color-bg-secondary);
		border-bottom: 1px solid var(--color-border);
		user-select: none;
		cursor: default;
		min-height: 36px;
		flex-shrink: 0;
	}
	.panel-header.draggable { cursor: grab; }
	.panel-header.draggable:active { cursor: grabbing; }
	.panel-actions {
		display: flex;
		gap: 0.25rem;
		align-self: center;
	}
	.panel-btn {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 4px;
		padding: 0.15rem 0.5rem;
		cursor: pointer;
		font-size: 0.8rem;
		color: var(--color-text);
		line-height: 1;
	}
	.panel-btn:hover { background: var(--color-border); }
	.panel-btn:disabled { opacity: 0.45; cursor: not-allowed; }
	.panel-btn.save-btn { color: var(--color-text-muted); }
	.panel-btn.publish-btn { color: var(--color-primary, #339af0); font-weight: 600; }

	/* Editor main: tab panels (left) + feature sidebar (right) */
	.editor-main {
		display: flex;
		flex: 1;
		min-height: 0;
		overflow: hidden;
	}
	.feature-btn {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 4px;
		padding: 0.35rem 0.6rem;
		cursor: pointer;
		font-size: 0.78rem;
		color: var(--color-text);
		line-height: 1;
		white-space: nowrap;
		width: 100%;
		text-align: left;
	}
	.feature-btn:hover:not(:disabled) { background: var(--color-border); }
	.feature-btn:disabled { opacity: 0.45; cursor: not-allowed; }

	/* Right feature sidebar */
	.feature-sidebar {
		width: 20%;
		min-width: 150px;
		max-width: 300px;
		flex-shrink: 0;
		background: var(--color-bg-secondary);
		border-left: 1px solid var(--color-border);
		display: flex;
		flex-direction: column;
		min-height: 0;
	}
	.feature-sidebar.narrow {
		width: 10%;
		min-width: 64px;
		max-width: 160px;
	}
	.feature-sidebar.narrow .feature-btn {
		font-size: 0.62rem;
		padding: 0.3rem 0.2rem;
		text-align: center;
	}
	.feature-sidebar.narrow .feature-group-label { display: none; }
	.feature-sidebar-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px 8px;
		font-size: 0.78rem;
		font-weight: 600;
		color: var(--color-text-muted);
		border-bottom: 1px solid var(--color-border);
		flex-shrink: 0;
	}
	.feature-sidebar-body {
		padding: 8px;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		overflow-y: auto;
	}
	.feature-group-label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--color-text-muted);
		margin-top: 0.5rem;
		margin-bottom: 0.1rem;
	}
	.feature-group-label:first-child { margin-top: 0; }

	/* Toolbar Fitur toggle (icon, highlighted when sidebar open) */
	.toolbar-toggle {
		font-size: 0.95rem;
		line-height: 1;
		padding: 0.2rem 0.5rem;
	}
	.toolbar-toggle.active {
		background: var(--color-border);
		color: var(--color-text);
	}

	/* Mobile: same 20% inline sidebar as desktop (no drawer overlay) */
	@media (max-width: 768px) {
		.feature-sidebar.mobile-drawer {
			position: static;
			top: auto;
			right: auto;
			bottom: auto;
			width: 30%;
			min-width: 70px;
			max-width: 200px;
			z-index: auto;
			box-shadow: none;
		}
	}
	.panel-title {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--color-text-muted);
		flex: 1;
		line-height: 1.8;
	}
	.btn-float-toggle {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 4px;
		padding: 0.2rem 0.5rem;
		cursor: pointer;
		font-size: 0.95rem;
		color: var(--color-text-muted);
		line-height: 1;
		align-self: center;
	}
	.btn-float-toggle:hover {
		background: var(--color-bg-secondary);
		color: var(--color-text);
	}

	/* ── Chrome-style tabs (reuse from WorkspaceHeader) ── */
	.chrome-tabs {
		display: flex;
		align-items: flex-end;
		gap: 2px;
		flex: 1;
		min-width: 0;
		overflow-x: auto;
		scrollbar-width: none;
		-webkit-overflow-scrolling: touch;
	}
	.chrome-tabs::-webkit-scrollbar { display: none; }

	.chrome-tab {
		position: relative;
		padding: 5px 12px;
		border: 1px solid transparent;
		border-bottom: none;
		border-radius: 8px 8px 0 0;
		background: transparent;
		color: var(--color-text-muted);
		font-size: 0.78rem;
		font-weight: 500;
		cursor: pointer;
		white-space: nowrap;
		flex-shrink: 0;
		margin-bottom: -1px;
		z-index: 0;
		transition: background 0.15s, color 0.15s;
	}
	.chrome-tab:hover:not(.active) {
		background: var(--color-border);
		color: var(--color-text);
	}
	.chrome-tab.active {
		background: var(--color-bg);
		color: var(--color-text);
		font-weight: 600;
		border-color: var(--color-border);
		z-index: 1;
	}

	/* Tab Panels */
	.tab-panels {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		min-height: 0;
	}
	.tab-panel {
		flex: 1;
		overflow-y: auto;
		min-height: 0;
	}
	.tab-panel.tab-hidden {
		display: none;
	}
	.tab-content {
		padding: 1rem;
	}
	.tab-heading {
		font-size: 1.1rem;
		font-weight: 700;
		margin-bottom: 0.75rem;
		color: var(--color-text);
	}
	.tab-empty {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
		min-height: 200px;
		color: var(--color-text-muted);
		text-align: center;
		padding: 1rem;
	}

	/* Code tab content fills available space */
	.code-tab-content {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		min-height: 0;
	}

	.editor-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.5rem 1rem;
		border-bottom: 1px solid var(--color-border);
		background: var(--color-bg-secondary);
		flex-shrink: 0;
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

	/* Code Panel (legacy, kept for reference) */
	.code-panel {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		min-width: 0;
	}
	/* Force CodeEditor to fill its parent container */
	.code-panel :global(.editor-wrapper) {
		flex: 1;
		min-height: 0;
	}
	.code-panel :global(.cm-editor) {
		height: 100% !important;
		min-height: 0 !important;
		max-height: none !important;
	}
	.code-panel :global(.cm-scroller) {
		height: 100%;
	}
	.code-empty {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
		color: var(--color-text-muted);
	}

	/* Force CodeEditor in tab to fill parent */
	.code-tab-content :global(.editor-wrapper) {
		flex: 1;
		min-height: 0;
	}
	.code-tab-content :global(.cm-editor) {
		height: 100% !important;
		min-height: 0 !important;
		max-height: none !important;
	}
	.code-tab-content :global(.cm-scroller) {
		height: 100%;
	}

	/* Circuit tab */
	.circuit-tab-content {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		min-height: 0;
	}
	.circuit-tab-content :global(.panel) {
		flex: 1;
	}

	/* Velxio / Arduino tab */
	.velxio-tab-content {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		min-height: 0;
	}
	.velxio-iframe {
		width: 100%;
		flex: 1;
		border: none;
	}

	/* Flowchart tab */
	.flowchart-tab-content {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		min-height: 0;
	}
	.flowchart-iframe {
		width: 100%;
		flex: 1;
		border: none;
	}

	/* Asset Preview */
	.asset-preview {
		display: flex;
		flex-direction: column;
		height: 100%;
		overflow: hidden;
	}
	.asset-preview-image {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
		overflow: auto;
		background: repeating-conic-gradient(var(--color-border) 0% 25%, transparent 0% 50%) 50% / 16px 16px;
	}
	.asset-preview-image img {
		max-width: 100%;
		max-height: 100%;
		object-fit: contain;
		border-radius: var(--radius);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}
	.asset-preview-info {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 0.5rem 1rem;
		border-top: 1px solid var(--color-border);
		background: var(--color-bg-secondary);
	}
	.asset-name {
		font-weight: 600;
		font-size: 0.85rem;
	}
	.asset-path {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		word-break: break-all;
	}
	.asset-actions {
		display: flex;
		gap: 0.5rem;
		margin-top: 4px;
	}

	/* Status Bar */
	.status-bar {
		padding: 0.4rem 1rem;
		font-size: 0.8rem;
		font-weight: 500;
		text-align: center;
		border-top: 1px solid var(--color-border);
		flex-shrink: 0;
	}
	.status-bar.success {
		background: #ebfbee;
		color: #2b8a3e;
	}
	.status-bar.error {
		background: #fff5f5;
		color: #c92a2a;
	}

	/* Resize Handle (floating mode) - matches WorkspaceHeader */
	.resize-handle {
		cursor: nwse-resize;
		font-size: 0.9rem;
		color: var(--color-text-muted);
		line-height: 1;
		padding: 0.1rem 0.3rem;
		border-radius: 3px;
		align-self: center;
	}
	.resize-handle:hover {
		background: var(--color-border);
		color: var(--color-text);
	}
	/* Bottom resize handle in floating mode */
	.editor-area > .resize-handle {
		position: absolute;
		bottom: 2px;
		left: 2px;
		z-index: 10;
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

	/* Mobile tree full-width */
	.tree-panel.mobile-tree-full {
		width: 100%;
		min-width: 0;
		border-right: none;
		flex: 1;
	}
	.tree-panel.mobile-tree-hidden {
		display: none;
	}

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
	}
</style>
