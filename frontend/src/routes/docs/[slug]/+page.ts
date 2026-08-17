import type { PageLoad } from './$types';
import type { DocContent } from '$types/docs';
import { error } from '@sveltejs/kit';

export const load: PageLoad = async ({ params, fetch }) => {
	const res = await fetch(`/api/docs/${params.slug}`);
	if (!res.ok) {
		throw error(404, 'Dokumen tidak ditemukan');
	}
	const data = await res.json();
	return {
		doc: data as DocContent
	};
};
