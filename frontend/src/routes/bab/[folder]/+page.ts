import type { PageLoad } from './$types';
import type { Lesson } from '$types/lesson';
import { error } from '@sveltejs/kit';

export const load: PageLoad = async ({ params, fetch }) => {
	const res = await fetch(`/api/bab/${params.folder}`);
	if (!res.ok) {
		throw error(404, 'Bab not found');
	}
	const data = await res.json();
	return {
		title: data.title,
		introHtml: data.intro_html,
		lessons: data.lessons as Lesson[],
		folder: params.folder,
	};
};