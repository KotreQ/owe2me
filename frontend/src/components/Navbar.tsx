import {
    Box,
    Button,
    Container,
    Group,
    Image,
    Menu,
    Text,
    UnstyledButton,
} from '@mantine/core';
import { IconChevronDown, IconLogout } from '@tabler/icons-react';

import type { Me } from '../api/auth';
import logo from '../assets/logo.svg';

interface NavbarProps {
    user?: Me | null;
    onLogin?: () => void;
    onSignup?: () => void;
    onLogout?: () => void;
}

export function Navbar({ user, onLogin, onSignup, onLogout }: NavbarProps) {
    return (
        <Box component='header' py='md'>
            <Container size={1000}>
                <Group justify='space-between'>
                    <Image src={logo} alt='owe2me' h={16} w='auto' />

                    {user ? (
                        <Menu
                            position='bottom-end'
                            width={160}
                            styles={{ dropdown: { border: 'none' } }}
                        >
                            <Menu.Target>
                                <UnstyledButton style={{ cursor: 'pointer' }}>
                                    <Group gap={4}>
                                        <Text fw={500}>{user.username}</Text>
                                        <IconChevronDown size={16} />
                                    </Group>
                                </UnstyledButton>
                            </Menu.Target>

                            <Menu.Dropdown>
                                <Menu.Item
                                    leftSection={<IconLogout size={16} />}
                                    onClick={onLogout}
                                >
                                    Log out
                                </Menu.Item>
                            </Menu.Dropdown>
                        </Menu>
                    ) : (
                        <Group gap='xs'>
                            <Button
                                variant='transparent'
                                c='black'
                                onClick={onSignup}
                            >
                                Sign up
                            </Button>
                            <Button onClick={onLogin}>Log in</Button>
                        </Group>
                    )}
                </Group>
            </Container>
        </Box>
    );
}
