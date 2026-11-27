import { Box, Button, Container, Group, Image } from '@mantine/core';

import logo from '../assets/logo.svg';

interface NavbarProps {
    onLogin?: () => void;
    onSignup?: () => void;
}

export function Navbar({ onLogin, onSignup }: NavbarProps) {
    return (
        <Box component='header' py='md'>
            <Container size={1000}>
                <Group justify='space-between'>
                    <Image src={logo} alt='owe2me' h={16} w='auto' />

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
                </Group>
            </Container>
        </Box>
    );
}
