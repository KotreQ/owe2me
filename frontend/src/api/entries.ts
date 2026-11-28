import { apiPost } from './client';

export interface CreateEntryRequest {
    payer_account_id: number;
    payee_account_id: number;
    kind: 'debt' | 'payment';
    amount_minor: number;
    currency: string;
    title: string;
}

export class CreateEntriesError extends Error {
    created: number;
    total: number;

    constructor(created: number, total: number, message: string) {
        super(message);
        this.created = created;
        this.total = total;
    }
}

export async function createEntries(
    requests: CreateEntryRequest[],
): Promise<void> {
    let created = 0;
    for (const request of requests) {
        try {
            await apiPost<unknown>('/entries', request);
            created += 1;
        } catch (err) {
            throw new CreateEntriesError(
                created,
                requests.length,
                err instanceof Error ? err.message : 'Request failed',
            );
        }
    }
}
