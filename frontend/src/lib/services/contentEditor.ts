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

export async function uploadAsset(file: File, folder = '') {
	const content_base64 = await fileToBase64(file);
	const res = await fetch('/api/content/assets/upload', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		credentials: 'include',
		body: JSON.stringify({ filename: file.name, folder, content_base64 }),
	});
	return res.json();
}
