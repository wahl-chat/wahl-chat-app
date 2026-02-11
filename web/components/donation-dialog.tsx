import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from './chat/responsive-drawer-dialog';
import DonationForm from './donation-form';
import VisuallyHidden from './visually-hidden';

type Props = {
  children: React.ReactNode;
};

function DonationDialog({ children }: Props) {
  return (
    <ResponsiveDialog>
      <ResponsiveDialogTrigger asChild>{children}</ResponsiveDialogTrigger>
      <ResponsiveDialogContent>
        <VisuallyHidden>
          <ResponsiveDialogTitle>Spenden</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            Halte wahl.chat mit deiner Spende am Leben!
          </ResponsiveDialogDescription>
        </VisuallyHidden>
        <DonationForm />
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default DonationDialog;
