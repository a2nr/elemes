import { getLessons } from '$services/api';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const data = await getLessons(fetch);
	return {
		lessons: data.lessons ?? [],
		homeContent: data.home_content ?? ''
	};
};
