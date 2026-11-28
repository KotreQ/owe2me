import {
    Alert,
    Button,
    Checkbox,
    Group,
    Loader,
    Modal,
    MultiSelect,
    NumberInput,
    Select,
    Stack,
    Text,
    TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useEffect, useRef, useState } from 'react';

import {
    createLocalAccount,
    findAccountByUsername,
    getContacts,
    type Account,
} from '../api/accounts';
import type { Me } from '../api/auth';
import { ApiError } from '../api/client';
import {
    CreateEntriesError,
    createEntries,
    type CreateEntryRequest,
} from '../api/entries';
import { CURRENCIES, CURRENCY_OPTIONS } from '../data/currencies';
import { formatMoney, toMinorUnits } from '../lib/money';
import { percentsAddUp, splitByPercent, splitEqual, sum } from '../lib/split';

type SplitMode = 'equal' | 'percent' | 'custom';
type ShareInputs = Record<string, number | string>;

const ME = 'me';
const TITLE_MAX = 120;
const USERNAME_MAX = 50;

const DIRECTION_OPTIONS = [
    { value: 'in', label: 'They owe me' },
    { value: 'out', label: 'I owe them' },
];

const SPLIT_OPTIONS = [
    { value: 'equal', label: 'Equally' },
    { value: 'percent', label: 'By percent' },
    { value: 'custom', label: 'Custom amounts' },
];

function computeShares(
    mode: SplitMode,
    total: number,
    participants: string[],
    inputs: ShareInputs,
    currency: string,
): number[] | null {
    if (mode === 'equal') {
        return splitEqual(total, participants.length);
    }
    if (mode === 'percent') {
        const percents = participants.map((id) => Number(inputs[id]) || 0);
        return percentsAddUp(percents) ? splitByPercent(total, percents) : null;
    }
    const amounts = participants.map((id) =>
        toMinorUnits(Number(inputs[id]) || 0, currency),
    );
    return sum(amounts) === total ? amounts : null;
}

interface AddEntryModalProps {
    opened: boolean;
    onClose: () => void;
    onCreated: () => void;
    user: Me;
}

