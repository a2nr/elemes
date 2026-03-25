export interface AuthState {
	token: string;
	studentName: string;
	isLoggedIn: boolean;
}

export interface LoginResponse {
	success: boolean;
	student_name?: string;
	message: string;
}

export interface ValidateTokenResponse {
	success: boolean;
	student_name?: string;
	message?: string;
}
