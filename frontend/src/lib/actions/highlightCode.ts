import hljs from 'highlight.js/lib/core';
import c from 'highlight.js/lib/languages/c';
import python from 'highlight.js/lib/languages/python';

hljs.registerLanguage('c', c);
hljs.registerLanguage('python', python);

export function highlightAllCode(container: HTMLElement) {
	container.querySelectorAll('pre code').forEach((block) => {
		if (!(block as HTMLElement).dataset.highlighted) {
			hljs.highlightElement(block as HTMLElement);
		}
	});
}
