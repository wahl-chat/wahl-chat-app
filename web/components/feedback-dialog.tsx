import { MailIcon } from 'lucide-react';
import Link from 'next/link';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from './chat/responsive-drawer-dialog';
import { Button } from './ui/button';
type Props = {
  /** The trigger. Omit it to open the dialog through `open` instead. */
  children?: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

function FeedbackDialog({ children, open, onOpenChange }: Props) {
  return (
    <ResponsiveDialog open={open} onOpenChange={onOpenChange}>
      {children && (
        <ResponsiveDialogTrigger asChild>{children}</ResponsiveDialogTrigger>
      )}

      <ResponsiveDialogContent>
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>
            Feedback? Wünsche? Anregungen?
          </ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            Schreib uns, was wir noch verbessern können oder was du dir gerne
            auf wahl.chat wünschen würdest.
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>

        <div className="flex w-full flex-col gap-2 p-4 md:p-0">
          <Button asChild variant="outline">
            <Link href="mailto:info@wahl.chat">
              <MailIcon />
              Schreibe uns eine E-Mail
            </Link>
          </Button>
        </div>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default FeedbackDialog;
