'use client';

import { Button } from '@/components/ui/button';
import { useEffect } from 'react';

interface ParticipateRedirectProps {
  href: string;
}

export function ParticipateRedirect({ href }: ParticipateRedirectProps) {
  useEffect(() => {
    window.location.href = href;
  }, [href]);

  return (
    <Button asChild className="mt-6 w-full">
      <a href={href}>Jetzt teilnehmen</a>
    </Button>
  );
}
