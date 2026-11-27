import type { Balance } from '../api/balances';

export type Side = 'debtors' | 'debts';

export interface PersonBalance {
    accountId: number;
    name: string;
    isLocal: boolean;
    amounts: { currency: string; net_minor: number }[];
}

export function peopleOnSide(
    balances: Balance[],
    side: Side,
    defaultCurrency: string,
): PersonBalance[] {
    const people = new Map<number, PersonBalance>();

    for (const b of balances) {
        const onSide = side === 'debtors' ? b.net_minor > 0 : b.net_minor < 0;
        if (!onSide) continue;

        const person = people.get(b.account_id) ?? {
            accountId: b.account_id,
            name: b.display_name,
            isLocal: b.kind === 'local',
            amounts: [],
        };
        person.amounts.push({ currency: b.currency, net_minor: b.net_minor });
        people.set(b.account_id, person);
    }

    const rank = (currency: string) => (currency === defaultCurrency ? 0 : 1);
    for (const person of people.values()) {
        person.amounts.sort(
            (a, b) =>
                rank(a.currency) - rank(b.currency) ||
                a.currency.localeCompare(b.currency),
        );
    }
    return [...people.values()].sort((a, b) => a.name.localeCompare(b.name));
}
