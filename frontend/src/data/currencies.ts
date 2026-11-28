import currencies from './currencies.json';

export interface Currency {
    code: string;
    name: string;
    minor_units: number;
}

export const CURRENCIES: Currency[] = currencies;

export const CURRENCY_OPTIONS = CURRENCIES.map(({ code, name }) => ({
    value: code,
    label: `${code} - ${name}`,
}));
