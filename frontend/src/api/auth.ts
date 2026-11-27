import { apiPost } from './client';

export interface SignupRequest {
    username: string;
    password: string;
    default_currency: string;
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

export async function logout(): Promise<void> {
    await apiPost<void>('/auth/logout', undefined);
}
