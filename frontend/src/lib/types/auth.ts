export interface AuthState {
	token: string;
	studentName: string;
	isLoggedIn: boolean;
}

export interface LoginResponse {
	success: boolean;
	student_name?: string;
	is_teacher?: boolean;
	message: string;
}

export interface ValidateTokenResponse {
	success: boolean;
	student_name?: string;
	is_teacher?: boolean;
	message?: string;
}
