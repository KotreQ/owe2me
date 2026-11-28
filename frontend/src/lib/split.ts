export function sum(values: number[]): number {
    return values.reduce((total, value) => total + value, 0);
}

export function splitEqual(total: number, parts: number): number[] {
    const base = Math.floor(total / parts);
    const remainder = total - base * parts;
    return Array.from(
        { length: parts },
        (_, index) => base + (index < remainder ? 1 : 0),
    );
}

export function splitByPercent(total: number, percents: number[]): number[] {
    const basisPoints = percents.map((percent) => Math.round(percent * 100));
    const shares = basisPoints.map((bp) => Math.floor((total * bp) / 10000));
    const fractions = basisPoints.map((bp) => (total * bp) % 10000);

    let remainder = total - sum(shares);
    const byFraction = fractions
        .map((fraction, index) => ({ fraction, index }))
        .sort((a, b) => b.fraction - a.fraction || a.index - b.index);

    for (const { index } of byFraction) {
        if (remainder <= 0) break;
        shares[index] += 1;
        remainder -= 1;
    }
    return shares;
}

export function percentsAddUp(percents: number[]): boolean {
    return sum(percents.map((percent) => Math.round(percent * 100))) === 10000;
}
