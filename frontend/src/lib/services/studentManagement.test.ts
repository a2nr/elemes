import { describe, expect, it } from 'vitest';
import {
	addStudent,
	bulkDeleteStudents,
	exportStudentsCsv,
	filenameFromDisposition,
	importPreview,
	importStudents
} from './studentManagement';

function captureFetch(handler: (url: string, init: RequestInit) => Response) {
	const calls: { url: string; init: RequestInit }[] = [];
	const customFetch = async (input: RequestInfo | URL, init?: RequestInit) => {
		const url = String(input);
		calls.push({ url, init: init ?? {} });
		return handler(url, init ?? {});
	};
	return { calls, customFetch };
}

function jsonResponse(body: unknown, status = 200): Response {
	return {
		ok: status >= 200 && status < 300,
		status,
		json: async () => body
	} as Response;
}

describe('exportStudentsCsv', () => {
	it('POST ke /api/students/export-csv dengan student_ids terpilih', async () => {
		const blob = new Blob(['student_id;token;nama_siswa'], {
			type: 'text/csv'
		});
		const { calls, customFetch } = captureFetch(() => ({
			ok: true,
			status: 200,
			blob: async () => blob,
			headers: new Headers({
				'Content-Disposition': 'attachment; filename="data_siswa_20260808_120000.csv"'
			})
		}) as unknown as Response);

		const result = await exportStudentsCsv(['uuid-1', 'uuid-2'], customFetch);
		expect(calls).toHaveLength(1);
		expect(calls[0].url).toBe('/api/students/export-csv');
		expect(calls[0].init.method).toBe('POST');
		const body = JSON.parse(String(calls[0].init.body));
		expect(body.student_ids).toEqual(['uuid-1', 'uuid-2']);
		expect(result.filename).toBe('data_siswa_20260808_120000.csv');
		expect(result.blob.type).toBe('text/csv');
	});

	it('export kosong saat tidak ada selection → student_ids = [] (export semua)', async () => {
		const { calls, customFetch } = captureFetch(() => ({
			ok: true,
			status: 200,
			blob: async () => new Blob(['h']),
			headers: new Headers()
		}) as unknown as Response);
		await exportStudentsCsv([], customFetch);
		expect(calls).toHaveLength(1);
		const body = JSON.parse(String(calls[0].init.body));
		expect(body.student_ids).toEqual([]); // selection kosong = export seluruh siswa
	});

	it('error response melempar dengan pesan server', async () => {
		const { customFetch } = captureFetch(() =>
			jsonResponse({ success: false, message: 'student_id tidak dikenal' }, 400)
		);
		await expect(exportStudentsCsv(['x'], customFetch)).rejects.toThrow(
			'student_id tidak dikenal'
		);
	});
});

describe('filenameFromDisposition', () => {
	it('mengekstrak filename dengan dan tanpa tanda kutip', () => {
		expect(filenameFromDisposition('attachment; filename="data_siswa_1.csv"')).toBe(
			'data_siswa_1.csv'
		);
		expect(filenameFromDisposition('attachment; filename=data_siswa_2.csv')).toBe(
			'data_siswa_2.csv'
		);
		expect(filenameFromDisposition(null)).toBe('data_siswa.csv');
	});
});

