import { apiGet } from './client';

export interface Balance {
    account_id: number;
    display_name: string;
    kind: 'user' | 'local';
    currency: string;
    net_minor: number;
}

export function getBalances(): Promise<Balance[]> {
    return apiGet<Balance[]>('/balances');
}
