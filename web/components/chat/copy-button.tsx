'use client';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { track } from '@vercel/analytics/react';
import type { VariantProps } from 'class-variance-authority';
import { Check, Copy } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { toast } from 'sonner';

type Props = {
  text: string;
  tooltip?: string;
  className?: string;
  variant?: VariantProps<typeof Button>['variant'];
  size?: VariantProps<typeof Button>['size'];
  loading?: boolean;
};

function CopyButton({
  text,
  tooltip,
  className,
  variant,
  size,
  loading,
}: Props) {
  const t = useTranslations('chat.copy');
  const [isCopied, setIsCopied] = useState(false);

  const handleCopyMessage = () => {
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    toast.success(t('copied'));

    track('message_copied', {
      message: text,
    });

    setTimeout(() => {
      setIsCopied(false);
    }, 2000);
  };

  return (
    <Button
      variant={variant}
      size={size}
      className={cn(
        'group-data-[has-message-background]:hover:bg-zinc-200 group-data-[has-message-background]:dark:hover:bg-zinc-800',
        className,
      )}
      tooltip={tooltip}
      onClick={handleCopyMessage}
      disabled={loading}
    >
      {isCopied ? <Check /> : <Copy />}
      <span className="sr-only">{t('label')}</span>
    </Button>
  );
}

export default CopyButton;
