import {
    Alert,
    Button,
    Center,
    Group,
    Loader,
    Tabs,
    Text,
} from '@mantine/core';
import { useEffect, useState } from 'react';

import { getBalances, type Balance } from '../api/balances';
import { peopleOnSide, type Side } from '../lib/people';
import { PersonRow } from './PersonRow';

interface DebtsListProps {
    defaultCurrency: string;
    onAddEntry?: () => void;
}

export function DebtsList({ defaultCurrency, onAddEntry }: DebtsListProps) {
    const [balances, setBalances] = useState<Balance[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [side, setSide] = useState<Side>('debtors');

    useEffect(() => {
        let cancelled = false;
        getBalances()
            .then((data) => !cancelled && setBalances(data))
            .catch(() => !cancelled && setError('Could not load balances.'));
        return () => {
            cancelled = true;
        };
    }, []);

    const people = balances
        ? peopleOnSide(balances, side, defaultCurrency)
        : [];

    return (
        <>
            <Tabs
                value={side}
                onChange={(value) => value && setSide(value as Side)}
            >
                <Group
                    justify='space-between'
                    align='end'
                    style={{
                        borderBottom: '1px solid var(--mantine-color-gray-3)',
                    }}
                >
                    <Tabs.List style={{ border: 0 }} mb={-1}>
                        <Tabs.Tab value='debtors' fz='md' py='md'>
                            Your debtors
                        </Tabs.Tab>
                        <Tabs.Tab value='debts' fz='md' py='md'>
                            Your debts
                        </Tabs.Tab>
                    </Tabs.List>
                    <Button mb='xs' onClick={onAddEntry}>
                        Add entry
                    </Button>
                </Group>
            </Tabs>

            {error ? (
                <Alert color='red' variant='light' mt='md'>
                    {error}
                </Alert>
            ) : balances === null ? (
                <Center py={48}>
                    <Loader size='sm' />
                </Center>
            ) : people.length === 0 ? (
                <Text c='dimmed' ta='center' py={48}>
                    {side === 'debtors'
                        ? 'Nobody owes you anything.'
                        : 'You do not owe anyone anything.'}
                </Text>
            ) : (
                people.map((person) => (
                    <PersonRow key={person.accountId} person={person} />
                ))
            )}
        </>
    );
}
