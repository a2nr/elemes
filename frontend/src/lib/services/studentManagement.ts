/**
 * API client student management (teacher-only round-trip CSV).
 *
 * - Export dikirim sebagai POST JSON → Blob → download client-side.
 * - Import preview/apply memakai multipart (file di-memory, tidak di-upload
 *   plaintext ke mana pun di sisi server).
 * - Response import TIDAK pernah memuat raw token / token hash.
 */

export interface ImportSummary {
	rows: number;
	students_to_create: number;
	students_to_update: number;
	progress_to_create: number;
	progress_to_restore: number;
	progress_to_reset?: number;
	conflicts: string[];
}

export interface ImportPreviewRow {
	line: number;
	student_id: string;
	nama_siswa: string;
	progress_lessons: number;
}

export interface ImportPreviewResponse {
	success: boolean;
	summary: ImportSummary;
	rows?: ImportPreviewRow[];
	message?: string;
	errors?: string[];
}

export interface ImportApplyResponse {
	success: boolean;
	students_created?: number;
	students_updated?: number;
	progress_created?: number;
	progress_restored?: number;
	progress_reset?: number;
	message?: string;
	errors?: string[];
}

export interface BulkDeleteResponse {
	success: boolean;
	deleted_count?: number;
	deleted_ids?: string[];
	message?: string;
}

export interface AddStudentResponse {
	success: boolean;
	student_id?: string;
	nama_siswa?: string;
	message?: string;
	errors?: string[];
}

export interface ExportResult {
	blob: Blob;
	filename: string;
}

export function filenameFromDisposition(disposition: string | null): string {
	if (!disposition) return 'data_siswa.csv';
	const match = /filename="?([^"]+)"?/.exec(disposition);
	return match?.[1] ?? 'data_siswa.csv';
}

/** Download Blob sebagai file (client-side). */
export function triggerBlobDownload(blob: Blob, filename: string) {
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	document.body.appendChild(a);
	a.click();
	a.remove();
	URL.revokeObjectURL(url);
}

/** Export siswa (selection) → Blob + filename dari Content-Disposition. */
export async function exportStudentsCsv(
	studentIds: string[],
	customFetch: typeof fetch = fetch
): Promise<ExportResult> {
	const res = await customFetch('/api/students/export-csv', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ student_ids: studentIds })
	});
	if (!res.ok) {
		const data = await res.json().catch(() => null);
		throw new Error(data?.message ?? 'Gagal mengekspor CSV');
	}
	return {
		blob: await res.blob(),
		filename: filenameFromDisposition(res.headers.get('Content-Disposition'))
	};
}

/** Preview import — server memvalidasi tanpa menulis apa pun. */
export async function importPreview(
	file: File,
	customFetch: typeof fetch = fetch
): Promise<ImportPreviewResponse> {
	const form = new FormData();
	form.append('file', file);
	const res = await customFetch('/api/students/import/preview', {
		method: 'POST',
		body: form
	});
	return (await parseResponse(res)) as ImportPreviewResponse;
}

/** Apply import (all-or-nothing: siswa baru dibuat, siswa existing di-restore/update). */
export async function importStudents(
	file: File,
	customFetch: typeof fetch = fetch
): Promise<ImportApplyResponse> {
	const form = new FormData();
	form.append('file', file);
	const res = await customFetch('/api/students/import', {
		method: 'POST',
		body: form
	});
	return (await parseResponse(res)) as ImportApplyResponse;
}

/** Bulk delete siswa terpilih. */
export async function bulkDeleteStudents(
	studentIds: string[],
	customFetch: typeof fetch = fetch
): Promise<BulkDeleteResponse> {
	const res = await customFetch('/api/students/bulk-delete', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ student_ids: studentIds })
	});
	return (await parseResponse(res)) as BulkDeleteResponse;
}

/** Tambah satu siswa langsung (nama + token). */
export async function addStudent(
	namaSiswa: string,
	token: string,
	customFetch: typeof fetch = fetch
): Promise<AddStudentResponse> {
	const res = await customFetch('/api/students/add', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ nama_siswa: namaSiswa, token })
	});
	return (await parseResponse(res)) as AddStudentResponse;
}

/**
 * Parsing respons API: error terstruktur backend (success:false + message/errors)
 * diteruskan apa adanya, sedangkan respons non-JSON (403/404/502 proxy, halaman
 * error HTML, dll) diubah menjadi Error dengan pesan yang informatif — bukan
 * menampilkan pesan generik di UI.
 */
async function parseResponse(res: Response): Promise<unknown> {
	if (res.ok) {
		return res.json();
	}
	const data = await res.json().catch(() => null);
	if (data && typeof data === 'object' && (data as { success?: boolean }).success === false) {
		return data; // error terstruktur dari backend (400/401/403/409/500)
	}
	throw new Error(
		(data as { message?: string } | null)?.message ??
			`Server merespons dengan status ${res.status}`
	);
}
