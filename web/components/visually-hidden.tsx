import * as VisuallyHiddenRadix from '@radix-ui/react-visually-hidden';

function VisuallyHidden({ children }: { children: React.ReactNode }) {
  return <VisuallyHiddenRadix.Root>{children}</VisuallyHiddenRadix.Root>;
}

export default VisuallyHidden;
