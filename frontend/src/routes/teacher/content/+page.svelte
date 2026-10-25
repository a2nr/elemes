<script lang="ts">
	import { onMount } from 'svelte';
	import { authIsTeacher } from '$stores/auth';
	import { createFloatingPanel } from '$actions/floatingPanel.svelte';
	import { preserveFocus } from '$actions/preserveFocus';
	import CodeEditor from '$components/CodeEditor.svelte';
	import CircuitEditor from '$components/CircuitEditor.svelte';
	import TeacherVelxioEditor from '$components/TeacherVelxioEditor.svelte';
	import ContentFileTree from '$components/ContentFileTree.svelte';
	import LessonContentView, { type ClickTextDetail } from '$components/LessonContentView.svelte';
	import ContentInlineEditor from '$components/ContentInlineEditor.svelte';
	import QuizPreviewReadonly from '$components/QuizPreviewReadonly.svelte';
	import { ContentEditorManager } from '$services/contentEditor.svelte';
	import { getTree, createFolder, createFile, renameEntry, deleteEntry, uploadAsset, exportBundle, extractBundle, importBundle } from '$services/contentEditor';
	import type { TreeNode } from '$services/contentEditor';
	import { upsertSection } from '$services/markdown';

	const mgr = new ContentEditorManager();
	const float = createFloatingPanel();

	let inlineEditorRef = $state<any>(null);
	let circuitEditorRef = $state<any>(null);
	let velxioEditorRef = $state<any>(null);

	// ── Indikator loading operasi tree (CRUD / upload / export) ──────
	// Label operasi yang sedang berjalan, mis. 'Membuat folder…'.
	let treeBusy = $state<string | null>(null);
	// Key aksi yang sedang berjalan — dipakai untuk menampilkan ⏳ pada tombolnya.
	let treeBusyAction = $state<string | null>(null);

	// Content view mode: 'preview' (default rendered view) or 'edit' (inline editor)
	let contentViewMode = $state<'preview' | 'edit'>('preview');
	let editCursorPos = $state<number | undefined>(undefined);
	let editLineNumber = $state<number | undefined>(undefined);

	// Mobile: show tree or editor

	// Load trees on mount & setup global shortcut
	onMount(() => {
		void openInitialFile();

		const handleGlobalKey = (e: KeyboardEvent) => {
			if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'e') {
				if (mgr.activePath && !isAssetFile) {
					e.preventDefault();
					contentViewMode = contentViewMode === 'preview' ? 'edit' : 'preview';
				}
			}
		};
		window.addEventListener('keydown', handleGlobalKey);
		return () => {
			window.removeEventListener('keydown', handleGlobalKey);
		};
	});

	// Reset content view mode to preview when active path changes
	$effect(() => {
		if (mgr.activePath) {
			contentViewMode = 'preview';
			editCursorPos = undefined;
			editLineNumber = undefined;
		}
	});

	// When mobile & no file selected, default to tree view

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

	let extractedCircuitVelxio = $derived(extractCode(mgr.body, 'VELXIO_CIRCUIT'));

	// Tab label map for chrome tabs
	// Catatan: tab "Fitur & Aksi" dihapus — tool digantikan rail (C3),
	// sehingga desktop & mobile memakai satu cara tampil yang sama.
	let allTabs = $derived([
		...dynamicTabs,
		{ id: 'exercise', label: 'Exercise', show: hasExercise },
		{ id: 'quiz', label: 'Quiz', show: hasQuiz },
	].filter((t) => t.show !== false));

	// Reset tab saat pindah file (tab pertama yang tersedia dipilih di bawah)
	$effect(() => {
		if (mgr.activePath) {
			mgr.activeTab = '';
		}
	});

	// Auto-switch away from a tab that's no longer available
	$effect(() => {
		const validIds = allTabs.map((t) => t.id);
		if (!validIds.includes(mgr.activeTab)) {
			mgr.activeTab = validIds[0] ?? '';
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

	/** Cari node file dengan path persis di tree (recursive). */
	function findTreeNode(nodes: TreeNode[], path: string): TreeNode | null {
		for (const n of nodes) {
			if (n.path === path) return n;
			if (n.children) {
				const found = findTreeNode(n.children, path);
				if (found) return found;
			}
		}
		return null;
	}

	/**
	 * Saat pertama kali masuk editor: muat tree, lalu buka `home.md` otomatis
	 * bila ada (file navigasi utama). Bila tidak ada → panel tetap kosong
	 * ("Pilih file…") seperti sebelumnya.
	 */
	async function openInitialFile() {
		await loadTrees();
		const home = findTreeNode(mgr.contentTree, 'home.md');
		if (home && home.type === 'file') {
			await mgr.loadDraft('home.md');
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
			mgr.activeTab = 'features';
		} else {
			mgr.loadDraft(path);
		}
		if (mgr.isMobile) {
			mgr.mobileMode = mgr.treeRoot === 'assets' ? 'h50' : 'peek';
		}
	}

	function handleEditorChange(value: string) {
		mgr.onBodyChange(value);
	}

	function handleContentTextClick(detail: ClickTextDetail) {
		if (!mgr.activePath || isAssetFile) return;

		let targetPos: number | undefined = undefined;
		let targetLine: number | undefined = undefined;

		const bodyText = mgr.body;

		// 1. Try finding context snippet in bodyText
		if (detail.snippet && detail.snippet.length >= 8) {
			const idx = bodyText.indexOf(detail.snippet);
			if (idx !== -1) {
				if (detail.word) {
					const wordRel = detail.snippet.indexOf(detail.word);
					targetPos = wordRel !== -1 ? idx + wordRel : idx;
				} else {
					targetPos = idx;
				}
			}
		}

		// 2. If snippet wasn't found (e.g. markdown formatting), try the clicked word
		if (targetPos === undefined && detail.word && detail.word.length >= 3) {
			const idx = bodyText.indexOf(detail.word);
			if (idx !== -1) {
				targetPos = idx;
			}
		}

		// 3. If word not found, try block text preview (first 25 chars)
		if (targetPos === undefined && detail.blockText) {
			const lead = detail.blockText.slice(0, 25).trim();
			if (lead.length >= 6) {
				const idx = bodyText.indexOf(lead);
				if (idx !== -1) {
					targetPos = idx;
				}
			}
		}

		// 4. Calculate line number from targetPos or estimate from block ratio
		if (targetPos !== undefined) {
			targetLine = bodyText.slice(0, targetPos).split('\n').length;
		} else if (detail.blockIndex >= 0 && detail.totalBlocks > 0) {
			const lines = bodyText.split('\n');
			const estimatedLine = Math.max(1, Math.round((detail.blockIndex / detail.totalBlocks) * lines.length));
			targetLine = estimatedLine;
		} else {
			targetLine = 1;
		}

		editCursorPos = targetPos;
		editLineNumber = targetLine;
		contentViewMode = 'edit';
	}

	function syncVelxioToMarkdown(): boolean {
		if (!velxioEditorRef) return false;
		const state = velxioEditorRef.getCurrentState();
		if (!state) return false;
		applyVelxioToBody(state.code, state.circuit);
		return true;
	}

	function applyVelxioToBody(code: string, circuitJson: string) {
		let currentBody = mgr.body;

		if (code !== undefined) {
			currentBody = upsertSection(
				currentBody,
				'---INITIAL_CODE_ARDUINO---',
				'---END_INITIAL_CODE_ARDUINO---',
				code.trim()
			);
		}

		if (circuitJson !== undefined) {
			currentBody = upsertSection(
				currentBody,
				'---VELXIO_CIRCUIT---',
				'---END_VELXIO_CIRCUIT---',
				circuitJson.trim()
			);
		}

		if (currentBody !== mgr.body) {
			mgr.onBodyChange(currentBody);
			if (inlineEditorRef) {
				inlineEditorRef.setCode(currentBody);
			}
		}
	}

	function handleTransferVelxioFromTab(state: { code: string; circuit: string }) {
		applyVelxioToBody(state.code, state.circuit);
	}

	async function handleSaveAction() {
		if (mgr.activeTab === 'velxio') {
			syncVelxioToMarkdown();
		}
		await mgr.handleSave();
	}

	async function handlePublishAction() {
		if (mgr.activeTab === 'velxio') {
			syncVelxioToMarkdown();
		}
		await mgr.handlePublish();
	}

	function handleTabClick(tab: string) {
		if (mgr.activeTab === 'velxio' && tab !== 'velxio') {
			syncVelxioToMarkdown();
		}
		mgr.activeTab = tab;
		if (mgr.isMobile && mgr.mobileMode === 'hidden') {
			mgr.mobileMode = 'h50';
		}
	}

	// Step the mobile workspace height up/down through the available modes
	const MOBILE_STEPS = ['hidden', 'peek', 'h30', 'h50', 'h70', 'full'] as const;
	function stepMobileMode(dir: 1 | -1) {
		const idx = MOBILE_STEPS.indexOf(mgr.mobileMode as (typeof MOBILE_STEPS)[number]);
		const next = MOBILE_STEPS[Math.min(MOBILE_STEPS.length - 1, Math.max(0, idx + dir))];
		mgr.mobileMode = next as typeof mgr.mobileMode;
	}

	// ── Feature templates ──────────────────────────────────────
	type FeatureTemplate = { id: string; label: string; group: 'layout' | 'set_soal' | 'inline'; snippet: string };

	const FEATURE_TEMPLATES: FeatureTemplate[] = [
		// ── Layout ──
		{
			id: 'info',
			label: 'Info',
			group: 'layout',
			snippet:
				'---LESSON_INFO---\n' +
				'**Learning Objectives:**\n- \n\n' +
				'**Prerequisites:**\n- \n' +
				'---END_LESSON_INFO---\n',
		},
		{
			id: 'quiz',
			label: 'Quiz',
			group: 'layout',
			snippet:
				'\n---QUIZ_MCQ---\n' +
				'### Pertanyaan contoh?\n' +
				'- [] Pilihan A\n- [x] Pilihan B\n' +
				'> Penjelasan: tulis penjelasan di sini.\n' +
				'---END_QUIZ_MCQ---\n',
		},
		{
			id: 'quiz_weighted',
			label: 'Quiz Bobot',
			group: 'set_soal',
			snippet:
				'\n---QUIZ_WEIGHTED---\n' +
				'### Pertanyaan contoh?\n' +
				'- [10] Jawaban paling tepat\n- [7] Jawaban kurang tepat\n- [ ] Jawaban salah\n' +
				'> Pembahasan: tulis pembahasan di sini.\n' +
				'---END_QUIZ_WEIGHTED---\n',
		},
		{
			id: 'flashcard',
			label: 'Flashcard',
			group: 'set_soal',
			snippet:
				'\n---FLASHCARD---\n' +
				'### Pertanyaan flashcard?\n' +
				'Jawaban singkat tanpa opsi pilihan.\n' +
				'---END_FLASHCARD---\n',
		},
		{
			id: 'details',
			label: 'Details',
			group: 'layout',
			snippet:
				'\n<details>\n' +
				'<summary>Judul bagian yang bisa dibuka-tutup</summary>\n\n' +
				'Isi konten di dalam lipatan (markdown tetap dirender).\n\n' +
				'</details>\n',
		},
		{
			id: 'exercise',
			label: 'Exercise',
			group: 'layout',
			snippet:
				'\n---EXERCISE---\n' +
				'### Tantangan\n' +
				'Tulis deskripsi latihan di sini.\n' +
				'---\n',
		},
		{
			id: 'slide',
			label: 'Slide',
			group: 'layout',
			snippet:
				'\n---slide-start---\n' +
				'# Judul Slide 1\nTulis konten slide pertama di sini.\n\n' +
				'```embed\n<iframe src="https://www.canva.com/design/XXXX/view?embed"></iframe>\n```\n' +
				'---\n' +
				'# Judul Slide 2\nTulis konten slide kedua.\n' +
				'---slide-end---\n',
		},

		// ── Set Soal ──
		{
			id: 'set-c',
			label: 'Set C',
			group: 'set_soal',
			snippet:
				'\n---INITIAL_CODE---\n' +
				'#include <stdio.h>\n\nint main() {\n    \n    return 0;\n}\n' +
				'---END_INITIAL_CODE---\n' +
				'\n---EXPECTED_OUTPUT---\n' +
				'Output yang diharapkan\n' +
				'---END_EXPECTED_OUTPUT---\n' +
				'\n---SOLUTION_CODE---\n' +
				'#include <stdio.h>\n\nint main() {\n    \n    return 0;\n}\n' +
				'---END_SOLUTION_CODE---\n' +
				'\n---KEY_TEXT---\n' +
				'kata_kunci1\nkata_kunci2\n' +
				'---END_KEY_TEXT---\n',
		},
		{
			id: 'set-python',
			label: 'Set Python',
			group: 'set_soal',
			snippet:
				'\n---INITIAL_PYTHON---\n' +
				'# Tulis kode Python di sini\n' +
				'---END_INITIAL_PYTHON---\n' +
				'\n---EXPECTED_OUTPUT_PYTHON---\n' +
				'Output yang diharapkan\n' +
				'---END_EXPECTED_OUTPUT_PYTHON---\n' +
				'\n---SOLUTION_PYTHON---\n' +
				'# Solusi Python\n' +
				'---END_SOLUTION_PYTHON---\n' +
				'\n---KEY_TEXT---\n' +
				'kata_kunci1\nkata_kunci2\n' +
				'---END_KEY_TEXT---\n',
		},
		{
			id: 'set-circuit',
			label: 'Set Circuit',
			group: 'set_soal',
			snippet:
				'\n---INITIAL_CIRCUIT---\n' +
				'<cir f="1" ts="0.000005" ic="10.20027730826997" cb="50" pb="50" vr="5" mts="5e-11">\n' +
				'  <v x="80 200 80 112" f="0" wf="0" maxv="5"/>\n' +
				'  <r x="80 112 176 112" f="0" r="1000"/>\n' +
				'  <w x="176 200 80 200" f="0"/>\n' +
				'</cir>\n' +
				'---END_INITIAL_CIRCUIT---\n' +
				'\n---EXPECTED_CIRCUIT_OUTPUT---\n' +
				'{\n  "nodes": {\n    "Vout": { "voltage": 2.5, "tolerance": 0.2 }\n  }\n}\n' +
				'---END_EXPECTED_CIRCUIT_OUTPUT---\n' +
				'\n---SOLUTION_CIRCUIT---\n' +
				'<cir f="1" ts="0.000005" ic="10.20027730826997" cb="50" pb="50" vr="5" mts="5e-11">\n' +
				'  <v x="80 200 80 112" f="0" wf="0" maxv="5"/>\n' +
				'  <r x="80 112 176 112" f="0" r="1000"/>\n' +
				'  <w x="176 200 80 200" f="0"/>\n' +
				'</cir>\n' +
				'---END_SOLUTION_CIRCUIT---\n' +
				'\n---KEY_TEXT_CIRCUIT---\n' +
				'Vout\n' +
				'---END_KEY_TEXT_CIRCUIT---\n',
		},
		{
			id: 'set-arduino',
			label: 'Set Velxio',
			group: 'set_soal',
			snippet:
				'\n---VELXIO_CIRCUIT---\n' +
				'{\n  "board": "arduino:avr:uno",\n  "components": [],\n  "wires": []\n}\n' +
				'---END_VELXIO_CIRCUIT---\n' +
				'\n---INITIAL_CODE_ARDUINO---\n' +
				'void setup() {\n  \n}\n\n' +
				'void loop() {\n  \n}\n' +
				'---END_INITIAL_CODE_ARDUINO---\n' +
				'\n---EXPECTED_SERIAL_OUTPUT---\n' +
				'LED ON\nLED OFF\n' +
				'---END_EXPECTED_SERIAL_OUTPUT---\n' +
				'\n---EXPECTED_WIRING---\n' +
				'{\n' +
				'  "wires": [\n' +
				'    {\n' +
				'      "start": { "componentId": "arduino-uno", "pinName": "13" },\n' +
				'      "end": { "componentId": "led-builtin", "pinName": "A" }\n' +
				'    },\n' +
				'    {\n' +
				'      "start": { "componentId": "arduino-uno", "pinName": "GND" },\n' +
				'      "end": { "componentId": "led-builtin", "pinName": "C" }\n' +
				'    }\n' +
				'  ]\n' +
				'}\n' +
				'---END_EXPECTED_WIRING---\n' +
				'\n---KEY_TEXT---\n' +
				'kata_kunci\n' +
				'---END_KEY_TEXT---\n',
		},
		{
			id: 'expected-wiring',
			label: 'Expected Wiring',
			group: 'set_soal',
			snippet:
				'\n---EXPECTED_WIRING---\n' +
				'{\n' +
				'  "wires": [\n' +
				'    {\n' +
				'      "start": { "componentId": "arduino-uno", "pinName": "13" },\n' +
				'      "end": { "componentId": "led-builtin", "pinName": "A" }\n' +
				'    }\n' +
				'  ]\n' +
				'}\n' +
				'---END_EXPECTED_WIRING---\n',
		},
		{
			id: 'set-flowchart',
			label: 'Set Flowchart',
			group: 'set_soal',
			snippet:
				'\n---INITIAL_FLOWCHART---\n' +
				'start[roundrect] "Mulai"\n' +
				'init[rect] "Inisialisasi"\n' +
				'start --> init\n' +
				'---END_INITIAL_FLOWCHART---\n' +
				'\n---EXPECTED_FLOWCHART---\n' +
				'start[roundrect] "mulai"\ninit[rect] "inisialisasi"\nstart --> init\n' +
				'---END_EXPECTED_FLOWCHART---\n',
		},

		// ── Inline ──
		{
			id: 'circuit-inline',
			label: 'Circuit Inline',
			group: 'inline',
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
			label: 'Flowchart Inline',
			group: 'inline',
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
			group: 'inline',
			snippet:
				'\n```embed\n' +
				'<div style="position: relative; width: 100%; height: 0; padding-top: 56.25%; overflow: hidden; border-radius: 8px;">\n' +
				'  <iframe loading="lazy" style="position: absolute; inset: 0; width: 100%; height: 100%; border: none;" src="https://www.canva.com/design/XXXX/view?embed" allowfullscreen="allowfullscreen" allow="fullscreen"></iframe>\n' +
				'</div>\n' +
				'```\n',
		}
	];

	function getTemplateDesc(id: string): string {
		switch (id) {
			case 'info': return 'Tujuan pembelajaran & prasyarat materi';
			case 'quiz': return 'Pilihan ganda interaktif & pembahasan';
			case 'quiz_weighted': return 'Pilihan ganda berbobot (bobot tertinggi = kunci)';
			case 'flashcard': return 'Kartu hafalan tanpa penilaian';
			case 'exercise': return 'Blok instruksi tantangan latihan mandiri';
			case 'slide': return 'Presentasi carousel slide atau embed Canva';
			case 'details': return 'Bagian lipatan (bisa dibuka-tutup)';
			case 'set-c': return 'Bundle C: initial, expected, solution, key';
			case 'set-python': return 'Bundle Python dengan verifikasi output';
			case 'set-circuit': return 'Rangkaian analog & evaluasi tegangan node';
			case 'set-arduino': return 'Simulasi Arduino Uno & evaluasi wiring';
			case 'expected-wiring': return 'Evaluasi sambungan pin hardware Arduino';
			case 'set-flowchart': return 'Diagram alur algoritma dengan verifikasi';
			case 'circuit-inline': return 'Embed simulasi rangkaian analog inline';
			case 'flowchart-inline': return 'Embed canvas diagram alur interaktif inline';
			case 'embed': return 'Embed iframe responsif (Canva, video, dll)';
			default: return 'Sisipkan template ke materi';
		}
	}

	function insertTemplate(tpl: FeatureTemplate) {
		if (!mgr.activePath || isAssetFile) return;

		if (contentViewMode === 'edit' && inlineEditorRef) {
			inlineEditorRef.insertAtCursor(tpl.snippet);
		} else {
			// Mode preview: tambahkan template ke akhir body dan alihkan ke mode edit
			const current = mgr.body.trimEnd();
			const newBody = current ? `${current}\n\n${tpl.snippet.trim()}\n` : `${tpl.snippet.trim()}\n`;
			mgr.onBodyChange(newBody);
			contentViewMode = 'edit';
		}
		showToast(`Template "${tpl.label}" disisipkan`);
	}


	// ── Busy helper ────────────────────────────────────────────────
	/**
	 * Jalankan `fn` dengan indikator loading aktif.
	 * Guard re-entrancy: bila operasi lain sedang berjalan, call diabaikan
	 * sehingga klik ganda tidak menghasilkan request kedua.
	 */
	async function withTreeBusy(label: string, action: string, fn: () => Promise<void>) {
		if (treeBusy !== null || importExportBusy) return;
		treeBusy = label;
		treeBusyAction = action;
		try {
			await fn();
		} finally {
			treeBusy = null;
			treeBusyAction = null;
		}
	}

	// Tree operations
	async function handleCreateFolder(parentPath: string) {
		const name = window.prompt('Nama folder baru:');
		if (!name) return;
		const path = parentPath ? `${parentPath}/${name}` : name;
		await withTreeBusy('Membuat folder…', 'create-folder', async () => {
			const res = await createFolder(mgr.treeRoot, path);
			if (res.success) {
				await loadTrees();
			} else {
				alert(res.message || 'Gagal membuat folder');
			}
		});
	}

	async function handleCreateFile(parentPath: string) {
		const name = window.prompt('Nama file (.md):');
		if (!name) return;
		const path = parentPath ? `${parentPath}/${name}` : name;
		await withTreeBusy('Membuat file…', 'create-file', async () => {
			const res = await createFile(path);
			if (res.success) {
				await loadTrees();
				await mgr.loadDraft(path);
			} else {
				alert(res.message || 'Gagal membuat file');
			}
		});
	}

	// File navigasi kritis yang memerlukan konfirmasi ganda
	const PROTECTED_BASENAMES = new Set(['home.md', 'sub-home.md']);

	async function handleRename(oldPath: string) {
		const oldName = oldPath.split('/').pop() || oldPath;
		const newName = window.prompt('Nama baru:', oldName);
		if (!newName || newName === oldName) return;
		const parentPath = oldPath.substring(0, oldPath.lastIndexOf('/'));
		const newPath = parentPath ? `${parentPath}/${newName}` : newName;

		// P0-1: konfirmasi kedua untuk file navigasi kritis
		if (PROTECTED_BASENAMES.has(oldName)) {
			if (!window.confirm(
				`"${oldName}" adalah file navigasi utama. Mengganti nama ini bisa ` +
				`merusak halaman untuk semua siswa dan TIDAK BISA di-undo. Lanjutkan?`
			)) return;
		}

		await withTreeBusy('Mengubah nama…', 'rename', async () => {
			const res = await renameEntry(mgr.treeRoot, oldPath, newPath, PROTECTED_BASENAMES.has(oldName));
			if (res.success) {
				await loadTrees();
				if (mgr.activePath === oldPath) {
					await mgr.loadDraft(newPath);
				}
			} else {
				alert(res.message || 'Gagal rename');
			}
		});
	}

	async function handleDelete(path: string) {
		const name = path.split('/').pop() || path;
		// P0-1: konfirmasi kedua untuk file navigasi kritis
		if (PROTECTED_BASENAMES.has(name)) {
			if (!window.confirm(
				`"${name}" adalah file navigasi utama. Menghapus ini bisa ` +
				`merusak halaman untuk semua siswa dan TIDAK BISA di-undo. Lanjutkan?`
			)) return;
		} else if (!window.confirm(`Hapus "${name}"?`)) return;

		await withTreeBusy('Menghapus…', 'delete', async () => {
			const res = await deleteEntry(mgr.treeRoot, path, PROTECTED_BASENAMES.has(name));
			if (res.success) {
				await loadTrees();
				if (mgr.activePath === path) {
					mgr.activePath = null;
					mgr.body = '';
					mgr.draftId = null;
					mgr.previewSlides = [];
					mgr.previewActiveTabs = [];
				}
			} else if (res.needs_force) {
				if (window.confirm(`Folder "${name}" tidak kosong. Hapus semua isi?`)) {
					const forceRes = await deleteEntry(mgr.treeRoot, path, PROTECTED_BASENAMES.has(name), true);
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
		});
	}

	async function handleUpload() {
		const input = document.createElement('input');
		input.type = 'file';
		input.accept = '.png,.jpg,.jpeg,.gif,.webp,.svg';
		input.onchange = async () => {
			const file = input.files?.[0];
			if (!file) return;
			const folder = window.prompt('Folder tujuan (opsional, kosongkan untuk root assets):', '') ?? '';
			await withTreeBusy(`Mengunggah ${file.name}…`, 'upload', async () => {
				showToast(`Mengunggah ${file.name}…`);
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
			});
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

	// ── Export / Import bundle ──────────────────────────────────────
	let importExportBusy = $state(false);
	let importProgress = $state<{ done: number; total: number; current: string } | null>(null);

	function flattenTreePaths(nodes: TreeNode[]): string[] {
		const out: string[] = [];
		const walk = (list: TreeNode[]) => {
			for (const n of list) {
				if (n.type === 'file') out.push(n.path);
				if (n.children) walk(n.children);
			}
		};
		walk(nodes);
		return out;
	}

	function showToast(text: string, isError = false) {
		const toast = document.createElement('div');
		toast.textContent = text;
		toast.style.cssText = `position:fixed;bottom:1rem;left:50%;transform:translateX(-50%);background:${isError ? '#b91c1c' : '#15803d'};color:#fff;padding:6px 16px;border-radius:8px;font-size:0.8rem;z-index:10000;max-width:90vw;`;
		document.body.appendChild(toast);
		setTimeout(() => toast.remove(), 4000);
	}

	async function handleExport() {
		await withTreeBusy('Menyiapkan zip…', 'export', async () => {
			importExportBusy = true;
			try {
				const blob = await exportBundle();
				const url = URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = url;
				a.download = `elemes-bundle-${new Date().toISOString().slice(0, 10)}.zip`;
				a.click();
				URL.revokeObjectURL(url);
				showToast('Export berhasil — file sedang diunduh.');
			} catch (e) {
				showToast(`Export gagal: ${e instanceof Error ? e.message : String(e)}`, true);
			} finally {
				importExportBusy = false;
			}
		});
	}

	async function handleImportFile(file: File) {
		if (importExportBusy || treeBusy !== null) return; // guard double-submit
		importExportBusy = true;
		importProgress = { done: 0, total: 0, current: 'Menyiapkan import…' };
		try {
			// 1. Reload tree SEBELUM extract supaya existingPaths fresh
			await loadTrees();
			const existing = new Set<string>([
				...flattenTreePaths(mgr.contentTree),
				...flattenTreePaths(mgr.assetsTree),
			]);

			// 2. Extract zip di browser
			const bundle = await extractBundle(file);
			if (bundle.invalidEntries.length > 0) {
				showToast(`${bundle.invalidEntries.length} entry diabaikan: ${bundle.invalidEntries.slice(0, 5).join(', ')}${bundle.invalidEntries.length > 5 ? '…' : ''}`, true);
			}
			if (bundle.contentFiles.length + bundle.assetFiles.length === 0) {
				showToast('Bundle kosong — tidak ada yang diimport.', true);
				return;
			}

			// 3. Konfirmasi mode: OK = skip, Cancel = overwrite
			const mode = confirm(
				`Import ${bundle.contentFiles.length} materi + ${bundle.assetFiles.length} asset?\n\n` +
				'OK = lewati file yang sudah ada\nCancel = timpa file yang sudah ada',
			) ? 'skip' : 'overwrite';

			// 4. Kirim per-file
			const result = await importBundle({
				contentFiles: bundle.contentFiles,
				assetFiles: bundle.assetFiles,
				mode,
				existingPaths: existing,
				onProgress: (done, total, current) => {
					importProgress = { done, total, current };
				},
			});
			showToast(
				result.success
					? `Import selesai: ${result.imported} ditulis, ${result.skipped} dilewati.`
					: `Import gagal di ${result.failedPath}: ${result.message}`,
				!result.success,
			);

			// 5. Reload tree UI setelah import
			await loadTrees();
		} catch (e) {
			showToast(`Import gagal: ${e instanceof Error ? e.message : String(e)}`, true);
		} finally {
			importExportBusy = false;
			importProgress = null;
		}
	}

	function handleImportClick() {
		const input = document.createElement('input');
		input.type = 'file';
		input.accept = '.zip,application/zip';
		input.onchange = () => {
			const file = input.files?.[0];
			if (file) handleImportFile(file);
		};
		input.click();
	}
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
		<!-- Preview Panel (content view or inline editor) -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="preview-panel"
			class:full-width={float.floating || mgr.isMobile}
			class:in-edit-mode={contentViewMode === 'edit'}
			onselectstart={(e) => { if (contentViewMode !== 'edit') e.preventDefault(); }}
			oncopy={(e) => { if (contentViewMode !== 'edit') e.preventDefault(); }}
			oncut={(e) => { if (contentViewMode !== 'edit') e.preventDefault(); }}
			oncontextmenu={(e) => { if (contentViewMode !== 'edit') e.preventDefault(); }}
		>
			{#if mgr.previewLoading && contentViewMode !== 'edit'}
				<div class="preview-loading">Memuat preview...</div>
			{:else if mgr.previewError && contentViewMode !== 'edit'}
				<div class="preview-error">{mgr.previewError}</div>
			{:else if isImageFile && mgr.activePath}
				<div class="preview-asset">
					<img src="/assets/{mgr.activePath}" alt={activeFileName} style="max-width:100%;border-radius:var(--radius);" loading="lazy" />
					<p class="preview-asset-meta">/assets/{mgr.activePath}</p>
				</div>
			{:else if contentViewMode === 'edit' && mgr.activePath && !isAssetFile}
				<ContentInlineEditor
					bind:this={inlineEditorRef}
					code={mgr.body}
					fileName={activeFileName}
					initialCursorPos={editCursorPos}
					initialLine={editLineNumber}
					onchange={handleEditorChange}
					onclose={() => contentViewMode = 'preview'}
				/>
			{:else if mgr.previewHtml}
				<div class="preview-edit-bar">
					<span class="preview-edit-hint">👆 Klik teks untuk edit langsung</span>
					<button
						type="button"
						class="btn-quick-edit"
						onclick={() => { editCursorPos = undefined; editLineNumber = 1; contentViewMode = 'edit'; }}
						title="Buka editor teks (Ctrl+E)"
					>
						✏️ Edit Teks (Ctrl+E)
					</button>
				</div>
				<LessonContentView
					lessonHtml={mgr.previewHtml}
					exerciseHtml={mgr.previewExerciseHtml}
					quizData={mgr.previewQuizData as any}
					slides={mgr.previewSlides}
					activeTabs={mgr.previewActiveTabs}
					clickable={true}
					onclicktext={handleContentTextClick}
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
			class:mobile-peek={mgr.isMobile && mgr.mobileMode === 'peek'}
			class:mobile-h30={mgr.isMobile && mgr.mobileMode === 'h30'}
			class:mobile-h50={mgr.isMobile && mgr.mobileMode === 'h50'}
			class:mobile-h70={mgr.isMobile && mgr.mobileMode === 'h70'}
			class:mobile-full={mgr.isMobile && mgr.mobileMode === 'full'}
			style={float.style}
		>
			<!-- Save / Publish actions (shared across all header modes) -->
		{#snippet saveActions()}
			{#if mgr.activePath && !isAssetFile}
				<button class="panel-btn save-btn" use:preserveFocus onclick={() => handleSaveAction()} disabled={mgr.saving || (!mgr.dirty && mgr.activeTab !== 'velxio')} title="Simpan">
					{mgr.saving ? '⏳' : '💾'}
				</button>
				<button class="panel-btn publish-btn" use:preserveFocus onclick={() => handlePublishAction()} disabled={mgr.publishing || mgr.saving} title="Publish">
					{mgr.publishing ? '⏳' : '🚀'}
				</button>
			{/if}
		{/snippet}

		<!-- File management actions (tree header) + indikator loading -->
		{#snippet treeActions()}
			{#if importProgress}
				<span class="ie-progress" title={importProgress.current}>
					⏳ {importProgress.total > 0 ? `${importProgress.done}/${importProgress.total}` : '…'} {importProgress.current}
				</span>
			{:else if treeBusy}
				<span class="ie-progress">⏳ {treeBusy}</span>
			{/if}
			{#if mgr.treeRoot === 'content'}
				<button type="button" class="tree-action-btn" use:preserveFocus onclick={() => handleCreateFile('')} disabled={treeBusy !== null || importExportBusy} title="Buat file baru (.md)">
					{treeBusyAction === 'create-file' ? '⏳' : '📄'}
				</button>
				<button type="button" class="tree-action-btn" use:preserveFocus onclick={() => handleCreateFolder('')} disabled={treeBusy !== null || importExportBusy} title="Buat folder baru">
					{treeBusyAction === 'create-folder' ? '⏳' : '📁'}
				</button>
			{:else}
				<button type="button" class="tree-action-btn" use:preserveFocus onclick={handleUpload} disabled={treeBusy !== null || importExportBusy} title="Upload asset gambar">
					{treeBusyAction === 'upload' ? '⏳' : '⬆️'}
				</button>
				<button type="button" class="tree-action-btn" use:preserveFocus onclick={() => handleCreateFolder('')} disabled={treeBusy !== null || importExportBusy} title="Buat folder asset">
					{treeBusyAction === 'create-folder' ? '⏳' : '📁'}
				</button>
			{/if}
			<button type="button" class="tree-action-btn" use:preserveFocus onclick={handleExport} disabled={treeBusy !== null || importExportBusy} title="Export semua materi & assets (zip)">
				{treeBusyAction === 'export' ? '⏳' : '📤'}
			</button>
			<button type="button" class="tree-action-btn" use:preserveFocus onclick={handleImportClick} disabled={treeBusy !== null || importExportBusy} title="Import materi & assets dari zip">
				{importExportBusy && !treeBusy ? '⏳' : '📥'}
			</button>
		{/snippet}

		<!-- Quick tools rail — dipakai desktop & mobile (satu cara tampil, C3) -->
		{#snippet toolsRail()}
			{#if mgr.activePath}
				<div class="quick-tools-rail" data-preserve-editor-focus>
					<!-- Pinned: status file aktif + aksi utama (tidak ikut scroll) -->
					<div class="qt-pinned">
						<span class="qt-file-name" title={mgr.activePath}>{isAssetFile ? '🖼️' : '📄'} {activeFileName}</span>
						{#if isAssetFile}
							<span class="qt-path" title={mgr.activePath}>/assets/{mgr.activePath}</span>
							<button type="button" class="qt-chip" use:preserveFocus onclick={handleCopyAssetPath} title="Salin path asset">📋 Salin Path</button>
						{:else}
							<span class="qt-dirty-badge" class:dirty={mgr.dirty}>{mgr.dirty ? '● Belum disimpan' : '✓ Tersimpan'}</span>
							<button type="button" class="qt-chip qt-action-edit" use:preserveFocus onclick={() => { contentViewMode = contentViewMode === 'edit' ? 'preview' : 'edit'; }} title="Toggle editor teks (Ctrl+E)">
								{contentViewMode === 'edit' ? '👁️' : '✏️'}
							</button>
							<button type="button" class="qt-chip" use:preserveFocus onclick={() => handleSaveAction()} disabled={mgr.saving || (!mgr.dirty && mgr.activeTab !== 'velxio')} title="Simpan">
								{mgr.saving ? '⏳' : '💾'}
							</button>
							<button type="button" class="qt-chip" use:preserveFocus onclick={() => handlePublishAction()} disabled={mgr.publishing || mgr.saving} title="Publish">
								{mgr.publishing ? '⏳' : '🚀'}
							</button>
						{/if}
					</div>

					{#if !isAssetFile}
						<!-- Scrollable templates -->
						<div class="qt-scroll">
							<div class="qt-divider" aria-hidden="true"></div>

							<!-- Layout templates -->
							<div class="qt-group">
								<span class="qt-label">📐 Layout</span>
								{#each FEATURE_TEMPLATES.filter(t => t.group === 'layout') as tpl}
									<button type="button" class="qt-chip" use:preserveFocus onclick={() => insertTemplate(tpl)} title={getTemplateDesc(tpl.id)}>
										{tpl.label}
									</button>
								{/each}
							</div>

							<div class="qt-divider" aria-hidden="true"></div>

							<!-- Set soal templates -->
							<div class="qt-group">
								<span class="qt-label">🎯 Set Soal</span>
								{#each FEATURE_TEMPLATES.filter(t => t.group === 'set_soal') as tpl}
									<button type="button" class="qt-chip" use:preserveFocus onclick={() => insertTemplate(tpl)} title={getTemplateDesc(tpl.id)}>
										{tpl.label}
									</button>
								{/each}
							</div>

							<div class="qt-divider" aria-hidden="true"></div>

							<!-- Inline templates -->
							<div class="qt-group">
								<span class="qt-label">⚡ Inline</span>
								{#each FEATURE_TEMPLATES.filter(t => t.group === 'inline') as tpl}
									<button type="button" class="qt-chip" use:preserveFocus onclick={() => insertTemplate(tpl)} title={getTemplateDesc(tpl.id)}>
										{tpl.label}
									</button>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/if}
		{/snippet}

		<!-- Panel Header (floating drag handle) -->
			{#if float.floating && !mgr.isMobile}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="panel-header draggable" onmousedown={float.onDragStart} ontouchstart={float.onTouchDragStart}>
					<span class="resize-handle" onmousedown={(e) => { e.stopPropagation(); float.onResizeStart(e); }} ontouchstart={float.onTouchResizeStart}>&#x25F3;</span>
					<div class="chrome-tabs">
						{#each allTabs as tab}
							<button class="chrome-tab" class:active={mgr.activeTab === tab.id} use:preserveFocus onclick={() => handleTabClick(tab.id)}>{tab.label}</button>
						{/each}
					</div>
					<div class="panel-actions">
						{@render saveActions()}
						<button class="panel-btn" title="Minimize" onclick={float.minimize}>▽</button>
						<button class="panel-btn" title="Kembali ke dock (inline)" onclick={float.toggle}>&#x229E;</button>
					</div>
				</div>
			{:else if mgr.isMobile}
				<!-- Mobile: panel header (tree view only) -->
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="panel-header">
					<span class="chrome-tab active">{mgr.activePath ? activeFileName : 'File Tree'}</span>
					<div class="panel-actions">
						<button class="panel-btn" use:preserveFocus onclick={() => stepMobileMode(-1)} title="Minimize" disabled={mgr.mobileMode === 'hidden'}>▽</button>
						<button class="panel-btn" use:preserveFocus onclick={() => stepMobileMode(1)} title="Maximize" disabled={mgr.mobileMode === 'full'}>△</button>
					</div>
				</div>
			{:else}
				<!-- Desktop: panel header with tabs + actions -->
				<div class="panel-header">
					<div class="chrome-tabs">
						{#if mgr.activePath}
							{#each allTabs as tab}
								<button class="chrome-tab" class:active={mgr.activeTab === tab.id} use:preserveFocus onclick={() => handleTabClick(tab.id)}>{tab.label}</button>
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

				<!-- Quick tools rail (desktop & mobile) -->
				{@render toolsRail()}

				<!-- Editor main: tab panels + feature sidebar -->
			<div class="editor-main">
			<div class="editor-body" class:no-tabs={allTabs.length === 0}>
				{#if mgr.isMobile}
					<!-- MOBILE: Show full-width tree -->
					<div class="tree-panel mobile-tree-full">
						<div class="tree-header">
							<div class="tree-actions">
								{@render treeActions()}
							</div>
							<div class="tree-tabs">
								<button class="tree-tab" class:active={mgr.treeRoot === 'content'} onclick={() => mgr.treeRoot = 'content'}>Materi</button>
								<button class="tree-tab" class:active={mgr.treeRoot === 'assets'} onclick={() => mgr.treeRoot = 'assets'}>Assets</button>
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
					<!-- DESKTOP: Tree + Tab panels side by side -->
					<!-- File Tree -->
					<div class="tree-panel">
						<div class="tree-header">
							<div class="tree-actions">
								{@render treeActions()}
							</div>
							<div class="tree-tabs">
								<button class="tree-tab" class:active={mgr.treeRoot === 'content'} onclick={() => mgr.treeRoot = 'content'}>Materi</button>
								<button class="tree-tab" class:active={mgr.treeRoot === 'assets'} onclick={() => mgr.treeRoot = 'assets'}>Assets</button>
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
										<TeacherVelxioEditor
											bind:this={velxioEditorRef}
											initialCode={extractedCodes.velxio}
											initialCircuit={extractedCircuitVelxio}
											onTransfer={handleTransferVelxioFromTab}
											onSave={handleTransferVelxioFromTab}
										/>
									</div>
								{:else if dynTab.id === 'flowchart'}
									<div class="flowchart-tab-content">
										<iframe
											class="flowchart-iframe"
											src="/flowchart/?iframe=true"
											title="Flowchart Editor"
											credentialless
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
	.preview-panel.in-edit-mode {
		padding: 0.5rem;
		display: flex;
		flex-direction: column;
	}
	.preview-panel.in-edit-mode :global(.inline-editor-container) {
		flex: 1;
		min-height: 75vh;
	}
	.preview-edit-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
		padding: 0.35rem 0.6rem;
		background: var(--color-bg-secondary);
		border: 1px dashed var(--color-border);
		border-radius: var(--radius);
		font-size: 0.78rem;
		color: var(--color-text-muted);
	}
	.preview-edit-hint {
		display: flex;
		align-items: center;
		gap: 4px;
	}
	.btn-quick-edit {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 4px;
		padding: 0.2rem 0.55rem;
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--color-primary, #339af0);
		cursor: pointer;
		transition: all 0.15s;
		white-space: nowrap;
	}
	.btn-quick-edit:hover {
		background: var(--color-border);
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
		margin-left: auto;
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
	.ie-progress {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		padding: 0.15rem 0.5rem;
		white-space: nowrap;
	}

	/* Editor main: tab panels (left) + feature sidebar (right) */
	.editor-main {
		display: flex;
		flex: 1;
		min-height: 0;
		overflow: hidden;
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
		flex: 0 0 35%;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		min-height: 0;
	}
	.tab-panel {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow-y: auto;
		min-height: 0;
		height: 100%;
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

	.editor-body {
		flex: 1;
		display: flex;
		overflow: hidden;
		min-height: 0;
	}
	/* Tanpa tab (mis. file materi biasa) → tree memakai seluruh lebar */
	.editor-body.no-tabs .tab-panels { display: none; }
	.editor-body.no-tabs .tree-panel { flex: 1 1 auto; }

	/* Tree Panel */
	.tree-panel {
		flex: 0 0 65%;
		min-width: 0;
		border-right: 1px solid var(--color-border);
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}
	.tree-panel.mobile-tree-full {
		flex: 0 0 100%;
		border-right: none;
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
	.tree-actions {
		display: flex;
		gap: 2px;
		align-items: center;
	}
	.tree-action-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		padding: 0;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 4px;
		font-size: 0.85rem;
		cursor: pointer;
		transition: background 0.15s, border-color 0.15s;
	}
	.tree-action-btn:hover:not(:disabled) {
		background: var(--color-border);
		border-color: var(--color-text-muted);
	}
	.tree-action-btn:disabled {
	 opacity: 0.45;
		cursor: not-allowed;
	}
	.tree-actions-header {
		display: flex;
		gap: 2px;
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
		height: 100%;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		min-height: 400px;
	}
	.velxio-iframe {
		width: 100%;
		flex: 1;
		height: 100%;
		min-height: 350px;
		border: none;
		display: block;
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
	.editor-area.mobile-peek { height: 84px; }
	.editor-area.mobile-h30 { height: 30vh; }
	.editor-area.mobile-h50 { height: 50vh; }
	.editor-area.mobile-h70 { height: 70vh; }
	.editor-area.mobile-full { height: 100dvh; border-radius: 0; max-height: none; }

	/* ── Quick tools rail ── */
	.quick-tools-rail {
		display: flex;
		align-items: stretch;
		background: var(--color-bg-secondary);
		border-bottom: 1px solid var(--color-border);
		flex-shrink: 0;
	}
	.qt-pinned {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.4rem 0.6rem;
		background: var(--color-bg-secondary);
		border-right: 1px solid var(--color-border);
		flex-shrink: 0;
	}
	.qt-file-name {
		font-size: 0.78rem;
		font-weight: 600;
		color: var(--color-text);
		max-width: 180px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.qt-path {
		font-size: 0.7rem;
		color: var(--color-text-muted);
		max-width: 200px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.qt-dirty-badge {
		font-size: 0.68rem;
		padding: 0.15rem 0.45rem;
		border-radius: 4px;
		background: #ebfbee;
		color: #2b8a3e;
		white-space: nowrap;
	}
	.qt-dirty-badge.dirty {
		background: #fff3bf;
		color: #e67700;
	}
	.qt-scroll {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.4rem 0.6rem;
		overflow-x: auto;
		overflow-y: hidden;
		white-space: nowrap;
		scrollbar-width: none;
		-webkit-overflow-scrolling: touch;
		flex: 1;
		min-width: 0;
	}
	.qt-scroll::-webkit-scrollbar { display: none; }

	.qt-group {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		flex-shrink: 0;
	}
	.qt-label {
		font-size: 0.68rem;
		font-weight: 700;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		white-space: nowrap;
	}
	.qt-divider {
		width: 1px;
		height: 22px;
		background: var(--color-border);
		flex-shrink: 0;
	}
	.qt-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.4rem 0.7rem;
		min-height: 36px;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 6px;
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--color-text);
		cursor: pointer;
		white-space: nowrap;
		flex-shrink: 0;
		transition: background 0.15s, border-color 0.15s;
	}
	.qt-chip:hover:not(:disabled) {
		background: var(--color-border);
		border-color: var(--color-text-muted);
	}
	.qt-chip:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}
	.qt-action-edit {
		color: var(--color-primary, #339af0);
		font-weight: 600;
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

	@media (max-width: 768px) {
		.content-editor-layout {
			grid-template-columns: 1fr;
			padding: 0;
		}
	}
</style>
