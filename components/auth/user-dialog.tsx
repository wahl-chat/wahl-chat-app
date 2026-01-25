import { useAnonymousAuth } from '@/components/anonymous-auth';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogFooter,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from '@/components/chat/responsive-drawer-dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { UserDetails } from '@/lib/utils';
import { getAuth, signOut } from 'firebase/auth';
import { LogOutIcon } from 'lucide-react';
import { useState } from 'react';

type Props = {
  children: React.ReactNode;
  details?: UserDetails;
  asChild?: boolean;
};

function UserDialog({ children, details, asChild }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const { user } = useAnonymousAuth();
  const [isLoading, setIsLoading] = useState(false);

  const handleLogout = async () => {
    setIsLoading(true);
    const auth = getAuth();
    await signOut(auth);
    setIsOpen(false);
    setIsLoading(false);
  };

  return (
    <ResponsiveDialog open={isOpen} onOpenChange={setIsOpen}>
      <ResponsiveDialogTrigger asChild={asChild}>
        {children}
      </ResponsiveDialogTrigger>
      <ResponsiveDialogContent>
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>Account</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            Hier kannst du deine persönlichen Details einsehen.
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>

        <section className="flex flex-col gap-4">
          {details?.displayName && (
            <div className="flex flex-col gap-4 px-4 md:px-0">
              <div className="flex flex-col gap-2">
                <Label htmlFor="displayName">Name</Label>
                <Input
                  disabled
                  id="displayName"
                  type="text"
                  value={details.displayName}
                />
              </div>
            </div>
          )}
          <div className="flex flex-col gap-4 px-4 md:px-0">
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">E-Mail</Label>
              <Input
                disabled
                id="email"
                type="email"
                value={user?.email ?? ''}
              />
            </div>
          </div>
        </section>

        <ResponsiveDialogFooter>
          <Button
            onClick={handleLogout}
            className="w-full"
            disabled={isLoading}
          >
            <LogOutIcon className="size-4" />
            Logout
          </Button>
        </ResponsiveDialogFooter>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default UserDialog;
