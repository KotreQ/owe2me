import {
    Alert,
    Anchor,
    Button,
    Modal,
    PasswordInput,
    Stack,
    Text,
    TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useState } from 'react';

import { login, type Me } from '../api/auth';
import { ApiError } from '../api/client';

interface LoginModalProps {
    opened: boolean;
    onClose: () => void;
    onSuccess: (user: Me) => void;
    onSwitchToSignup: () => void;
}

export function LoginModal({
    opened,
    onClose,
    onSuccess,
    onSwitchToSignup,
}: LoginModalProps) {
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const form = useForm({
        initialValues: { username: '', password: '' },
        validateInputOnBlur: true,
        transformValues: (values) => ({
            ...values,
            username: values.username.trim().toLowerCase(),
        }),
        validate: {
            username: (value) => (value.trim() ? null : 'Enter your username'),
            password: (value) => (value ? null : 'Enter your password'),
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
        onSwitchToSignup();
    };

    const handleSubmit = form.onSubmit(async (values) => {
        setSubmitting(true);
        setError(null);
        try {
            const user = await login(values);
            form.reset();
            onSuccess(user);
        } catch (err) {
            setError(
                err instanceof ApiError
                    ? err.message
                    : 'Something went wrong. Try again.',
            );
        } finally {
            setSubmitting(false);
        }
    });

    return (
        <Modal opened={opened} onClose={handleClose} title='Log in' centered>
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
                        autoComplete='current-password'
                        {...form.getInputProps('password')}
                    />

                    {error && (
                        <Alert color='red' variant='light'>
                            {error}
                        </Alert>
                    )}

                    <Button type='submit' loading={submitting} fullWidth>
                        Log in
                    </Button>

                    <Text size='sm' ta='center'>
                        Don't have an account?{' '}
                        <Anchor
                            component='button'
                            type='button'
                            onClick={handleSwitch}
                        >
                            Sign up
                        </Anchor>
                    </Text>
                </Stack>
            </form>
        </Modal>
    );
}
