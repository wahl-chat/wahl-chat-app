import { ThumbsDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from './responsive-drawer-dialog';
import { useState } from 'react';
import { Textarea } from '@/components/ui/textarea';

type Props = {
  isDisliked: boolean;
  onDislikeFeedback: (details: string) => void;
  feedbackDetail?: string;
};

function ChatDislikeFeedbackButton({
  isDisliked,
  onDislikeFeedback,
  feedbackDetail,
}: Props) {
  const [isOpen, setIsOpen] = useState(false);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsOpen(false);

    const formData = new FormData(e.target as HTMLFormElement);
    const details = formData.get('details') as string;
    onDislikeFeedback(details);
  };

  return (
    <ResponsiveDialog open={isOpen} onOpenChange={setIsOpen}>
      <ResponsiveDialogTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="group/dislike size-8 group-data-[has-message-background=true]:hover:bg-zinc-200 group-data-[has-message-background=true]:dark:hover:bg-zinc-800"
          onClick={() => setIsOpen(true)}
        >
          <div className="group-hover/dislike:-translate-y-2 group-hover/dislike:scale-125 group-hover/dislike:transition-transform group-hover/dislike:duration-200 group-hover/dislike:ease-in-out">
            <ThumbsDown className={cn(isDisliked && 'fill-foreground/30')} />
          </div>
        </Button>
      </ResponsiveDialogTrigger>
      <ResponsiveDialogContent className="px-4">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>Feedback abgeben</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            Was gefällt dir nicht an dieser Antwort?
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        <form onSubmit={handleSubmit}>
          <Textarea
            placeholder="Bitte gib hier dein Feedback ein. (optional)"
            className="w-full"
            name="details"
            defaultValue={feedbackDetail}
          />
          <Button className="my-4 w-full md:mb-0" type="submit">
            Feedback abgeben
          </Button>
        </form>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default ChatDislikeFeedbackButton;
