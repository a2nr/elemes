import type { PageLoad } from './$types';
import type { DocsIndexEntry } from '$types/docs';
import { error } from '@sveltejs/kit';

export const load: PageLoad = async ({ fetch }) => {
	const res = await fetch('/api/docs');
	if (!res.ok) {
		throw error(500, 'Gagal memuat daftar dokumentasi');
	}
	const data = await res.json();
	return {
		docs: data.docs as DocsIndexEntry[]
	};
};
