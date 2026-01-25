'use client';
import { useAnonymousAuth } from '@/components/anonymous-auth';
import {
  ResponsiveDialogDescription,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import GithubIcon from '@/components/icons/github-icon';
import GoogleIcon from '@/components/icons/google-icon';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { getUser } from '@/lib/firebase/firebase';
import { FirebaseError } from 'firebase/app';
import {
  EmailAuthProvider,
  GithubAuthProvider,
  GoogleAuthProvider,
  getAuth,
  linkWithCredential,
  linkWithPopup,
  signInWithCredential,
  signInWithEmailAndPassword,
} from 'firebase/auth';
import Link from 'next/link';
import { useState } from 'react';
import { toast } from 'sonner';
import PasswordResetForm from './password-reset-form';
import SuccessAuthForm from './success-auth-form';

type AuthProvider = 'google' | 'github' | 'email';

type Props = {
  onSuccess: () => void;
};

function LoginForm({ onSuccess }: Props) {
  const { refreshUser } = useAnonymousAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [isResetPassword, setIsResetPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [allowNewsletter, setAllowNewsletter] = useState(false);

  const handleAuthSuccess = async () => {
    await refreshUser();
    const uid = getAuth().currentUser?.uid;

    if (uid) {
      const user = await getUser(uid);

      if (user?.newsletter_allowed === undefined) {
        setAllowNewsletter(true);
        return;
      }
    }

    onSuccess();
    showSuccessToast();
  };

  const handleAuthError = (error: unknown, provider: AuthProvider) => {
    if (error instanceof FirebaseError) {
      if (error.code === 'auth/invalid-credential') {
        return toast.error('Die eingegebenen Daten sind ungültig.');
      }
      if (error.code === 'auth/credential-already-in-use') {
        return handleCredentialAlreadyInUse(error, provider);
      }
      if (error.code === 'auth/provider-already-linked') {
        return handleProviderAlreadyLinked();
      }
    }

    console.error(error);
    showErrorReloadToast();
  };

  const handleCredentialAlreadyInUse = async (
    error: FirebaseError,
    provider: AuthProvider,
  ) => {
    const auth = getAuth();

    let credential = null;
    if (provider === 'google') {
      credential = GoogleAuthProvider.credentialFromError(error);
    } else if (provider === 'github') {
      credential = GithubAuthProvider.credentialFromError(error);
    } else if (provider === 'email') {
      return;
    }

    if (!credential) {
      showErrorReloadToast();
      return;
    }

    try {
      await signInWithCredential(auth, credential);
      await handleAuthSuccess();
    } catch (signInError) {
      handleAuthError(signInError, provider);
    }
  };

  const handleProviderAlreadyLinked = async () => {
    const auth = getAuth();
    if (!auth.currentUser?.isAnonymous && auth.currentUser?.email) {
      await handleAuthSuccess();
      return;
    }
    showErrorReloadToast();
  };

  const handleLogin = async (email: string, password: string) => {
    const auth = getAuth();
    try {
      await signInWithEmailAndPassword(auth, email, password);
      await handleAuthSuccess();
    } catch (error) {
      handleAuthError(error, 'email');
    }
  };

  const handleRegister = async (email: string, password: string) => {
    const auth = getAuth();
    const user = auth.currentUser;

    if (!user) {
      showErrorReloadToast();
      return;
    }

    try {
      const credential = EmailAuthProvider.credential(email, password);
      await linkWithCredential(auth.currentUser, credential);
      await handleAuthSuccess();
    } catch (error) {
      handleAuthError(error, 'email');
    }
  };

  const handleOAuthLogin = async (
    provider: GoogleAuthProvider | GithubAuthProvider,
  ) => {
    const auth = getAuth();

    if (!auth.currentUser) {
      showErrorReloadToast();
      return;
    }

    try {
      const result = await linkWithPopup(auth.currentUser, provider);
      const credential =
        provider instanceof GoogleAuthProvider
          ? GoogleAuthProvider.credentialFromResult(result)
          : GithubAuthProvider.credentialFromResult(result);

      if (!credential) {
        showErrorReloadToast();
        return;
      }

      await linkWithCredential(auth.currentUser, credential);
      await handleAuthSuccess();
    } catch (error) {
      handleAuthError(
        error,
        provider instanceof GoogleAuthProvider ? 'google' : 'github',
      );
    }
  };

  const handleGoogleLogin = () => handleOAuthLogin(new GoogleAuthProvider());
  const handleGithubLogin = () => handleOAuthLogin(new GithubAuthProvider());

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.target as HTMLFormElement);
    const isRegister = formData.get('isRegister') === 'true';
    const email = formData.get('email') as string;
    const password = formData.get('password') as string;

    setIsLoading(true);

    if (isRegister) {
      await handleRegister(email, password);
    } else {
      await handleLogin(email, password);
    }

    setIsLoading(false);
  };

  const showErrorReloadToast = () => {
    toast.error(
      'Es ist ein Fehler aufgetreten. Bitte lade die Seite neu und versuche es erneut.',
    );
  };

  const showSuccessToast = () => {
    toast.success('Erfolgreich angemeldet');
  };

  const handleResetPassword = async () => {
    setIsResetPassword(true);
  };

  const handleChangeView = () => {
    setIsResetPassword(!isResetPassword);
  };

  if (isResetPassword) {
    return <PasswordResetForm onChangeView={handleChangeView} />;
  }

  if (allowNewsletter) {
    return <SuccessAuthForm onSuccess={onSuccess} />;
  }

  return (
    <form className="flex flex-col p-4 md:p-0" onSubmit={handleSubmit}>
      <input
        type="hidden"
        name="isRegister"
        value={isRegister ? 'true' : 'false'}
      />
      <div className="mb-4">
        <ResponsiveDialogTitle className="text-center text-2xl font-bold md:text-left">
          {isRegister ? 'Registrieren' : 'Anmelden'}
        </ResponsiveDialogTitle>
        <ResponsiveDialogDescription className="text-center text-sm text-muted-foreground md:text-left">
          {isRegister
            ? 'Du kannst dich bei wahl.chat registrieren um deine Chatverläufe zu speichern und mit mehreren Geräten abzurufen.'
            : 'Du kannst dich bei wahl.chat anmelden um deine Chatverläufe zu speichern und mit mehreren Geräten abzurufen.'}
        </ResponsiveDialogDescription>
      </div>

      <div className="flex flex-col">
        <div className="mt-4 grid gap-1">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            name="email"
            type="email"
            placeholder="max@mustermann.de"
            required
          />
        </div>
        <div className="my-4 grid gap-1">
          <div className="flex items-center">
            <Label htmlFor="password">Passwort</Label>
            <Button
              variant="link"
              className="ml-auto inline-block h-fit p-0 text-sm underline-offset-4 hover:underline"
              onClick={handleResetPassword}
              size="sm"
              type="button"
            >
              Passwort vergessen?
            </Button>
          </div>
          <Input
            id="password"
            type="password"
            name="password"
            required
            minLength={8}
            maxLength={30}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isRegister ? 'Registrieren' : 'Anmelden'}
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            Mit deinem Klick auf {isRegister ? 'Registrieren' : 'Anmelden'}{' '}
            akzeptierst du unsere{' '}
            <Link href="/datenschutz" target="_blank" className="underline">
              Datenschutzerklärung
            </Link>
            .
          </p>

          <div className="relative my-4 text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:flex after:items-center after:border-t after:border-border">
            <span className="relative z-10 bg-background px-2 text-muted-foreground">
              Oder nutze einen der folgenden Anbieter
            </span>
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Button
              variant="outline"
              className="flex items-center gap-2"
              disabled={isLoading}
              onClick={handleGoogleLogin}
              type="button"
            >
              <GoogleIcon className="!size-3" />
              Mit Google anmelden
            </Button>
            <Button
              variant="outline"
              className="flex items-center gap-2"
              disabled={isLoading}
              type="button"
              onClick={handleGithubLogin}
            >
              <GithubIcon className="!size-3" />
              Mit Github anmelden
            </Button>
          </div>
        </div>
      </div>
      <div className="mt-4 text-center text-sm">
        {isRegister ? 'Hast du schon einen Account?' : 'Noch keinen Account?'}{' '}
        <Button
          size="sm"
          type="button"
          variant="link"
          onClick={() => setIsRegister(!isRegister)}
          className="p-0 underline underline-offset-4"
          disabled={isLoading}
        >
          {isRegister ? 'Anmelden' : 'Registrieren'}
        </Button>
      </div>
    </form>
  );
}

export default LoginForm;
