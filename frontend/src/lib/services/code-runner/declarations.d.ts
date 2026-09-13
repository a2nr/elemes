declare module '@micropython/micropython-webassembly-pyscript' {
	export function loadMicroPython(options?: any): Promise<any>;
}

declare module '$lib/vendor/picoc.js' {
	export const picoc: any;
	export const runC: any;
}

declare module '*?worker' {
	const workerConstructor: {
		new (): Worker;
	};
	export default workerConstructor;
}

declare module '*?url' {
	const url: string;
	export default url;
}

