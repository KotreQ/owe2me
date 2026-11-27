import { CURRENCIES } from '../data/currencies';

export function formatMoney(
    minor: number,
    currency: string,
    { sign = false }: { sign?: boolean } = {},
): string {
    const units = CURRENCIES.find((c) => c.code === currency)?.minor_units ?? 2;
    const value = Math.abs(minor) / 10 ** units;
    const text = value.toLocaleString('en-US', {
        minimumFractionDigits: Number.isInteger(value) ? 0 : units,
        maximumFractionDigits: units,
    });
    const prefix = minor < 0 ? '-' : sign && minor > 0 ? '+' : '';
    return `${prefix}${text} ${currency}`;
}

export function toMinorUnits(value: number, currency: string): number {
    const units = CURRENCIES.find((c) => c.code === currency)?.minor_units ?? 2;
    return Math.round(value * 10 ** units);
}
