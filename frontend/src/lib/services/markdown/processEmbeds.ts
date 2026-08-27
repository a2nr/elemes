// Polyfill markAsUncloneable on node:worker_threads for Node 20 runtime compatibility (undici/jsdom)
try {
	// eslint-disable-next-line @typescript-eslint/no-require-imports
	const wt = require('node:worker_threads');
	if (wt && typeof wt.markAsUncloneable === 'undefined') {
		wt.markAsUncloneable = () => {};
	}
} catch {
	// ignore
}

import DOMPurify from 'isomorphic-dompurify';

/**
 * Escape HTML characters to prevent XSS in data embeds.
 */
function escapeHtml(unsafe: string): string {
	return unsafe
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#039;');
}

/**
 * Replace ```circuit[,width][,height] code fences with embeddable HTML divs.
 */
export function processCircuitEmbeds(text: string): string {
	const pattern = /```circuit(?:,([^\s,`]+))?(?:,([^\s,`]+))?\s*\n([\s\S]*?)```/g;
	return text.replace(pattern, (_, p1, p2, content) => {
		let width = '100%';
		let height = '400px';
		if (p1 && p2) {
			width = p1;
			height = p2;
		} else if (p1) {
			height = p1;
		}
		const escapedData = escapeHtml(content.trim());
		return (
			`<div class="circuit-embed" ` +
			`data-width="${escapeHtml(width)}" ` +
			`data-height="${escapeHtml(height)}">` +
			`<pre class="circuit-data" style="display:none">${escapedData}</pre>` +
			`<div class="circuit-embed-loading">Memuat simulator...</div>` +
			`</div>`
		);
	});
}

/**
 * Replace ```flowchart[,width][,height] code fences with embeddable HTML divs.
 */
export function processFlowchartEmbeds(text: string): string {
	const pattern = /```flowchart(?:,([^\s,`]+))?(?:,([^\s,`]+))?\s*\n([\s\S]*?)```/g;
	return text.replace(pattern, (_, p1, p2, content) => {
		let width = '100%';
		let height = '400px';
		if (p1 && p2) {
			width = p1;
			height = p2;
		} else if (p1) {
			height = p1;
		}
		const escapedData = escapeHtml(content.trim());
		return (
			`<div class="flowchart-embed" ` +
			`data-width="${escapeHtml(width)}" ` +
			`data-height="${escapeHtml(height)}">` +
			`<pre class="flowchart-data" style="display:none">${escapedData}</pre>` +
			`<div class="flowchart-embed-loading">Memuat flowchart...</div>` +
			`</div>`
		);
	});
}

const ALLOWED_TAGS = ['div', 'iframe', 'a', 'span', 'p', 'br', 'img'];
const ALLOWED_ATTR = [
	'style',
	'class',
	'src',
	'loading',
	'allowfullscreen',
	'allow',
	'title',
	'href',
	'target',
	'rel',
	'alt',
	'width',
	'height'
];

const SAFE_URI_REGEXP = /^https:\/\//i;

const ALLOWED_STYLE_PROPS = new Set([
	'position',
	'width',
	'height',
	'padding',
	'padding-top',
	'padding-bottom',
	'padding-left',
	'padding-right',
	'margin',
	'margin-top',
	'margin-bottom',
	'margin-left',
	'margin-right',
	'border',
	'border-radius',
	'overflow',
	'box-shadow',
	'top',
	'left',
	'right',
	'bottom',
	'will-change',
	'display',
	'flex-direction',
	'gap',
	'max-width',
	'max-height',
	'min-height'
]);

const BLOCKED_HOSTS = new Set([
	'localhost',
	'127.0.0.1',
	'0.0.0.0',
	'metadata.google.internal',
	'169.254.169.254'
]);

function isBlockedHost(hostname: string): boolean {
	const h = hostname.toLowerCase();
	return BLOCKED_HOSTS.has(h) || Array.from(BLOCKED_HOSTS).some((bh) => h.endsWith('.' + bh));
}

// Hook: filter properti CSS yang tidak di-whitelist di dalam atribut style
DOMPurify.addHook('uponSanitizeAttribute', (_node, data) => {
	if (data.attrName === 'style') {
		const clean = data.attrValue
			.split(';')
			.map((s) => s.trim())
			.filter(Boolean)
			.filter((s) => {
				const prop = s.split(':')[0]?.trim().toLowerCase();
				return prop && ALLOWED_STYLE_PROPS.has(prop);
			});
		data.attrValue = clean.join('; ');
	}
});

// Hook: buang iframe/a/img yang src atau hrefnya bukan https atau host-nya diblokir
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
	const el = node as Element;
	const tag = el.tagName?.toLowerCase();
	if (tag !== 'iframe' && tag !== 'a' && tag !== 'img') return;
	const attr = tag === 'a' ? 'href' : 'src';
	const val = el.getAttribute(attr);
	if (!val) {
		if (tag === 'iframe' || tag === 'img') {
			el.remove();
		}
		return;
	}
	try {
		const url = new URL(val);
		if (url.protocol !== 'https:' || isBlockedHost(url.hostname)) {
			el.remove();
		}
	} catch {
		el.remove(); // URL relatif/tidak valid untuk embed pihak-ketiga -> buang
	}
});

/**
 * Sanitize raw embed HTML using isomorphic-dompurify.
 */
function sanitizeEmbedHtml(htmlText: string): string {
	return DOMPurify.sanitize(htmlText, {
		ALLOWED_TAGS,
		ALLOWED_ATTR,
		ADD_ATTR: ['target', 'rel'],
		ALLOWED_URI_REGEXP: SAFE_URI_REGEXP
	});
}

/**
 * Replace ```embed fences containing raw HTML embed code with sanitized HTML.
 */
export function processEmbedEmbeds(text: string): string {
	const pattern = /```embed\s*\n([\s\S]*?)```/g;
	return text.replace(pattern, (_, rawHtml) => {
		const trimmed = rawHtml.trim();
		if (!trimmed) {
			return '<div class="embed-error">Konten embed kosong.</div>';
		}
		const sanitized = sanitizeEmbedHtml(trimmed);
		const textContent = sanitized.replace(/<[^>]*>/g, '').trim();
		const hasMedia = /<(?:iframe|img|a\s+href)/i.test(sanitized);
		if (!textContent && !hasMedia) {
			return '<div class="embed-error">Konten embed ditolak.</div>';
		}
		return sanitized;
	});
}
