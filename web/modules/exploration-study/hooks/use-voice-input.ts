'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

// Web Speech API types
interface SpeechRecognitionEvent {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionResultList {
  length: number;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  isFinal: boolean;
  [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

interface SpeechRecognitionErrorEvent {
  error: string;
}

interface SpeechRecognitionInstance {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
}

interface SpeechRecognitionConstructor {
  new (): SpeechRecognitionInstance;
}

export interface UseVoiceInputOptions {
  language?: string;
  continuous?: boolean;
  onResult?: (transcript: string) => void;
  onInterim?: (transcript: string) => void;
  onError?: (error: string) => void;
}

export interface UseVoiceInputReturn {
  isSupported: boolean;
  isListening: boolean;
  transcript: string;
  interimTranscript: string;
  startListening: () => void;
  stopListening: () => void;
  resetTranscript: () => void;
}

export function useVoiceInput({
  language = 'de-DE',
  continuous = true,
  onResult,
  onInterim,
  onError,
}: UseVoiceInputOptions = {}): UseVoiceInputReturn {
  const [isSupported, setIsSupported] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const interimRef = useRef(''); // Track interim for use in stopListening

  // Use refs for callbacks to avoid recreating recognition on callback changes
  const onResultRef = useRef(onResult);
  const onInterimRef = useRef(onInterim);
  const onErrorRef = useRef(onError);

  // Keep refs updated
  useEffect(() => {
    onResultRef.current = onResult;
    onInterimRef.current = onInterim;
    onErrorRef.current = onError;
  }, [onResult, onInterim, onError]);

  useEffect(() => {
    // Check for browser support
    const windowWithSpeech = window as typeof window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };

    const SpeechRecognition =
      windowWithSpeech.SpeechRecognition ||
      windowWithSpeech.webkitSpeechRecognition;

    if (SpeechRecognition) {
      setIsSupported(true);
      const recognition = new SpeechRecognition();
      recognition.lang = language;
      recognition.continuous = continuous;
      recognition.interimResults = true;

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let finalTranscript = '';
        let currentInterim = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcriptPart = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcriptPart;
          } else {
            currentInterim += transcriptPart;
          }
        }

        // Update interim transcript for real-time display
        interimRef.current = currentInterim;
        setInterimTranscript(currentInterim);
        if (currentInterim && onInterimRef.current) {
          onInterimRef.current(currentInterim);
        }

        // When we get final results, add them to the transcript
        if (finalTranscript) {
          interimRef.current = '';
          setTranscript((prev) => prev + finalTranscript);
          setInterimTranscript(''); // Clear interim when we have final
          if (onResultRef.current) {
            onResultRef.current(finalTranscript);
          }
        }
      };

      recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
        setIsListening(false);
        interimRef.current = '';
        setInterimTranscript('');
        if (onErrorRef.current) {
          onErrorRef.current(event.error);
        }
      };

      recognition.onend = () => {
        // Only update if we haven't already processed in stopListening
        setIsListening(false);
        // Don't clear interim here - stopListening already handles it
      };

      recognitionRef.current = recognition;
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
        recognitionRef.current = null;
      }
    };
  }, [language, continuous]);

  const startListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch {
        // Recognition already started
      }
    }
  }, []);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);

      // Convert any remaining interim transcript to final result immediately
      const remainingInterim = interimRef.current;
      if (remainingInterim) {
        interimRef.current = '';
        setInterimTranscript('');
        setTranscript((prev) => prev + remainingInterim);
        if (onResultRef.current) {
          onResultRef.current(remainingInterim);
        }
      } else {
        setInterimTranscript('');
      }
    }
  }, []);

  const resetTranscript = useCallback(() => {
    setTranscript('');
    setInterimTranscript('');
  }, []);

  return {
    isSupported,
    isListening,
    transcript,
    interimTranscript,
    startListening,
    stopListening,
    resetTranscript,
  };
}