export function AddEntryModal({
    opened,
    onClose,
    onCreated,
    user,
}: AddEntryModalProps) {
    const [contacts, setContacts] = useState<Account[]>([]);
    const [personSearch, setPersonSearch] = useState('');
    const [addingPerson, setAddingPerson] = useState(false);
    const [personNote, setPersonNote] = useState<string | null>(null);
    const [personError, setPersonError] = useState<string | null>(null);
    const [shareInputs, setShareInputs] = useState<ShareInputs>({});
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const form = useForm({
        initialValues: {
            direction: 'in',
            people: [] as string[],
            amount: '' as number | string,
            currency: user.default_currency as string | null,
            title: '',
            split: false,
            mode: 'equal' as SplitMode,
            includeMe: false,
        },
        validateInputOnBlur: true,
        onValuesChange: () => setError(null),
        validate: {
            people: (value) =>
                value.length > 0 ? null : 'Add at least one person',
            amount: (value) =>
                Number(value) > 0 ? null : 'Enter an amount greater than 0',
            currency: (value) =>
                CURRENCIES.some((c) => c.code === value)
                    ? null
                    : 'Select a currency',
            title: (value) => {
                const title = value.trim();
                if (!title) return 'Enter a title';
                return title.length <= TITLE_MAX
                    ? null
                    : `Title can have at most ${TITLE_MAX} characters`;
            },
        },
    });

    const openedRef = useRef(opened);
    const pendingPerson = useRef<Promise<void> | null>(null);

    useEffect(() => {
        openedRef.current = opened;
        if (!opened) return;
        let cancelled = false;
        getContacts()
            .then((data) => !cancelled && setContacts(data))
            .catch(() => !cancelled && setContacts([]));
        return () => {
            cancelled = true;
        };
    }, [opened]);

    const { values } = form;

    const derive = (v: typeof values) => {
        const entryCurrency = v.currency ?? user.default_currency;
        const amountMinor = toMinorUnits(Number(v.amount) || 0, entryCurrency);
        const split = v.split && v.people.length >= 2;
        const people = split
            ? [...v.people, ...(v.includeMe ? [ME] : [])]
            : v.people;
        const result =
            amountMinor > 0 && people.length > 0
                ? split
                    ? computeShares(
                          v.mode,
                          amountMinor,
                          people,
                          shareInputs,
                          entryCurrency,
                      )
                    : people.map(() => amountMinor)
                : null;
        return {
            currency: entryCurrency,
            total: amountMinor,
            splitActive: split,
            participants: people,
            shares: result,
        };
    };

    const { currency, total, splitActive, participants, shares } =
        derive(values);
    const units = CURRENCIES.find((c) => c.code === currency)?.minor_units ?? 2;

    const nameOf = (id: string) =>
        id === ME
            ? 'Me'
            : (contacts.find((c) => String(c.account_id) === id)?.display_name ?? id);

    const contactOptions = contacts.map((account) => ({
        value: String(account.account_id),
        label:
            account.kind === 'local'
                ? `${account.display_name} (local)`
                : account.display_name,
    }));

    const handleClose = () => {
        form.reset();
        setShareInputs({});
        setPersonSearch('');
        setPersonNote(null);
        setPersonError(null);
        setError(null);
        onClose();
    };

    const selectPerson = (account: Account) => {
        setContacts((current) =>
            current.some((c) => c.account_id === account.account_id)
                ? current
                : [...current, account],
        );
        const id = String(account.account_id);
        if (!form.getValues().people.includes(id)) {
            form.insertListItem('people', id);
        }
    };

    const resolvePerson = async (text: string) => {
        const wanted = text.trim();
        if (!wanted) return;
        setAddingPerson(true);
        setPersonNote(null);
        setPersonError(null);
        try {
            const lower = wanted.toLowerCase();
            const existing = contacts.find(
                (c) =>
                    c.display_name.toLowerCase() === lower ||
                    c.username?.toLowerCase() === lower,
            );
            if (existing) {
                selectPerson(existing);
            } else {
                const found =
                    lower.length <= USERNAME_MAX
                        ? await findAccountByUsername(lower)
                        : null;
                if (!openedRef.current) return;
                if (found) {
                    selectPerson(found);
                } else {
                    selectPerson(await createLocalAccount(wanted));
                    setPersonNote('Saved as a local contact.');
                }
            }
            setPersonSearch('');
        } catch (err) {
            setPersonSearch(wanted);
            setPersonError(
                err instanceof ApiError && err.status === 409
                    ? err.message
                    : 'Could not add this person. Try again.',
            );
        } finally {
            setAddingPerson(false);
        }
    };

    const handlePeopleBlur = (event: React.FocusEvent<HTMLInputElement>) => {
        const target = event.relatedTarget as HTMLElement | null;
        if (target?.closest('.mantine-Modal-close')) return;
        const text = personSearch.trim();
        if (!text) {
            form.validateField('people');
            return;
        }
        const task = resolvePerson(text).then(() => {
            form.validateField('people');
        });
        pendingPerson.current = task;
    };

    const splitProblem = (mode: SplitMode, amount: number, code: string) => {
        if (mode === 'percent') return 'Percentages must add up to 100.';
        return `Amounts must add up to ${formatMoney(amount, code)}.`;
    };

    const handleSubmit = form.onSubmit(async (submitted) => {
        setError(null);
        const latest = derive(submitted);
        if (!latest.shares) {
            setError(
                splitProblem(submitted.mode, latest.total, latest.currency),
            );
            return;
        }
        const latestShares = latest.shares;

        const requests: CreateEntryRequest[] = [];
        latest.participants.forEach((id, index) => {
            if (id === ME || latestShares[index] <= 0) return;
            const person = Number(id);
            const theyOweMe = submitted.direction === 'in';
            requests.push({
                payer_account_id: theyOweMe ? person : user.account_id,
                payee_account_id: theyOweMe ? user.account_id : person,
                kind: 'debt',
                amount_minor: latestShares[index],
                currency: latest.currency,
                title: submitted.title.trim(),
            });
        });
        if (requests.length === 0) {
            setError('Nothing to create. Check the amounts.');
            return;
        }

        setSubmitting(true);
        try {
            await createEntries(requests);
            onCreated();
            handleClose();
        } catch (err) {
            if (err instanceof CreateEntriesError) {
                if (err.created > 0) onCreated();
                setError(
                    err.created > 0
                        ? `Created ${err.created} of ${err.total} entries, then it failed: ${err.message}. Close this window and check the list.`
                        : err.message,
                );
            } else {
                setError('Something went wrong. Try again.');
            }
        } finally {
            setSubmitting(false);
        }
    });

    return (
        <Modal
            opened={opened}
            onClose={handleClose}
            title='Add entry'
            centered
        >
            <form
                onSubmit={async (event) => {
                    event.preventDefault();
                    await pendingPerson.current;
                    handleSubmit(event);
                }}
                noValidate
            >
                <Stack>
                    <TextInput
                        label='Title'
                        data-autofocus
                        {...form.getInputProps('title')}
                    />

                    <Select
                        label='Direction'
                        data={DIRECTION_OPTIONS}
                        allowDeselect={false}
                        {...form.getInputProps('direction')}
                    />

                    <MultiSelect
                        label='People'
                        placeholder='Type a username'
                        data={contactOptions}
                        searchable
                        searchValue={personSearch}
                        onSearchChange={(value) => {
                            setPersonSearch(value);
                            setPersonError(null);
                        }}
                        onKeyDown={(event) => {
                            if (event.key === 'Enter' && personSearch.trim()) {
                                event.preventDefault();
                            }
                        }}
                        rightSection={
                            addingPerson ? <Loader size='xs' /> : undefined
                        }
                        {...form.getInputProps('people')}
                        onBlur={handlePeopleBlur}
                        error={personError ?? form.errors.people}
                    />
                    {personNote && (
                        <Text size='sm' c='dimmed'>
                            {personNote}
                        </Text>
                    )}

                    <Group align='start' grow>
                        <NumberInput
                            label='Amount'
                            decimalScale={units}
                            allowNegative={false}
                            hideControls
                            {...form.getInputProps('amount')}
                        />
                        <Select
                            label='Currency'
                            data={CURRENCY_OPTIONS}
                            searchable
                            allowDeselect={false}
                            {...form.getInputProps('currency')}
                        />
                    </Group>

                    {values.people.length >= 2 && (
                        <Checkbox
                            label='Split amount between people'
                            {...form.getInputProps('split', {
                                type: 'checkbox',
                            })}
                        />
                    )}

                    {values.people.length >= 2 && !splitActive && total > 0 && (
                        <Text size='sm' c='dimmed'>
                            Each person will get an entry for{' '}
                            {formatMoney(total, currency)}.
                        </Text>
                    )}

                    {splitActive && (
                        <Stack gap='xs'>
                            <Select
                                label='Split'
                                data={SPLIT_OPTIONS}
                                allowDeselect={false}
                                {...form.getInputProps('mode')}
                            />
                            <Checkbox
                                label='Include me'
                                {...form.getInputProps('includeMe', {
                                    type: 'checkbox',
                                })}
                            />

                            {participants.map((id, index) => (
                                <Group key={id} justify='space-between'>
                                    <Text>{nameOf(id)}</Text>
                                    <Group gap='sm'>
                                        {values.mode !== 'equal' && (
                                            <NumberInput
                                                w={110}
                                                hideControls
                                                allowNegative={false}
                                                decimalScale={
                                                    values.mode === 'percent'
                                                        ? 2
                                                        : units
                                                }
                                                suffix={
                                                    values.mode === 'percent'
                                                        ? ' %'
                                                        : ` ${currency}`
                                                }
                                                value={shareInputs[id] ?? ''}
                                                onChange={(value) => {
                                                    setError(null);
                                                    setShareInputs(
                                                        (current) => ({
                                                            ...current,
                                                            [id]: value,
                                                        }),
                                                    );
                                                }}
                                            />
                                        )}
                                        {values.mode === 'equal' && shares && (
                                            <Text fw={500}>
                                                {formatMoney(
                                                    shares[index],
                                                    currency,
                                                )}
                                            </Text>
                                        )}
                                    </Group>
                                </Group>
                            ))}

                            {values.mode !== 'equal' &&
                                total > 0 &&
                                !shares &&
                                Object.keys(shareInputs).length > 0 && (
                                    <Text size='sm' c='red'>
                                        {splitProblem(
                                            values.mode,
                                            total,
                                            currency,
                                        )}
                                    </Text>
                                )}
                        </Stack>
                    )}

                    {error && (
                        <Alert color='red' variant='light'>
                            {error}
                        </Alert>
                    )}

                    <Button type='submit' loading={submitting} fullWidth>
                        Create entry
                    </Button>
                </Stack>
            </form>
        </Modal>
    );
}
