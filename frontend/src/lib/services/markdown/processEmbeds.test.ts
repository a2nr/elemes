import { describe, it, expect } from 'vitest';
import { processEmbedEmbeds } from './processEmbeds';

describe('processEmbedEmbeds - keamanan & fungsionalitas', () => {
	it('should strip javascript: URI from <a href>', () => {
		const input = '```embed\n<a href="javascript:alert(1)">Klik</a>\n```';
		const out = processEmbedEmbeds(input);
		expect(out).not.toContain('javascript:');
		expect(out).not.toContain('alert(1)');
	});

	it('should strip data: URI from <a href>', () => {
		const input = '```embed\n<a href="data:text/html,<script>alert(1)</script>">Klik</a>\n```';
		const out = processEmbedEmbeds(input);
		expect(out).not.toContain('data:text/html');
		expect(out).not.toContain('alert(1)');
	});

	it('should strip javascript: URI from <img src>', () => {
		const input = '```embed\n<img src="javascript:alert(1)">\n```';
		const out = processEmbedEmbeds(input);
		expect(out).not.toContain('javascript:');
		expect(out).not.toContain('alert(1)');
	});

	it('should strip <script> tag and its content entirely', () => {
		const input = '```embed\n<div>hello<script>alert(document.cookie)</script>world</div>\n```';
		const out = processEmbedEmbeds(input);
		expect(out).not.toContain('<script>');
		expect(out).not.toContain('alert(document.cookie)');
		expect(out).toContain('hello');
		expect(out).toContain('world');
	});

	it('should strip onclick/onerror attributes', () => {
		const input = '```embed\n<div onclick="alert(1)"><img src="https://example.com/img.png" onerror="alert(2)"></div>\n```';
		const out = processEmbedEmbeds(input);
		expect(out).not.toContain('onclick');
		expect(out).not.toContain('onerror');
		expect(out).not.toContain('alert(1)');
		expect(out).not.toContain('alert(2)');
	});

	it('should reject blocked iframe hosts (SSRF-style)', () => {
		const input = '```embed\n<iframe src="https://169.254.169.254/latest/meta-data"></iframe>\n```';
		const out = processEmbedEmbeds(input);
		expect(out).not.toContain('169.254.169.254');
		expect(out).toContain('embed-error');
	});

	it('should reject blocked domain (localhost / metadata.google.internal)', () => {
		const input1 = '```embed\n<iframe src="https://localhost:8080/admin"></iframe>\n```';
		const out1 = processEmbedEmbeds(input1);
		expect(out1).not.toContain('localhost');
		expect(out1).toContain('embed-error');

		const input2 = '```embed\n<iframe src="https://metadata.google.internal/computeMetadata/v1/"></iframe>\n```';
		const out2 = processEmbedEmbeds(input2);
		expect(out2).not.toContain('metadata.google.internal');
		expect(out2).toContain('embed-error');
	});

	it('should reject non-https iframe src', () => {
		const input = '```embed\n<iframe src="http://youtube.com/embed/x"></iframe>\n```';
		const out = processEmbedEmbeds(input);
		expect(out).not.toContain('<iframe');
		expect(out).toContain('embed-error');
	});

	it('should allow valid https embed (Canva/YouTube-style)', () => {
		const input = '```embed\n<iframe src="https://www.youtube.com/embed/xyz" allowfullscreen></iframe>\n```';
		const out = processEmbedEmbeds(input);
		expect(out).toContain('https://www.youtube.com/embed/xyz');
		expect(out).toContain('<iframe');
		expect(out).toContain('allowfullscreen');
	});

	it('should allow responsive Canva embed HTML', () => {
		const input = `\`\`\`embed
<div style="position: relative; width: 100%; padding-top: 56.25%;">
  <iframe loading="lazy" src="https://www.canva.com/design/ABC/view?embed" allowfullscreen></iframe>
</div>
\`\`\``;
		const out = processEmbedEmbeds(input);
		expect(out).toContain('canva.com');
		expect(out).toContain('<iframe');
		expect(out).toContain('allowfullscreen');
		expect(out).toContain('position: relative');
	});

	it('should strip dangerous style properties', () => {
		const input = '```embed\n<div style="background: url(\'javascript:alert(1)\'); width: 100%;"><iframe src="https://www.youtube.com/embed/x"></iframe></div>\n```';
		const out = processEmbedEmbeds(input);
		expect(out).not.toContain('javascript');
		expect(out).not.toContain('background');
		expect(out).toContain('width: 100%');
	});

	it('should return error div for empty embed', () => {
		const input = '```embed\n\n```';
		const out = processEmbedEmbeds(input);
		expect(out).toContain('embed-error');
		expect(out).toContain('kosong');
	});

	it('should leave non-embed markdown unchanged', () => {
		const md = '# Heading\n\nparagraf biasa';
		expect(processEmbedEmbeds(md)).toBe(md);
	});
});
