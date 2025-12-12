import {
  ResponsiveDialogDescription,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { getAuth, sendPasswordResetEmail } from 'firebase/auth';
import { useState } from 'react';
import { toast } from 'sonner';

type Props = {
  onChangeView: () => void;
};

function PasswordResetForm({ onChangeView }: Props) {
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsLoading(true);
    const formData = new FormData(e.target as HTMLFormElement);
    const email = formData.get('email') as string;
    const auth = getAuth();
    await sendPasswordResetEmail(auth, email);
    setIsLoading(false);
    toast.success('E-Mail zum Zurücksetzen des Passworts wurde gesendet.');

    onChangeView();
  };

  return (
    <form className="flex flex-col p-4 md:p-0" onSubmit={handleSubmit}>
      <div className="mb-4">
        <ResponsiveDialogTitle className="text-center text-2xl font-bold md:text-left">
          Passwort vergessen?
        </ResponsiveDialogTitle>
        <ResponsiveDialogDescription className="text-center text-sm text-muted-foreground md:text-left">
          Gib deine Email ein und wir senden dir einen Link zum Zurücksetzen
          deines Passworts.
        </ResponsiveDialogDescription>
      </div>

      <div className="flex flex-col gap-4">
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
        <Button type="submit" className="w-full" disabled={isLoading}>
          Link senden
        </Button>
      </div>
      <div className="mt-4 text-center text-sm">
        Hast du schon einen Account?{' '}
        <Button
          size="sm"
          type="button"
          variant="link"
          onClick={onChangeView}
          className="p-0 underline underline-offset-4"
        >
          Anmelden
        </Button>
      </div>
    </form>
  );
}

export default PasswordResetForm;
