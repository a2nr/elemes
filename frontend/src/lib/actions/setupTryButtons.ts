export function setupTryButtons(container: HTMLElement, callback: (code: string, lang: string) => void) {
	// Function to apply buttons
	const applyButtons = () => {
		container.querySelectorAll('pre code').forEach((block) => {
			const pre = block.parentElement;
			if (!pre) return;
			
			// Don't add if already added
			if (pre.querySelector('.btn-try')) return;

			let lang = '';
			const classes = Array.from(block.classList);
			
			// Strictly follow the language tag provided in markdown fences
			// highlight.js adds 'language-xxxx' class based on the fence tag
			if (classes.includes('language-c')) {
				lang = 'c';
			} else if (classes.includes('language-python')) {
				lang = 'python';
			} else if (classes.some(c => ['language-cpp', 'language-arduino', 'language-ino'].includes(c))) {
				lang = 'cpp';
			}
			
			// If no specific language class is found, we don't add the button.
			// This allows teachers to hide the button by using generic code blocks (```) 
			// or inline code which doesn't get these classes.

			if (lang) {
				const btn = document.createElement('button');
				btn.className = 'btn btn-try';
				btn.textContent = 'Coba ▶';
				btn.onclick = () => {
					callback(block.textContent || '', lang);
				};
				
				pre.style.position = 'relative';
				pre.appendChild(btn);
			}
		});
	};

	applyButtons();

	return {
		update(newCallback: (code: string, lang: string) => void) {
			callback = newCallback;
			applyButtons();
		},
		destroy() {}
	};
}
