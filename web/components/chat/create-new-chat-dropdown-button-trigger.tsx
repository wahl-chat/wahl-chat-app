'use client';

import { Button } from '@/components/ui/button';
import { DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { useSidebar } from '@/components/ui/sidebar';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { SquarePenIcon } from 'lucide-react';

type Props = {
  onTriggerClick?: () => void;
};

function CreateNewChatDropdownButtonTrigger({ onTriggerClick }: Props) {
  const { isMobile, state } = useSidebar();

  if (!isMobile && state === 'expanded') return null;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <DropdownMenuTrigger asChild>
          <Button
            size="icon"
            variant="ghost"
            className="size-8"
            onClick={onTriggerClick}
          >
            <SquarePenIcon />
          </Button>
        </DropdownMenuTrigger>
      </TooltipTrigger>
      <TooltipContent>Erstelle einen neuen Chat</TooltipContent>
    </Tooltip>
  );
}

export default CreateNewChatDropdownButtonTrigger;
