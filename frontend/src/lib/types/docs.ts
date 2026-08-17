export interface DocsIndexEntry {
	slug: string;
	title: string;
	order: number;
	category: string;
}

export interface DocContent {
	title: string;
	order: number;
	category: string;
	html: string;
}

export interface DocMeta {
	title: string;
	order: number;
	category: string;
}

/** Satu entry dari GET /api/docs/api-reference. */
export interface ApiReferenceEntry {
	method: string[];
	path: string;
	name: string;
	auth: boolean;
	doc: string;
}

export interface ApiReferenceResponse {
	endpoints: ApiReferenceEntry[];
}
