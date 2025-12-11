'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  FacebookIcon,
  FacebookShareButton,
  LinkedinIcon,
  LinkedinShareButton,
  TwitterShareButton,
  WhatsappIcon,
  WhatsappShareButton,
  XIcon,
} from 'react-share';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { Label } from '@/components/ui/label';
import CopyButton from './copy-button';
import { Input } from '@/components/ui/input';
import { useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { ShareIcon } from 'lucide-react';
import { track } from '@vercel/analytics/react';

type Props = {
  sharePrivateSession: boolean;
};

function ChatShareLinkInputForm({ sharePrivateSession }: Props) {
  const [isLoading, setIsLoading] = useState(sharePrivateSession);
  const sessionTitle = useChatStore((state) => state.currentChatTitle);
  const sharingSnapshot = useChatStore((state) => state.sharingSnapshot);
  const generateSharingSnapshotLink = useChatStore(
    (state) => state.generateSharingSnapshotLink,
  );
  const params = useSearchParams();

  const link = useMemo(() => {
    if (!sharePrivateSession || !sharingSnapshot?.id) {
      const url = new URL(window.location.href);
      const partyIds = params.getAll('partyId');
      partyIds.forEach((partyId) =>
        url.searchParams.append('partyId', partyId),
      );
      return url.toString();
    }

    return `${window.location.origin}/share?snapshot_id=${sharingSnapshot?.id}`;
  }, [sharingSnapshot?.id, params, sharePrivateSession]);

  const loadShareableSession = useCallback(async () => {
    try {
      setIsLoading(true);
      await generateSharingSnapshotLink();

      track('share_link_generated');
    } catch (error) {
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  }, [generateSharingSnapshotLink]);

  useEffect(() => {
    if (!sharePrivateSession) return;

    loadShareableSession();
  }, [loadShareableSession, sharePrivateSession]);

  const handleNativeShare = async () => {
    if (!navigator.share) return;

    try {
      await navigator.share({
        title: sessionTitle,
        url: link,
      });
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center space-x-2">
        <div className="grid flex-1 gap-2">
          <Label htmlFor="link" className="sr-only">
            Link
          </Label>
          <Input id="link" value={link} readOnly disabled={isLoading} />
        </div>
        <CopyButton size="icon" text={link} loading={isLoading} />
      </div>
      <div className="flex items-center gap-2">
        <WhatsappShareButton
          className="aspect-square w-fit"
          url={link}
          title={sessionTitle}
          separator=" - "
        >
          <WhatsappIcon size={30} borderRadius={10} />
        </WhatsappShareButton>
        <TwitterShareButton
          url={link}
          title={sessionTitle}
          hashtags={['WahlChat', 'Wahl2025', 'Bundestagswahl']}
          via="WahlChat"
        >
          <XIcon size={30} borderRadius={10} />
        </TwitterShareButton>
        <LinkedinShareButton url={link} title={sessionTitle}>
          <LinkedinIcon size={30} borderRadius={10} />
        </LinkedinShareButton>
        <FacebookShareButton url={link} hashtag="#WahlChat">
          <FacebookIcon size={30} borderRadius={10} />
        </FacebookShareButton>
        <Button
          variant="secondary"
          size="icon"
          className="size-8"
          onClick={handleNativeShare}
        >
          <ShareIcon />
        </Button>
      </div>
    </div>
  );
}

export default ChatShareLinkInputForm;
