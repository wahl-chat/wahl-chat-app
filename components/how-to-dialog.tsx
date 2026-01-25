import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from './chat/responsive-drawer-dialog';
import HowTo from './how-to';

type Props = {
  children: React.ReactNode;
};

function HowToDialog({ children }: Props) {
  return (
    <ResponsiveDialog>
      <ResponsiveDialogTrigger asChild>{children}</ResponsiveDialogTrigger>
      <ResponsiveDialogContent className="flex max-h-[95dvh] flex-col overflow-hidden">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>
            Was kann ich mit <span className="underline">wahl.chat</span> alles
            machen?
          </ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            Tipps und Tricks, wie du wahl.chat am besten nutzen kannst.
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>

        <div className="grow overflow-y-auto px-4 md:px-0">
          <HowTo />
        </div>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default HowToDialog;
