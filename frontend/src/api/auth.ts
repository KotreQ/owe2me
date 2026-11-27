import { apiGet, apiPost } from './client';

export interface SignupRequest {
    username: string;
    password: string;
    default_currency: string;
}

export interface LoginRequest {
    username: string;
    password: string;
}

export interface Me {
    account_id: number;
    username: string;
    display_name: string;
    default_currency: string;
}

export function signup(body: SignupRequest): Promise<Me> {
    return apiPost<Me>('/auth/signup', body);
}

export function login(body: LoginRequest): Promise<Me> {
    return apiPost<Me>('/auth/login', body);
}

export function me(): Promise<Me> {
    return apiGet<Me>('/auth/me');
}

export async function logout(): Promise<void> {
    await apiPost<void>('/auth/logout', undefined);
}
