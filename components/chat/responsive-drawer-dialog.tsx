'use client';

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from '@/components/ui/drawer';
import { useIsDesktop } from '@/lib/hooks/use-is-desktop';

type ResponsiveDefaultProps = {
  className?: string;
  children?: React.ReactNode;
};

type AsChildProps = {
  asChild?: boolean;
};

type ResponsiveDialogProps = Pick<ResponsiveDefaultProps, 'children'> & {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  defaultOpen?: boolean;
};

export function ResponsiveDialog({
  children,
  open,
  onOpenChange,
  defaultOpen,
}: ResponsiveDialogProps) {
  return (
    <>
      <Drawer open={open} onOpenChange={onOpenChange} defaultOpen={defaultOpen}>
        <Dialog
          open={open}
          onOpenChange={onOpenChange}
          defaultOpen={defaultOpen}
        >
          {children}
        </Dialog>
      </Drawer>
    </>
  );
}

export function ResponsiveDialogTrigger({
  children,
  className,
  asChild,
}: ResponsiveDefaultProps & AsChildProps) {
  const isDesktop = useIsDesktop();
  return isDesktop ? (
    <DialogTrigger asChild={asChild} className={className}>
      {children}
    </DialogTrigger>
  ) : (
    <DrawerTrigger asChild={asChild} className={className}>
      {children}
    </DrawerTrigger>
  );
}

export function ResponsiveDialogContent({
  children,
  className,
  asChild,
}: ResponsiveDefaultProps & AsChildProps) {
  const isDesktop = useIsDesktop();
  return isDesktop ? (
    <DialogContent asChild={asChild} className={className}>
      {children}
    </DialogContent>
  ) : (
    <DrawerContent asChild={asChild} className={className}>
      {children}
    </DrawerContent>
  );
}

export function ResponsiveDialogClose({
  children,
  className,
  asChild,
}: ResponsiveDefaultProps & AsChildProps) {
  const isDesktop = useIsDesktop();
  return isDesktop ? (
    <DialogClose asChild={asChild} className={className}>
      {children}
    </DialogClose>
  ) : (
    <DrawerClose asChild={asChild} className={className}>
      {children}
    </DrawerClose>
  );
}

export function ResponsiveDialogHeader({
  children,
  className,
}: ResponsiveDefaultProps) {
  const isDesktop = useIsDesktop();
  return isDesktop ? (
    <DialogHeader className={className}>{children}</DialogHeader>
  ) : (
    <DrawerHeader className={className}>{children}</DrawerHeader>
  );
}

export function ResponsiveDialogTitle({
  children,
  className,
}: ResponsiveDefaultProps) {
  const isDesktop = useIsDesktop();
  return isDesktop ? (
    <DialogTitle className={className}>{children}</DialogTitle>
  ) : (
    <DrawerTitle className={className}>{children}</DrawerTitle>
  );
}

export function ResponsiveDialogDescription({
  children,
  className,
}: ResponsiveDefaultProps) {
  const isDesktop = useIsDesktop();
  return isDesktop ? (
    <DialogDescription className={className}>{children}</DialogDescription>
  ) : (
    <DrawerDescription className={className}>{children}</DrawerDescription>
  );
}

export function ResponsiveDialogFooter({
  children,
  className,
}: ResponsiveDefaultProps) {
  const isDesktop = useIsDesktop();
  return isDesktop ? (
    <DialogFooter className={className}>{children}</DialogFooter>
  ) : (
    <DrawerFooter className={className}>{children}</DrawerFooter>
  );
}
