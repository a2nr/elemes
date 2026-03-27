import { getLesson } from '$services/api';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch }) => {
	const token = typeof window !== 'undefined'
		? localStorage.getItem('student_token') ?? ''
		: '';
	const lesson = await getLesson(params.slug, fetch, token);
	return { lesson };
};
