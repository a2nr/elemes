import { unzip, strFromU8 } from 'fflate';

export interface TreeNode {
	type: 'file' | 'folder';
	name: string;
	path: string;
	ext?: string;
	children?: TreeNode[];
}

export interface DraftResponse {
	success: boolean;
	source?: 'draft' | 'file';
	draft_id: string | null;
	body?: string;
	base_mtime?: number | null;
	message?: string;
}

export interface PreviewResponse {
	success: boolean;
	lesson_content?: string;
	exercise_content?: string;
	quiz_data?: unknown[];
	slides?: string[];
	active_tabs?: string[];
	message?: string;
}

export async function getTree(root: 'content' | 'assets'): Promise<TreeNode[]> {
	const res = await fetch(`/api/content/tree?root=${root}`, { credentials: 'include' });
	const data = await res.json();
	return data.success ? data.tree : [];
}

export async function getDraft(targetPath: string): Promise<DraftResponse> {
	const res = await fetch(`/api/content/drafts?target_path=${encodeURIComponent(targetPath)}`, {
		credentials: 'include',
	});
	return res.json();
}

export async function saveDraft(targetPath: string, body: string, baseMtime: number | null) {
	const res = await fetch('/api/content/drafts', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		credentials: 'include',
		body: JSON.stringify({ target_path: targetPath, body, base_mtime: baseMtime }),
	});
	return res.json();
}

/**
 * @deprecated Use client-side renderMarkdownPreview from './markdown' instead.
 * Kept for fallback or direct API verification purposes.
 */
export async function previewContent(body: string): Promise<PreviewResponse> {
	const res = await fetch('/api/content/preview', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		credentials: 'include',
		body: JSON.stringify({ body }),
	});
	return res.json();
}

export async function publishDraft(draftId: string) {
	const res = await fetch(`/api/content/drafts/${draftId}/publish`, {
		method: 'POST',
		credentials: 'include',
	});
	return res.json();
}

export async function discardDraft(draftId: string) {
	const res = await fetch(`/api/content/drafts/${draftId}`, {
		method: 'DELETE',
		credentials: 'include',
	});
	return res.json();
}

export async function createFolder(root: 'content' | 'assets', path: string) {
	const res = await fetch('/api/content/tree/folder', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		credentials: 'include',
		body: JSON.stringify({ root, path }),
	});
	return res.json();
}

export async function createFile(path: string, template?: string) {
	const res = await fetch('/api/content/tree/file', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		credentials: 'include',
		body: JSON.stringify({ root: 'content', path, template }),
	});
	return res.json();
}

export async function renameEntry(
	root: 'content' | 'assets',
	oldPath: string,
	newPath: string,
	confirmCritical = false,
) {
	const res = await fetch('/api/content/tree/rename', {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		credentials: 'include',
		body: JSON.stringify({ root, old_path: oldPath, new_path: newPath, confirm_critical: confirmCritical }),
	});
	return res.json();
}

export async function deleteEntry(root: 'content' | 'assets', path: string, confirmCritical = false, force = false) {
	const res = await fetch(
		`/api/content/tree/entry?root=${root}&path=${encodeURIComponent(path)}&force=${force}&confirm_critical=${confirmCritical}`,
		{ method: 'DELETE', credentials: 'include' },
	);
	return res.json();
}

function fileToBase64(file: File): Promise<string> {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => {
			const result = reader.result as string;
			resolve(result.split(',')[1] ?? '');
		};
		reader.onerror = () => reject(reader.error);
		reader.readAsDataURL(file);
	});
}

export async function uploadAsset(file: File, folder = '', overwrite = false) {
	const content_base64 = await fileToBase64(file);
	const res = await fetch('/api/content/assets/upload', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		credentials: 'include',
		body: JSON.stringify({ filename: file.name, folder, content_base64, overwrite }),
	});
	if (!res.ok) {
		// Respons error bisa berupa JSON {message, ...}, JSON lain (mis. 502
		// proxy {"error": ...}), atau HTML (Flask default 404/500). Pastikan
		// selalu menghasilkan string — jangan pernah 'undefined'.
		const data = await res.json().catch(() => null);
		return { success: false, message: data?.message ?? `HTTP ${res.status}` };
	}
	return res.json();
}

// ── Bundle import/export (client-side zip, per-file transfer) ─────

export async function exportBundle(scope: 'all' | 'content' | 'assets' = 'all'): Promise<Blob> {
	const url = scope === 'all' ? '/api/content/export' : `/api/content/export?scope=${scope}`;
	const res = await fetch(url, { credentials: 'include' });
	if (!res.ok) {
		throw new Error(`Export gagal (${res.status})`);
	}
	return res.blob();
}

export interface ImportFileSpec {
	path: string;                 // relatif root (tanpa prefix content/ | assets/)
	body?: string;                // untuk .md (teks hasil decode)
	bytes?: Uint8Array;           // untuk asset biner
}

export interface ImportOptions {
	contentFiles: ImportFileSpec[];
	assetFiles: ImportFileSpec[];
	mode: 'skip' | 'overwrite';
	existingPaths?: Set<string>;  // path (relatif root) yang sudah ada di server
	onProgress?: (done: number, total: number, currentPath: string) => void;
}

