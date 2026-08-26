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

/**
 * Sanitize raw embed HTML: whitelist tags/attrs/styles + check iframe src domain.
 * Replicates Python's bleach configuration using native DOMParser in the browser.
 */
function sanitizeEmbedHtml(htmlText: string): string {
	if (typeof window === 'undefined') {
		return htmlText;
	}

	const parser = new DOMParser();
	const doc = parser.parseFromString(htmlText, 'text/html');
	const body = doc.body;

	const allowedTags = new Set(['div', 'iframe', 'a', 'span', 'p', 'br', 'img']);
	const allowedAttrs: Record<string, string[]> = {
		div: ['style', 'class'],
		iframe: ['src', 'style', 'loading', 'allowfullscreen', 'allow', 'title', 'class'],
		a: ['href', 'target', 'rel', 'style', 'class'],
		span: ['style', 'class'],
		p: ['style', 'class'],
		img: ['src', 'alt', 'style', 'class', 'loading']
	};

	const allowedStyles = new Set([
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

	const blockedHosts = new Set([
		'localhost',
		'127.0.0.1',
		'0.0.0.0',
		'metadata.google.internal',
		'169.254.169.254'
	]);

	function sanitize(node: Node): Node | null {
		if (node.nodeType === Node.TEXT_NODE) {
			return node.cloneNode(true);
		}
		if (node.nodeType !== Node.ELEMENT_NODE) {
			return null;
		}

		const el = node as HTMLElement;
		const tagName = el.tagName.toLowerCase();

		if (!allowedTags.has(tagName)) {
			// Strip the tag but sanitize and keep its children
			const fragment = doc.createDocumentFragment();
			for (let i = 0; i < el.childNodes.length; i++) {
				const child = sanitize(el.childNodes[i]);
				if (child) fragment.appendChild(child);
			}
			return fragment;
		}

		const newEl = doc.createElement(tagName);

		// Copy allowed attributes
		const attrs = allowedAttrs[tagName] || [];
		for (let i = 0; i < el.attributes.length; i++) {
			const attr = el.attributes[i];
			const attrName = attr.name.toLowerCase();

			if (attrs.includes(attrName) || attrName === 'class') {
				let val = attr.value;
				if (tagName === 'iframe' && attrName === 'src') {
					try {
						const url = new URL(val);
						if (url.protocol !== 'https:') {
							return doc.createTextNode('[Konten embed ditolak: iframe harus https]');
						}
						const hostname = url.hostname.toLowerCase();
						if (
							blockedHosts.has(hostname) ||
							Array.from(blockedHosts).some((bh) => hostname.endsWith('.' + bh))
						) {
							return doc.createTextNode('[Konten embed ditolak: domain iframe diblokir]');
						}
					} catch {
						if (!val.startsWith('https://')) {
							return doc.createTextNode('[Konten embed ditolak: iframe harus https]');
						}
						return doc.createTextNode('[Konten embed ditolak: URL iframe tidak valid]');
					}
				}
				if (attrName === 'style') {
					const inlineStyles = val.split(';');
					const cleanStyles: string[] = [];
					for (const style of inlineStyles) {
						const parts = style.split(':');
						if (parts.length === 2) {
							const prop = parts[0].trim().toLowerCase();
							if (allowedStyles.has(prop)) {
								cleanStyles.push(`${prop}: ${parts[1].trim()}`);
							}
						}
					}
					val = cleanStyles.join('; ');
				}
				newEl.setAttribute(attrName, val);
			}
		}

		// Process children
		for (let i = 0; i < el.childNodes.length; i++) {
			const child = sanitize(el.childNodes[i]);
			if (child) {
				newEl.appendChild(child);
			}
		}

		return newEl;
	}

	const resultFragment = doc.createDocumentFragment();
	for (let i = 0; i < body.childNodes.length; i++) {
		const child = sanitize(body.childNodes[i]);
		if (child) {
			resultFragment.appendChild(child);
		}
	}

	const tempDiv = doc.createElement('div');
	tempDiv.appendChild(resultFragment);
	return tempDiv.innerHTML;
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
		if (sanitized.includes('[Konten embed ditolak')) {
			return `<div class="embed-error">${sanitized.replace(/[\[\]]/g, '')}</div>`;
		}
		return sanitized;
	});
}
