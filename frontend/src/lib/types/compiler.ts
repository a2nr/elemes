export interface CompileRequest {
	code: string;
	language: string;
}

export interface CompileResponse {
	success: boolean;
	output: string;
	error: string;
}
