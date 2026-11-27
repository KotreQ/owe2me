import { useDisclosure } from '@mantine/hooks';
import { useState } from 'react';

import { logout, type Me } from './api/auth';
import { Navbar } from './components/Navbar';
import { SignupModal } from './components/SignupModal';

export default function App() {
    const [user, setUser] = useState<Me | null>(null);
    const [signupOpened, signup] = useDisclosure(false);

    const handleLogout = async () => {
        try {
            await logout();
        } finally {
            setUser(null);
        }
    };

    return (
        <>
            <Navbar
                user={user}
                onSignup={signup.open}
                onLogout={handleLogout}
            />
            <SignupModal
                opened={signupOpened}
                onClose={signup.close}
                onSuccess={(me) => {
                    setUser(me);
                    signup.close();
                }}
            />
        </>
    );
}
