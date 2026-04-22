export interface CompileRequest {
	code: string;
	language: string;
	token?: string;
}

export interface CompileResponse {
	success: boolean;
	output: string;
	error: string;
}
