import { getLesson } from '$services/api';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch }) => {
	const lesson = await getLesson(params.slug, fetch);
	return { lesson };
};