export interface ImportSummary {
	success: boolean;
	imported: number;
	skipped: number;
	failedPath?: string;
	message?: string;
}

/** Pastikan semua folder parent dari relPath ada di server.
 *  POST /content/tree/folder; 409 "Folder sudah ada" dianggap sukses. */
async function ensureFolders(root: 'content' | 'assets', relPath: string): Promise<void> {
	const parts = relPath.split('/').slice(0, -1); // buang filename
	let cur = '';
	for (const part of parts) {
		cur = cur ? `${cur}/${part}` : part;
		const res = await createFolder(root, cur);
		if (!res.success && res.message !== 'Folder sudah ada') {
			throw new Error(`Gagal membuat folder ${cur}: ${res.message ?? 'unknown'}`);
		}
	}
}

export async function importBundle(options: ImportOptions): Promise<ImportSummary> {
	const { contentFiles, assetFiles, mode, existingPaths, onProgress } = options;
	const total = contentFiles.length + assetFiles.length;
	let done = 0;
	let imported = 0;
	let skipped = 0;

	const files: Array<{ root: 'content' | 'assets'; spec: ImportFileSpec }> = [
		...contentFiles.map((spec) => ({ root: 'content' as const, spec })),
		...assetFiles.map((spec) => ({ root: 'assets' as const, spec })),
	];

	for (const { root, spec } of files) {
		if (mode === 'skip' && existingPaths?.has(spec.path)) {
			skipped++;
			onProgress?.(++done, total, spec.path);
			continue;
		}
		try {
			await ensureFolders(root, spec.path);
			if (root === 'content') {
				if (existingPaths?.has(spec.path)) {
					// file sudah ada → jalur overwrite: draft + publish (base_mtime null = tanpa conflict check)
					const draft = await saveDraft(spec.path, spec.body ?? '', null);
					if (!draft.success) {
						return { success: false, imported, skipped, failedPath: spec.path, message: draft.message };
					}
					const pub = await publishDraft(draft.draft_id!);
					if (!pub.success) {
						return { success: false, imported, skipped, failedPath: spec.path, message: pub.message };
					}
				} else {
					// file baru → tree/file dengan body sebagai template
					const res = await createFile(spec.path, spec.body);
					if (!res.success) {
						return { success: false, imported, skipped, failedPath: spec.path, message: res.message };
					}
				}
			} else {
				// asset → assets/upload (nama file = basename, folder = parent relatif)
				const bytes = spec.bytes ?? new Uint8Array();
				const res = await uploadAsset(
					new File([bytes.slice().buffer as ArrayBuffer], spec.path.split('/').pop() ?? 'file'),
					spec.path.includes('/') ? spec.path.slice(0, spec.path.lastIndexOf('/')) : '',
					mode === 'overwrite',
				);
				if (!res.success) {
					return { success: false, imported, skipped, failedPath: spec.path, message: res.message ?? 'Gagal mengunggah asset' };
				}
			}
			imported++;
			onProgress?.(++done, total, spec.path);
		} catch (e) {
			return {
				success: false, imported, skipped, failedPath: spec.path,
				message: e instanceof Error ? e.message : String(e),
			};
		}
	}
	return { success: true, imported, skipped };
}

export interface ExtractedBundle {
	contentFiles: ImportFileSpec[];
	assetFiles: ImportFileSpec[];
	invalidEntries: string[]; // entry di luar content/|assets/ | bukan .md di content/ | path mencurigakan
}

/** Extract zip di browser (pola zip = output /content/export:
 *  top-level `content/**.md` dan `assets/**`). Entry tidak valid
 *  dikumpulkan di invalidEntries — tidak diimport, dilaporkan ke user. */
export async function extractBundle(file: File): Promise<ExtractedBundle> {
	const buf = new Uint8Array(await file.arrayBuffer());
	const entries = await new Promise<Record<string, Uint8Array>>((resolve, reject) =>
		unzip(buf, (err, data) => (err ? reject(new Error('File bukan zip yang valid')) : resolve(data))),
	);

	const contentFiles: ImportFileSpec[] = [];
	const assetFiles: ImportFileSpec[] = [];
	const invalidEntries: string[] = [];

	for (const [name, bytes] of Object.entries(entries)) {
		if (name.endsWith('/')) continue; // directory entry
		const parts = name.split('/');
		if ((parts[0] !== 'content' && parts[0] !== 'assets') || parts.length < 2) {
			invalidEntries.push(name);
			continue;
		}
		const rel = parts.slice(1).join('/');
		if (!rel || rel.startsWith('/') || rel.split('/').includes('..') || rel.split('/').includes('')) {
			invalidEntries.push(name);
			continue;
		}
		if (parts[0] === 'content') {
			if (!rel.endsWith('.md')) {
				invalidEntries.push(name);
				continue;
			}
			contentFiles.push({ path: rel, body: strFromU8(bytes) });
		} else {
			assetFiles.push({ path: rel, bytes });
		}
	}
	return { contentFiles, assetFiles, invalidEntries };
}
