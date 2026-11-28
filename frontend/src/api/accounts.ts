import { ApiError, apiGet, apiPost } from './client';

export interface Account {
    account_id: number;
    kind: 'user' | 'local';
    display_name: string;
    username: string | null;
}

interface UserLookup {
    account_id: number;
    display_name: string;
    username: string;
}

export function getContacts(): Promise<Account[]> {
    return apiGet<Account[]>('/accounts');
}

export function createLocalAccount(displayName: string): Promise<Account> {
    return apiPost<Account>('/accounts/local', { display_name: displayName });
}

export async function findAccountByUsername(
    username: string,
): Promise<Account | null> {
    try {
        const found = await apiGet<UserLookup>(
            `/accounts/lookup?username=${encodeURIComponent(username)}`,
        );
        return { ...found, kind: 'user' };
    } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
            return null;
        }
        throw err;
    }
}
