'use client';

import LoginForm from '@/components/auth/login-form';
import { ResponsiveDialog } from '@/components/chat/responsive-drawer-dialog';

/**
 * The form on its own page. It is built for the login dialog, whose title
 * needs a dialog around it: a closed one provides that and renders nothing
 * of its own. A client component, since a server page cannot hand the form
 * its callback.
 */
function LoginPageForm() {
  return (
    <ResponsiveDialog open={false}>
      <LoginForm onSuccess={() => {}} />
    </ResponsiveDialog>
  );
}

export default LoginPageForm;