describe('importPreview & importStudents', () => {
	it('mengirim multipart file ke /api/students/import/preview', async () => {
		const { calls, customFetch } = captureFetch(() =>
			jsonResponse({
				success: true,
				summary: {
					rows: 2,
					students_to_create: 1,
					students_to_update: 1,
					progress_to_create: 2,
					progress_to_restore: 1,
					conflicts: []
				},
				rows: [
					{ line: 2, student_id: '1234…', nama_siswa: 'Budi', progress_lessons: 2 },
					{ line: 3, student_id: '', nama_siswa: 'Siti', progress_lessons: 1 }
				]
			})
		);

		const file = new File(['data'], 'data_siswa.csv', { type: 'text/csv' });
		const res = await importPreview(file, customFetch);
		expect(calls).toHaveLength(1);
		expect(calls[0].url).toBe('/api/students/import/preview');
		expect(calls[0].init.body).toBeInstanceOf(FormData);
		expect(res.summary.rows).toBe(2);
		expect(res.summary.students_to_create).toBe(1);
		expect(res.summary.students_to_update).toBe(1);
		expect(res.summary.progress_to_create).toBe(2);
		expect(res.summary.progress_to_restore).toBe(1);
		expect(res.summary.conflicts).toEqual([]);
	});

	it('mengirim multipart file ke /api/students/import untuk apply', async () => {
		const { calls, customFetch } = captureFetch(() =>
			jsonResponse({
				success: true,
				students_created: 1,
				students_updated: 1,
				progress_created: 2,
				progress_restored: 1
			})
		);

		const file = new File(['data'], 'data_siswa.csv');
		const res = await importStudents(file, customFetch);
		expect(calls[0].url).toBe('/api/students/import');
		expect(calls[0].init.method).toBe('POST');
		expect(res.students_created).toBe(1);
		expect(res.students_updated).toBe(1);
		expect(res.progress_restored).toBe(1);
	});

	it('conflict apply → response 409 dengan errors, tidak melempar (ditangani UI)', async () => {
		const { customFetch } = captureFetch(() =>
			jsonResponse(
				{ success: false, message: 'Import ditolak', errors: ['Baris 2: sudah ada'] },
				409
			)
		);
		const res = await importStudents(new File(['x'], 'x.csv'), customFetch);
		expect(res.success).toBe(false);
		expect(res.errors).toEqual(['Baris 2: sudah ada']);
	});

	it('error terstruktur 400 → dikembalikan sebagai data (success:false), tidak melempar', async () => {
		const { customFetch } = captureFetch(() =>
			jsonResponse(
				{
					success: false,
					message: 'File tidak valid',
					errors: ['Baris 2: token wajib diisi']
				},
				400
			)
		);
		const res = await importPreview(new File(['x'], 'x.csv'), customFetch);
		expect(res.success).toBe(false);
		expect(res.errors).toEqual(['Baris 2: token wajib diisi']);
	});

	it('respons non-JSON (mis. 403 CSRF/proxy) → melempar Error berisi status, bukan pesan generik', async () => {
		const { customFetch } = captureFetch(() => ({
			ok: false,
			status: 403,
			json: async () => {
				throw new SyntaxError('Unexpected token < in JSON');
			}
		}) as unknown as Response);
		await expect(importPreview(new File(['x'], 'x.csv'), customFetch)).rejects.toThrow(
			'status 403'
		);
	});

	it('respons non-JSON dengan body message → melempar dengan pesan tersebut', async () => {
		const { customFetch } = captureFetch(() =>
			jsonResponse({ success: true, message: 'Origin tidak diizinkan' }, 403)
		);
		await expect(importPreview(new File(['x'], 'x.csv'), customFetch)).rejects.toThrow(
			'Origin tidak diizinkan'
		);
	});
});

describe('bulkDeleteStudents', () => {
	it('POST student_ids dan mengembalikan deleted_count', async () => {
		const { calls, customFetch } = captureFetch(() =>
			jsonResponse({ success: true, deleted_count: 2, deleted_ids: ['a', 'b'] })
		);

		const res = await bulkDeleteStudents(['a', 'b'], customFetch);
		expect(calls[0].url).toBe('/api/students/bulk-delete');
		const body = JSON.parse(String(calls[0].init.body));
		expect(body.student_ids).toEqual(['a', 'b']);
		expect(res.deleted_count).toBe(2);
	});
});

describe('addStudent', () => {
	it('mengirim POST ke /api/students/add dengan nama_siswa & token', async () => {
		const { calls, customFetch } = captureFetch(() =>
			jsonResponse({ success: true, student_id: 'abc-123', nama_siswa: 'Andi' })
		);

		const result = await addStudent('Andi', 'TOKEN_ANDI_001', customFetch);
		expect(calls).toHaveLength(1);
		expect(calls[0].url).toBe('/api/students/add');
		expect(calls[0].init.method).toBe('POST');
		const body = JSON.parse(String(calls[0].init.body));
		expect(body).toEqual({ nama_siswa: 'Andi', token: 'TOKEN_ANDI_001' });
		expect(result.success).toBe(true);
		expect(result.student_id).toBe('abc-123');
		expect(result.nama_siswa).toBe('Andi');
	});

	it('meneruskan error terstruktur saat backend menolak (mis. token duplikat)', async () => {
		const { customFetch } = captureFetch(() =>
			jsonResponse(
				{
					success: false,
					message: 'Token sudah terdaftar',
					errors: ['Baris 1: token sudah terdaftar di database']
				},
				409
			)
		);

		const result = await addStudent('Siswa Lain', 'TOKEN_DIPAKAI', customFetch);
		expect(result.success).toBe(false);
		expect(result.errors).toContain('Baris 1: token sudah terdaftar di database');
	});
});
