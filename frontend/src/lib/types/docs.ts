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
