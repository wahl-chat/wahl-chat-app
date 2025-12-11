'use client';

import { useState, useRef, useCallback, useEffect } from 'react';

type PermissionStatus = 'granted' | 'denied' | 'prompt' | 'unknown';

type VoiceRecorderReturn = {
  isRecording: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<Blob | null>;
  cancelRecording: () => void;
  permissionStatus: PermissionStatus;
  error: string | null;
};

export function useVoiceRecorder(): VoiceRecorderReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [permissionStatus, setPermissionStatus] =
    useState<PermissionStatus>('unknown');
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    if (typeof navigator === 'undefined' || !navigator.permissions) return;

    navigator.permissions
      .query({ name: 'microphone' as PermissionName })
      .then((result) => {
        setPermissionStatus(result.state as PermissionStatus);

        result.onchange = () => {
          setPermissionStatus(result.state as PermissionStatus);
        };
      })
      .catch(() => {
        setPermissionStatus('unknown');
      });
  }, []);

  const startRecording = useCallback(async () => {
    try {
      setError(null);

      if (typeof navigator === 'undefined' || !navigator.mediaDevices) {
        setError('Audioaufnahme wird nicht unterstützt.');
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm',
      });

      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsRecording(true);
      setPermissionStatus('granted');
    } catch (err) {
      if (err instanceof DOMException && err.name === 'NotAllowedError') {
        setPermissionStatus('denied');
        setError('Mikrofonzugriff wurde verweigert.');
      } else {
        setError('Fehler beim Starten der Aufnahme.');
      }
    }
  }, []);

  const stopRecording = useCallback(async (): Promise<Blob | null> => {
    return new Promise((resolve) => {
      if (
        !mediaRecorderRef.current ||
        mediaRecorderRef.current.state === 'inactive'
      ) {
        resolve(null);
        return;
      }

      mediaRecorderRef.current.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        setIsRecording(false);

        mediaRecorderRef.current?.stream
          .getTracks()
          .forEach((track) => track.stop());

        resolve(blob);
      };

      mediaRecorderRef.current.stop();
    });
  }, []);

  const cancelRecording = useCallback(() => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== 'inactive'
    ) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream
        .getTracks()
        .forEach((track) => track.stop());
    }
    setIsRecording(false);
    chunksRef.current = [];
  }, []);

  return {
    isRecording,
    startRecording,
    stopRecording,
    cancelRecording,
    permissionStatus,
    error,
  };
}
