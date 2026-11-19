import { resolveLocale } from '@/lib/seo';
import type { Metadata } from 'next';
import { getTranslations } from 'next-intl/server';
import LoginPageForm from './login-page-form';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const locale = resolveLocale((await params).locale);
  const t = await getTranslations({ locale, namespace: 'meta.login' });
  return {
    title: t('title'),
    robots: 'noindex, nofollow',
  };
}

function LoginPage() {
  return <LoginPageForm />;
}

export default LoginPage;
