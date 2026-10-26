import LoginForm from '@/components/auth/login-form';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Login',
  robots: 'noindex, nofollow',
};

function LoginPage() {
  return <LoginForm onSuccess={() => {}} />;
}

export default LoginPage;
