import { tick } from 'svelte';
import { getDraft, saveDraft, previewContent, publishDraft, type DraftResponse } from './contentEditor';

export class ContentEditorManager {
	activePath = $state<string | null>(null);
	body = $state('');
	draftId = $state<string | null>(null);
	baseMtime = $state<number | null>(null);
	dirty = $state(false);
	loading = $state(false);
	saving = $state(false);
	publishing = $state(false);

	// Preview state
	previewHtml = $state('');
	previewExerciseHtml = $state('');
	previewQuizData = $state<unknown[]>([]);
	previewSlides = $state<string[]>([]);
	previewActiveTabs = $state<string[]>([]);
	previewError = $state<string | null>(null);
	previewLoading = $state(false);

	// Mobile mode (replicated from LessonManager pattern)
	mobileMode = $state<'hidden' | 'h30' | 'h50' | 'h70' | 'full'>('hidden');
	isMobile = $state(false);

	// Tab state — 'editor' | 'preview' | 'exercise' | 'quiz' | dynamic tabs from active_tabs ('c', 'python', 'circuit', 'velxio', 'flowchart')
	activeTab = $state<string>('editor');

	// Tree state
	contentTree = $state<any[]>([]);
	assetsTree = $state<any[]>([]);
	treeRoot = $state<'content' | 'assets'>('content');
	treeLoading = $state(false);

	// Message feedback
	lastMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);

	private previewTimeout: ReturnType<typeof setTimeout> | null = null;

	constructor() {
		if (typeof window !== 'undefined') {
			const mql = window.matchMedia('(max-width: 768px)');
			this.isMobile = mql.matches;
			const handler = (e: MediaQueryListEvent) => {
				this.isMobile = e.matches;
			};
			mql.addEventListener('change', handler);
		}
	}

	async loadDraft(targetPath: string) {
		this.loading = true;
		this.activePath = targetPath;
		try {
			const res = await getDraft(targetPath);
			if (res.success) {
				this.body = res.body ?? '';
				this.draftId = res.draft_id;
				this.baseMtime = res.base_mtime ?? null;
				this.dirty = false;
				// Trigger preview
				this.schedulePreview();
			} else {
				this.showMessage('error', res.message || 'Gagal memuat file');
			}
		} catch {
			this.showMessage('error', 'Gagal terhubung ke server');
		} finally {
			this.loading = false;
		}
	}

	onBodyChange(newBody: string) {
		this.body = newBody;
		this.dirty = true;
		this.schedulePreview();
	}

	private schedulePreview() {
		if (this.previewTimeout) clearTimeout(this.previewTimeout);
		this.previewTimeout = setTimeout(() => this.runPreview(), 500);
	}

	private async runPreview() {
		if (!this.body.trim()) {
			this.previewHtml = '';
			this.previewExerciseHtml = '';
			this.previewQuizData = [];
			this.previewSlides = [];
			this.previewActiveTabs = [];
			this.previewError = null;
			return;
		}
		this.previewLoading = true;
		try {
			const res = await previewContent(this.body);
			if (res.success) {
				this.previewHtml = res.lesson_content ?? '';
				this.previewExerciseHtml = res.exercise_content ?? '';
				this.previewQuizData = res.quiz_data ?? [];
				this.previewSlides = res.slides ?? [];
				this.previewActiveTabs = res.active_tabs ?? [];
				this.previewError = null;
			} else {
				this.previewError = res.message || 'Preview gagal';
			}
		} catch {
			this.previewError = 'Gagal menghubungi server untuk preview';
		} finally {
			this.previewLoading = false;
		}
	}

	async handleSave() {
		if (!this.activePath || this.saving) return;
		this.saving = true;
		try {
			const res = await saveDraft(this.activePath, this.body, this.baseMtime);
			if (res.success) {
				this.draftId = res.draft_id;
				this.dirty = false;
				this.showMessage('success', 'Draft tersimpan');
			} else {
				this.showMessage('error', res.message || 'Gagal menyimpan draft');
			}
		} catch {
			this.showMessage('error', 'Gagal terhubung ke server');
		} finally {
			this.saving = false;
		}
	}

	async handlePublish() {
		if (!this.draftId || this.publishing) return;
		this.publishing = true;
		try {
			const res = await publishDraft(this.draftId);
			if (res.success) {
				this.dirty = false;
				this.showMessage('success', `Berhasil dipublikasikan ke ${res.published_path}`);
				// Reload to get fresh base_mtime
				if (this.activePath) {
					await this.loadDraft(this.activePath);
				}
			} else {
				if (res.message === 'conflict') {
					this.showMessage('error', res.detail || 'Konflik: file berubah di server. Muat ulang terlebih dahulu.');
				} else {
					this.showMessage('error', res.message || 'Gagal mempublikasikan');
				}
			}
		} catch {
			this.showMessage('error', 'Gagal terhubung ke server');
		} finally {
			this.publishing = false;
		}
	}

	private showMessage(type: 'success' | 'error', text: string) {
		this.lastMessage = { type, text };
		setTimeout(() => { this.lastMessage = null; }, 4000);
	}
}
