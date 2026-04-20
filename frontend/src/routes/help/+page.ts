import { error } from '@sveltejs/kit';

export async function load({ fetch }) {
	const res = await fetch('/api/help');
	if (!res.ok) {
		throw error(res.status, 'Gagal memuat panduan');
	}
	const data = await res.json();
	return {
		help: data
	};
}
