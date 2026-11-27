import currencies from './currencies.json';

export interface Currency {
    code: string;
    name: string;
    minor_units: number;
}

export const CURRENCIES: Currency[] = currencies;
