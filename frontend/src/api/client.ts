export class ApiError extends Error {
    status: number;

    constructor(status: number, message: string) {
        super(message);
        this.status = status;
    }
}

function errorMessage(body: unknown, fallback: string): string {
    if (typeof body !== 'object' || body === null || !('detail' in body)) {
        return fallback;
    }
    const { detail } = body as { detail: unknown };
    if (typeof detail === 'string') {
        return detail;
    }
    if (Array.isArray(detail)) {
        return detail.map((item) => item?.msg ?? String(item)).join(', ');
    }
    return fallback;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`/api${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(body),
    });
    const data: unknown = await response.json().catch(() => null);

    if (!response.ok) {
        throw new ApiError(
            response.status,
            errorMessage(data, response.statusText),
        );
    }
    return data as T;
}
