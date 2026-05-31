'use client';

import {
  StudyExplorationWrapper,
  StudyHeader,
  type StudyTopic,
  TOPIC_INFO,
  TaskContainer,
  TaskIntro,
  getProgress,
  getRouteForState,
  getStateFromResponse,
  studyApi,
  useScreenTelemetry,
  useStudySessionContext,
} from '@/modules/exploration-study';
import {
  explorationActions,
  useExplorationStore,
} from '@/modules/guided-exploration/store';
import { Loader2 } from 'lucide-react';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

type PageState = 'loading' | 'intro' | 'task' | 'error';

export default function TaskPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const studySession = useStudySessionContext();

  const dispatch = useExplorationStore((s) => s.dispatch);

  const [pageState, setPageState] = useState<PageState>('loading');
  const [error, setError] = useState<string | null>(null);
  // Step announcement for this route. StudyLayout deliberately skips its own
  // focus/announcement on the task route (it hides the header), so we mirror
  // that behaviour here once the content for a state is ready.
  const [stepAnnouncement, setStepAnnouncement] = useState('');

  // Session info for intro
  const [sessionInfo, setSessionInfo] = useState<{
    topic: StudyTopic;
    condition: 'guided' | 'baseline';
    durationSeconds: number;
  } | null>(null);

  // Task data after starting
  const [taskData, setTaskData] = useState<{
    chatId: string;
    condition: 'guided' | 'baseline';
    durationSeconds: number;
    topic: StudyTopic;
    taskStartedAt: string | null;
  } | null>(null);

  const [isStarting, setIsStarting] = useState(false);

  // Behavioral integrity telemetry while the participant works on the task
  // (tab/window focus, copy/paste, cursor leaving the viewport). Active only
  // once the chat/exploration is on screen.
  useScreenTelemetry(sessionId, 'task', { enabled: pageState === 'task' });

  // Load session on mount
  useEffect(() => {
    async function loadSession() {
      const response = await studyApi.getSession(sessionId);

      if (response.error) {
        setError(response.error);
        setPageState('error');
        return;
      }

      if (response.data) {
        const session = response.data;

        // If task already started, go directly to task
        if (session.chatId && session.currentCondition) {
          setTaskData({
            chatId: session.chatId,
            condition: session.currentCondition,
            durationSeconds: session.taskDurationSeconds,
            topic: session.currentTopic as StudyTopic,
            taskStartedAt: session.taskStartedAt ?? null,
          });
          setPageState('task');
          return;
        }

        // Show intro
        const topic = session.currentTopic as StudyTopic;
        const condition = session.currentCondition;

        if (!condition) {
          setError('No condition assigned');
          setPageState('error');
          return;
        }

        setSessionInfo({
          topic,
          condition,
          durationSeconds: session.taskDurationSeconds || 600,
        });
        setPageState('intro');
      }
    }

    loadSession();
  }, [sessionId]);

  const handleStart = useCallback(async () => {
    setIsStarting(true);
    const response = await studyApi.startTask(sessionId);

    if (response.error) {
      setError(response.error);
      setPageState('error');
      return;
    }

    if (response.data && sessionInfo) {
      setTaskData({
        chatId: response.data.chatId,
        condition: response.data.condition as 'guided' | 'baseline',
        durationSeconds: response.data.durationSeconds,
        topic: sessionInfo.topic,
        taskStartedAt: response.data.taskStartedAt,
      });
      setPageState('task');
    }
  }, [sessionId, sessionInfo]);

  // Returns `true` when the task was ended and a navigation was kicked off,
  // `false` on any failure (network error, missing/unrecognized next state).
  // The caller (`TaskContainer`) re-enables its end button on `false` so the
  // participant isn't stranded on a "Wird beendet…" state after a hiccup.
  const handleEnd = useCallback(async (): Promise<boolean> => {
    const response = await studyApi.endTask(sessionId);
    if (response.error || !response.data) {
      return false;
    }
    const nextState = getStateFromResponse(response.data);
    if (!nextState) {
      return false;
    }
    router.push(getRouteForState(sessionId, nextState));
    return true;
  }, [sessionId, router]);

  const handleFirstFinishClick = useCallback(() => {
    void studyApi.notifyFirstFinishClick(sessionId);
  }, [sessionId]);

  const progress = getProgress('task', studySession.studyType);

  // On arrival at a ready state, announce the step and move focus to the top
  // of the content (the "Deine Aufgabe" heading on the intro; the chat content
  // region once the task is live) so screen-reader users land in the right
  // place instead of at the top of the document.
  useEffect(() => {
    if (pageState !== 'intro' && pageState !== 'task') return;
    setStepAnnouncement(
      `Schritt ${progress.currentStep} von ${progress.totalSteps}: ${progress.label}`,
    );
    const raf = requestAnimationFrame(() => {
      const target =
        pageState === 'intro'
          ? document.querySelector<HTMLElement>('[data-task-intro-heading]')
          : document.getElementById('main-content');
      target?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(raf);
  }, [pageState, progress.currentStep, progress.totalSteps, progress.label]);

  if (pageState === 'loading') {
    return (
      <div className="flex h-dvh flex-col overflow-hidden">
        <StudyHeader
          currentStep={progress.currentStep}
          totalSteps={progress.totalSteps}
          stepLabel={progress.label}
        />
        <div className="flex flex-1 items-center justify-center">
          <div
            role="status"
            aria-live="polite"
            className="flex flex-col items-center gap-4"
          >
            <Loader2
              aria-hidden="true"
              className="size-8 animate-spin text-muted-foreground"
            />
            <p className="text-sm text-muted-foreground">
              Aufgabe wird vorbereitet...
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (pageState === 'error') {
    return (
      <div className="flex h-dvh flex-col overflow-hidden">
        <StudyHeader
          currentStep={progress.currentStep}
          totalSteps={progress.totalSteps}
          stepLabel={progress.label}
        />
        <div role="alert" className="flex flex-1 items-center justify-center">
          <div className="text-center">
            <h1 className="text-2xl font-bold">Fehler</h1>
            <p className="mt-2 text-muted-foreground">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (pageState === 'intro' && sessionInfo) {
    return (
      <div className="flex h-dvh flex-col overflow-hidden">
        <StudyHeader
          currentStep={progress.currentStep}
          totalSteps={progress.totalSteps}
          stepLabel={progress.label}
        />
        <div
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className="sr-only"
        >
          {stepAnnouncement}
        </div>
        <div className="flex-1 overflow-auto py-8">
          <TaskIntro
            topic={sessionInfo.topic}
            condition={sessionInfo.condition}
            durationMinutes={Math.round(sessionInfo.durationSeconds / 60)}
            onStart={handleStart}
            isStarting={isStarting}
          />
        </div>
      </div>
    );
  }

  if (pageState === 'task' && taskData) {
    return (
      <div className="flex h-dvh flex-col overflow-hidden">
        <StudyHeader
          currentStep={progress.currentStep}
          totalSteps={progress.totalSteps}
          stepLabel={progress.label}
        />
        <div
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className="sr-only"
        >
          {stepAnnouncement}
        </div>
        <TaskContainer
          durationSeconds={taskData.durationSeconds}
          startedAt={taskData.taskStartedAt}
          onEnd={handleEnd}
          // On time-up, close any open leaf panel so the time-up dialog is the
          // only modal — otherwise focus bounces between two stacked dialogs.
          onTimeUp={() => dispatch(explorationActions.leafClosed())}
          onFirstFinishClick={handleFirstFinishClick}
        >
          <StudyExplorationWrapper
            chatId={taskData.chatId}
            studyTopicLabel={TOPIC_INFO[taskData.topic]?.title}
          />
        </TaskContainer>
      </div>
    );
  }

  return null;
}
