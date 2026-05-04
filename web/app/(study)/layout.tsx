'use client';

import { useTheme } from 'next-themes';
import { useEffect } from 'react';

/**
 * Force light theme inside the (study) route group so participants see
 * identical surfaces regardless of their system / saved preference. We
 * only flip if the resolved theme isn't already light to avoid loops.
 */
function ForceLightTheme() {
  const { setTheme, resolvedTheme } = useTheme();
  useEffect(() => {
    if (resolvedTheme !== 'light') {
      setTheme('light');
    }
  }, [setTheme, resolvedTheme]);
  return null;
}

export default function StudyGroupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <ForceLightTheme />
      {children}
    </>
  );
}
