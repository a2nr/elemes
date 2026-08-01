export interface CompileRequest {
	code: string;
	language: string;
	token?: string;
	stdin?: string;
}

export interface CompileResponse {
	success: boolean;
	output: string;
	error: string;
}
