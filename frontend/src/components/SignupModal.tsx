import {
    Alert,
    Anchor,
    Button,
    Modal,
    PasswordInput,
    Select,
    Stack,
    Text,
    TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useState } from 'react';

import { signup, type Me } from '../api/auth';
import { ApiError } from '../api/client';
import { CURRENCIES } from '../data/currencies';

const USERNAME_PATTERN = /^[a-z0-9_.-]{3,50}$/;
const PASSWORD_MIN = 8;
const PASSWORD_MAX = 128;

const CURRENCY_OPTIONS = CURRENCIES.map(({ code, name }) => ({
    value: code,
    label: `${code} - ${name}`,
}));

interface SignupModalProps {
    opened: boolean;
    onClose: () => void;
    onSuccess: (user: Me) => void;
    onSwitchToLogin: () => void;
}

export function SignupModal({
    opened,
    onClose,
    onSuccess,
    onSwitchToLogin,
}: SignupModalProps) {
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const form = useForm({
        initialValues: {
            username: '',
            password: '',
            repeatPassword: '',
            default_currency: null as string | null,
        },
        validateInputOnBlur: true,
        transformValues: (values) => ({
            ...values,
            username: values.username.trim().toLowerCase(),
            default_currency: values.default_currency ?? '',
        }),
        validate: {
            username: (value) =>
                USERNAME_PATTERN.test(value.trim().toLowerCase())
                    ? null
                    : '3-50 characters: letters, digits, dot, dash or underscore',
            password: (value) =>
                value.length >= PASSWORD_MIN && value.length <= PASSWORD_MAX
                    ? null
                    : `Password must be minimum ${PASSWORD_MIN} characters`,
            repeatPassword: (value, values) =>
                value === values.password ? null : 'Passwords do not match',
            default_currency: (value) =>
                CURRENCIES.some((c) => c.code === value)
                    ? null
                    : 'Select a currency',
        },
    });

    const handleClose = () => {
        form.reset();
        setError(null);
        onClose();
    };

    const handleSwitch = () => {
        form.reset();
        setError(null);
        onSwitchToLogin();
    };

    const handleSubmit = form.onSubmit(
        async ({ username, password, default_currency }) => {
            setSubmitting(true);
            setError(null);
            try {
                const user = await signup({
                    username,
                    password,
                    default_currency,
                });
                form.reset();
                onSuccess(user);
            } catch (err) {
                if (err instanceof ApiError && err.status === 409) {
                    form.setFieldError(
                        'username',
                        'This username is already taken',
                    );
                } else {
                    setError(
                        err instanceof ApiError
                            ? err.message
                            : 'Something went wrong. Try again.',
                    );
                }
            } finally {
                setSubmitting(false);
            }
        },
    );

    return (
        <Modal
            opened={opened}
            onClose={handleClose}
            title='Create account'
            centered
        >
            <form onSubmit={handleSubmit} noValidate>
                <Stack>
                    <TextInput
                        label='Username'
                        autoComplete='username'
                        data-autofocus
                        {...form.getInputProps('username')}
                    />
                    <PasswordInput
                        label='Password'
                        autoComplete='new-password'
                        {...form.getInputProps('password')}
                    />
                    <PasswordInput
                        label='Repeat password'
                        autoComplete='new-password'
                        {...form.getInputProps('repeatPassword')}
                    />
                    <Select
                        label='Default currency'
                        placeholder='Select currency'
                        data={CURRENCY_OPTIONS}
                        searchable
                        allowDeselect={false}
                        {...form.getInputProps('default_currency')}
                    />

                    {error && (
                        <Alert color='red' variant='light'>
                            {error}
                        </Alert>
                    )}

                    <Button type='submit' loading={submitting} fullWidth>
                        Create account
                    </Button>

                    <Text size='sm' ta='center'>
                        Already have an account?{' '}
                        <Anchor component='button' type='button' onClick={handleSwitch}>
                            Log in
                        </Anchor>
                    </Text>
                </Stack>
            </form>
        </Modal>
    );
}
