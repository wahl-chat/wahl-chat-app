import { Button } from '@/components/ui/button';
import { useVoiceRecorder } from '@/lib/hooks/use-voice-recorder';
import { cn } from '@/lib/utils';
import { Mic, Square } from 'lucide-react';
import { useEffect } from 'react';
import { toast } from 'sonner';

async function blobToUint8Array(blob: Blob): Promise<Uint8Array> {
  const arrayBuffer = await blob.arrayBuffer();
  return new Uint8Array(arrayBuffer);
}

export function useVoiceRecordButton(
  onRecordingComplete: (audioBytes: Uint8Array) => void,
) {
  const {
    isRecording,
    startRecording,
    stopRecording,
    error: recordingError,
  } = useVoiceRecorder();

  useEffect(() => {
    if (recordingError) {
      toast.error(recordingError);
    }
  }, [recordingError]);

  const handleStartRecording = async () => {
    await startRecording();
  };

  const handleStopRecording = async () => {
    const blob = await stopRecording();
    if (blob) {
      const bytes = await blobToUint8Array(blob);
      onRecordingComplete(bytes);
    }
  };

  return {
    isRecording,
    handleStartRecording,
    handleStopRecording,
  };
}

type VoiceRecordButtonProps = {
  onClick: () => void;
  disabled?: boolean;
  className?: string;
};

export function VoiceRecordButton({
  onClick,
  disabled,
  className,
}: VoiceRecordButtonProps) {
  return (
    <Button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'flex size-8 items-center justify-center rounded-full bg-foreground text-background transition-colors hover:bg-foreground/80 disabled:bg-foreground/20 disabled:text-muted',
        className,
      )}
    >
      <Mic className="size-4" />
    </Button>
  );
}

type RecordingIndicatorProps = {
  onStop: () => void;
  className?: string;
};

export function VoiceRecordingIndicator({
  onStop,
  className,
}: RecordingIndicatorProps) {
  return (
    <div
      className={cn('flex items-center justify-between py-3 px-4', className)}
    >
      <div className="flex items-center gap-2">
        <span className="size-3 animate-pulse rounded-full bg-red-500" />
        <span className="text-sm text-muted-foreground">Aufnahme läuft...</span>
      </div>
      <Button
        type="button"
        onClick={onStop}
        className="flex size-8 items-center justify-center rounded-full bg-red-500 text-white hover:bg-red-600"
      >
        <Square className="size-4" />
      </Button>
    </div>
  );
}

export default VoiceRecordButton;
