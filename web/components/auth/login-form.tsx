'use client';
import { useAnonymousAuth } from '@/components/anonymous-auth';
import {
  ResponsiveDialogDescription,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import GithubIcon from '@/components/icons/github-icon';
import GoogleIcon from '@/components/icons/google-icon';
import { useStudyRunning } from '@/components/providers/study-status-provider';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Link } from '@/i18n/navigation';
import { oauthErrorAction } from '@/lib/auth/oauth-errors';
import { getUser, userJoinBriefingsWaitlist } from '@/lib/firebase/firebase';
import { FirebaseError } from 'firebase/app';
import {
  EmailAuthProvider,
  GithubAuthProvider,
  GoogleAuthProvider,
  type OAuthCredential,
  type User,
  getAuth,
  linkWithCredential,
  linkWithPopup,
  signInWithCredential,
  signInWithEmailAndPassword,
} from 'firebase/auth';
import { ChevronLeftIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { toast } from 'sonner';
import PasswordResetForm from './password-reset-form';
import SuccessAuthForm from './success-auth-form';
import WeeklySignup from './weekly-signup';

type AuthProvider = 'google' | 'github' | 'email';

/** Why the reader is asked to sign in. The feed asks them to sign up for
 * "Meine Woche", the weekly digest, which is also recorded on their user
 * doc. */
export type LoginPurpose = 'chat-history' | 'briefings';

type Props = {
  onSuccess: () => void;
  purpose?: LoginPurpose;
};

const DESCRIPTION_KEYS = {
  'chat-history': {
    login: 'loginDescription',
    register: 'registerDescription',
  },
  briefings: {
    login: 'briefingsLoginDescription',
    register: 'briefingsRegisterDescription',
  },
} as const;

function LoginForm({ onSuccess, purpose = 'chat-history' }: Props) {
  const t = useTranslations('auth');
  const tErrors = useTranslations('errors');
  const { refreshUser } = useAnonymousAuth();
  const studyRunning = useStudyRunning();
  // "Meine Woche" opens on its own pitch; its email option is signing up.
  const [showWeekly, setShowWeekly] = useState(purpose === 'briefings');
  const [isRegister, setIsRegister] = useState(purpose === 'briefings');
  const [isResetPassword, setIsResetPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [allowNewsletter, setAllowNewsletter] = useState(false);
  // A provider credential whose email already has a password account. It is
  // linked to that account once the password sign-in succeeds.
  const [pendingCredential, setPendingCredential] =
    useState<OAuthCredential | null>(null);
  const [pendingEmail, setPendingEmail] = useState('');

  const handleAuthSuccess = async () => {
    await refreshUser();
    const uid = getAuth().currentUser?.uid;

    if (uid && purpose === 'briefings') {
      try {
        await userJoinBriefingsWaitlist(uid);
      } catch (error) {
        // The sign-in itself worked; a missed waitlist mark must not undo it.
        console.error('Could not join the briefings waitlist', error);
      }
    }

    if (uid) {
      const user = await getUser(uid);

      // While the PledgeTracker study runs, its questionnaire is the only
      // thing we ask anyone for; skip the newsletter step rather than hiding
      // it, so the login flow still completes.
      if (user?.newsletter_allowed === undefined && !studyRunning) {
        setAllowNewsletter(true);
        return;
      }
    }

    onSuccess();
    showSuccessToast();
  };

  const handleAuthError = (error: unknown, provider: AuthProvider) => {
    if (error instanceof FirebaseError) {
      switch (oauthErrorAction(error.code)) {
        case 'invalid-credential':
          return toast.error(t('loginForm.invalidCredentials'));
        case 'sign-in-with-credential':
          return signInWithExistingCredential(error, provider);
        case 'already-linked':
          return handleProviderAlreadyLinked();
        case 'popup-blocked':
          return toast.error(t('loginForm.popupBlocked'));
        case 'ignore':
          return;
      }
    }

    console.error(error);
    showErrorReloadToast();
  };

  const signInWithExistingCredential = async (
    error: FirebaseError,
    provider: AuthProvider,
  ) => {
    if (provider === 'email') {
      setIsRegister(false);
      toast.error(t('loginForm.emailInUse'));
      return;
    }

    const credential =
      provider === 'google'
        ? GoogleAuthProvider.credentialFromError(error)
        : GithubAuthProvider.credentialFromError(error);

    if (!credential) {
      console.error(error);
      showErrorReloadToast();
      return;
    }

    try {
      await signInWithCredential(getAuth(), credential);
      await handleAuthSuccess();
    } catch (signInError) {
      // Firebase lets Google take over an account with the same email, but
      // not GitHub: the owner has to sign in with the password first.
      if (
        signInError instanceof FirebaseError &&
        signInError.code === 'auth/account-exists-with-different-credential'
      ) {
        const email = signInError.customData?.email;
        askForPassword(credential, typeof email === 'string' ? email : '');
        return;
      }

      // Not handleAuthError: its credential path would retry this sign-in.
      console.error(signInError);
      showErrorReloadToast();
    }
  };

  const askForPassword = (credential: OAuthCredential, email: string) => {
    setPendingCredential(credential);
    setPendingEmail(email);
    setShowWeekly(false);
    setIsRegister(false);
  };

  const linkPendingCredential = async (user: User) => {
    if (!pendingCredential) return;

    try {
      await linkWithCredential(user, pendingCredential);
    } catch (error) {
      // The password sign-in itself worked; a missed link must not undo it.
      console.error('Could not link the provider to the account', error);
    }
    setPendingCredential(null);
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
      const { user } = await signInWithEmailAndPassword(auth, email, password);
      await linkPendingCredential(user);
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
      await linkWithPopup(auth.currentUser, provider);
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
    toast.error(tErrors('reloadAndRetry'));
  };

  const showSuccessToast = () => {
    toast.success(
      t(
        purpose === 'briefings'
          ? 'loginForm.briefingsSuccess'
          : 'loginForm.success',
      ),
    );
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
    return (
      <SuccessAuthForm
        onSuccess={() => {
          onSuccess();
          // Signing up for "Meine Woche" is confirmed even when the
          // newsletter question came first.
          if (purpose === 'briefings') {
            showSuccessToast();
          }
        }}
      />
    );
  }

  if (showWeekly) {
    return (
      <WeeklySignup
        onGoogle={handleGoogleLogin}
        onGithub={handleGithubLogin}
        onEmail={() => {
          setIsRegister(true);
          setShowWeekly(false);
        }}
        onLogin={() => {
          setIsRegister(false);
          setShowWeekly(false);
        }}
        disabled={isLoading}
      />
    );
  }

  return (
    <form className="flex flex-col p-4 md:p-0" onSubmit={handleSubmit}>
      <input
        type="hidden"
        name="isRegister"
        value={isRegister ? 'true' : 'false'}
      />
      {purpose === 'briefings' && (
        <Button
          type="button"
          variant="link"
          className="mb-2 h-auto self-start p-0 text-muted-foreground"
          onClick={() => setShowWeekly(true)}
          disabled={isLoading}
        >
          <ChevronLeftIcon className="size-4" aria-hidden />
          {t('back')}
        </Button>
      )}
      <div className="mb-4">
        <ResponsiveDialogTitle className="text-center text-2xl font-bold md:text-left">
          {isRegister ? t('register') : t('login')}
        </ResponsiveDialogTitle>
        <ResponsiveDialogDescription className="text-center text-sm text-muted-foreground md:text-left">
          {t(
            `loginForm.${DESCRIPTION_KEYS[purpose][isRegister ? 'register' : 'login']}`,
          )}
        </ResponsiveDialogDescription>
      </div>

      {pendingCredential && (
        <p className="rounded-md border border-border p-3 text-sm">
          {t('loginForm.linkWithPassword', {
            provider:
              pendingCredential.providerId === 'google.com'
                ? 'Google'
                : 'Github',
          })}
        </p>
      )}

      <div className="flex flex-col">
        <div className="mt-4 grid gap-1">
          <Label htmlFor="email">{t('emailLabel')}</Label>
          <Input
            // Re-mounts so the address from a provider collision is filled in.
            key={pendingEmail}
            id="email"
            name="email"
            type="email"
            placeholder={t('emailPlaceholder')}
            defaultValue={pendingEmail}
            required
          />
        </div>
        <div className="my-4 grid gap-1">
          <div className="flex items-center">
            <Label htmlFor="password">{t('passwordLabel')}</Label>
            <Button
              variant="link"
              className="ml-auto inline-block h-fit p-0 text-sm underline-offset-4 hover:underline"
              onClick={handleResetPassword}
              size="sm"
              type="button"
            >
              {t('forgotPassword')}
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
            {isRegister ? t('register') : t('login')}
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            {t.rich(
              isRegister
                ? 'loginForm.registerConsent'
                : 'loginForm.loginConsent',
              {
                link: (chunks) => (
                  <Link
                    href="/datenschutz"
                    target="_blank"
                    className="underline"
                  >
                    {chunks}
                  </Link>
                ),
              },
            )}
          </p>

          <div className="relative my-4 text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:flex after:items-center after:border-t after:border-border">
            <span className="relative z-10 bg-background px-2 text-muted-foreground">
              {t('loginForm.otherProviders')}
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
              {t('loginForm.google')}
            </Button>
            <Button
              variant="outline"
              className="flex items-center gap-2"
              disabled={isLoading}
              type="button"
              onClick={handleGithubLogin}
            >
              <GithubIcon className="!size-3" />
              {t('loginForm.github')}
            </Button>
          </div>
        </div>
      </div>
      <div className="mt-4 text-center text-sm">
        {isRegister ? t('hasAccount') : t('noAccount')}{' '}
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
