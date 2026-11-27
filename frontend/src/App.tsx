import { useDisclosure } from '@mantine/hooks';
import { useEffect, useState } from 'react';

import { logout, me, type Me } from './api/auth';
import { LoginModal } from './components/LoginModal';
import { Navbar } from './components/Navbar';
import { SignupModal } from './components/SignupModal';

export default function App() {
    const [user, setUser] = useState<Me | null>(null);
    const [loading, setLoading] = useState(true);
    const [loginOpened, login] = useDisclosure(false);
    const [signupOpened, signup] = useDisclosure(false);

    // Restore the session after a page refresh. A 401 just means nobody is logged in.
    useEffect(() => {
        let cancelled = false;
        me()
            .then((current) => !cancelled && setUser(current))
            .catch(() => !cancelled && setUser(null))
            .finally(() => !cancelled && setLoading(false));
        return () => {
            cancelled = true;
        };
    }, []);

    const handleLogout = async () => {
        try {
            await logout();
        } finally {
            setUser(null);
        }
    };

    const handleAuthSuccess = (current: Me) => {
        setUser(current);
        login.close();
        signup.close();
    };

    return (
        <>
            <Navbar
                user={user}
                loading={loading}
                onLogin={login.open}
                onSignup={signup.open}
                onLogout={handleLogout}
            />
            <LoginModal
                opened={loginOpened}
                onClose={login.close}
                onSuccess={handleAuthSuccess}
                onSwitchToSignup={() => {
                    login.close();
                    signup.open();
                }}
            />
            <SignupModal
                opened={signupOpened}
                onClose={signup.close}
                onSuccess={handleAuthSuccess}
                onSwitchToLogin={() => {
                    signup.close();
                    login.open();
                }}
            />
        </>
    );
}
