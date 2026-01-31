'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { type TtsMessageState, getTtsKey } from '@/lib/stores/chat-store.types';
import { useCallback, useEffect, useRef } from 'react';

const DEFAULT_TTS_STATE: TtsMessageState = { status: 'idle' };

function useTtsState(partyId: string, messageId: string): TtsMessageState {
  return useChatStore((state) => {
    const sessionId =
      state.chatSessionId ?? state.localPreliminaryChatSessionId;
    if (!sessionId) return DEFAULT_TTS_STATE;
    const key = getTtsKey(sessionId, partyId, messageId);
    return state.ttsState[key] ?? DEFAULT_TTS_STATE;
  });
}

export type TtsStatus = 'idle' | 'loading' | 'ready' | 'playing' | 'error';

type UseTTSAudioReturn = {
  play: () => void;
  pause: () => void;
  status: TtsStatus;
};

export function useTTSAudio(
  partyId: string,
  messageId: string,
): UseTTSAudioReturn {
  const ttsState = useTtsState(partyId, messageId);
  const requestTextToSpeech = useChatStore(
    (state) => state.requestTextToSpeech,
  );
  const setTtsPlaying = useChatStore((state) => state.setTtsPlaying);
  const setTtsIdle = useChatStore((state) => state.setTtsIdle);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  const play = useCallback(() => {
    if (ttsState.status === 'idle' || ttsState.status === 'error') {
      // Request TTS if not ready yet
      requestTextToSpeech(partyId, messageId);
    } else if (ttsState.status === 'ready' && ttsState.audioBase64) {
      const audio = new Audio(`data:audio/mp3;base64,${ttsState.audioBase64}`);
      audioRef.current = audio;
      audio.play().catch(console.error);
      setTtsPlaying(partyId, messageId);

      audio.onended = () => {
        setTtsIdle(partyId, messageId);
      };
    }
  }, [
    ttsState,
    partyId,
    messageId,
    requestTextToSpeech,
    setTtsPlaying,
    setTtsIdle,
  ]);

  const pause = useCallback(() => {
    audioRef.current?.pause();
    if (audioRef.current) {
      audioRef.current.currentTime = 0;
    }
    setTtsIdle(partyId, messageId);
  }, [partyId, messageId, setTtsIdle]);

  // Auto-play when audio becomes ready
  useEffect(() => {
    if (
      ttsState.status === 'ready' &&
      ttsState.audioBase64 &&
      !audioRef.current
    ) {
      const audio = new Audio(`data:audio/mp3;base64,${ttsState.audioBase64}`);
      audioRef.current = audio;
      audio.play().catch(console.error);
      setTtsPlaying(partyId, messageId);

      audio.onended = () => {
        setTtsIdle(partyId, messageId);
      };
    }
  }, [ttsState, partyId, messageId, setTtsPlaying, setTtsIdle]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      audioRef.current?.pause();
    };
  }, []);

  return {
    play,
    pause,
    status: ttsState.status,
  };
}
