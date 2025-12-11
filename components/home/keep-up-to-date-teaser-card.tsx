'use client';

import { MailCheckIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import Logo from '@/components/chat/logo';
import { Input } from '@/components/ui/input';
import { type FullUser, useAnonymousAuth } from '@/components/anonymous-auth';
import { toast } from 'sonner';
import { useMemo } from 'react';

type Props = {
  initialUser: FullUser | null;
};

function KeepUpToDateTeaserCard({ initialUser }: Props) {
  const { user, updateUser } = useAnonymousAuth();

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.target as HTMLFormElement);
    const email = formData.get('email') as string;

    toast.promise(handleAddEmail(email), {
      loading: 'Einen Moment, wir fügen deine E-Mail hinzu...',
      success:
        'Vielen Dank! Wir werden dich benachrichtigen, wenn der Koalitionsvertrag verfügbar ist.',
      error: 'Ein Fehler ist aufgetreten. Bitte versuche es später erneut.',
      duration: 5000,
    });
  };

  const handleAddEmail = async (email: string) => {
    if (!user) {
      throw new Error('User not found');
    }
    await updateUser({ keep_up_to_date_email: email });
  };

  const normalizedKeepUpToDateEmail = useMemo(() => {
    if (!user?.keep_up_to_date_email) {
      return initialUser?.keep_up_to_date_email ?? null;
    }

    return user.keep_up_to_date_email;
  }, [user, initialUser]);

  if (normalizedKeepUpToDateEmail) {
    return null;
  }

  return (
    <div className="relative mt-4 flex flex-col gap-2 overflow-hidden rounded-md border border-border bg-muted p-4">
      <div className="flex items-center gap-4">
        <Logo variant="small" className="size-6" />
        <div className="flex flex-col">
          <h1 className="text-base font-bold">Der Koalitionsvertrag!</h1>
          <p className="text-sm text-muted-foreground">
            Bald auf <span className="font-bold">wahl.chat</span>
          </p>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        Teile uns deine E-Mail mit, um benachrichtigt zu werden, wenn der
        Koalitionsvertrag auf wahl.chat verfügbar ist.
      </p>

      <form className="flex flex-col gap-2 md:flex-row" onSubmit={handleSubmit}>
        <Input
          name="email"
          placeholder="Email"
          type="email"
          autoComplete="email"
          autoCapitalize="off"
          spellCheck="false"
          required
        />

        <Button type="submit">
          <MailCheckIcon />
          Benachrichtige mich
        </Button>
      </form>
    </div>
  );
}

export default KeepUpToDateTeaserCard;
