'use client';
import CopyButton from '@/components/chat/copy-button';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import { setWahlSwiperResultToPublic } from '@/lib/firebase/firebase';
import { track } from '@vercel/analytics/react';
import { ShareIcon } from 'lucide-react';
import { useParams } from 'next/navigation';
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

function WahlSwiperShareLinkInputForm() {
  const [isLoading, setIsLoading] = useState(false);
  const { contextId, resultId } = useParams();

  const resolvedContextId = Array.isArray(contextId) ? contextId[0] : contextId;
  const resolvedResultId = Array.isArray(resultId) ? resultId[0] : resultId;

  const link = useMemo(() => {
    const currentContextId = resolvedContextId ?? DEFAULT_CONTEXT_ID;
    return `${window.location.origin}/${currentContextId}/swiper/results/${resolvedResultId}`;
  }, [resolvedContextId, resolvedResultId]);

  const loadShareableSession = useCallback(async () => {
    if (!resolvedResultId) return;

    try {
      setIsLoading(true);
      await setWahlSwiperResultToPublic(resolvedResultId);

      track('share_link_generated');
    } catch (error) {
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  }, [resolvedResultId]);

  useEffect(() => {
    loadShareableSession();
  }, [loadShareableSession]);

  const handleNativeShare = async () => {
    if (!navigator.share) return;

    try {
      await navigator.share({
        title: 'Wahl Swiper Ergebnis',
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
          title="Wahl Swiper Ergebnis"
          separator=" - "
        >
          <WhatsappIcon size={30} borderRadius={10} />
        </WhatsappShareButton>
        <TwitterShareButton
          url={link}
          title="Wahl Swiper Ergebnis"
          hashtags={['WahlChat', 'Wahl2025', 'Bundestagswahl']}
          via="WahlChat"
        >
          <XIcon size={30} borderRadius={10} />
        </TwitterShareButton>
        <LinkedinShareButton url={link} title="Wahl Swiper Ergebnis">
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

export default WahlSwiperShareLinkInputForm;
