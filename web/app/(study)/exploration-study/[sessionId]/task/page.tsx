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
} from '@/modules/exploration-study';
import { Loader2 } from 'lucide-react';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

type PageState = 'loading' | 'intro' | 'task' | 'error';

export default function TaskPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;

  const [pageState, setPageState] = useState<PageState>('loading');
  const [error, setError] = useState<string | null>(null);

  // Session info for intro
  const [sessionInfo, setSessionInfo] = useState<{
    topic: StudyTopic;
    condition: 'guided' | 'chat';
    durationSeconds: number;
  } | null>(null);

  // Task data after starting
  const [taskData, setTaskData] = useState<{
    chatId: string;
    condition: 'guided' | 'chat';
    durationSeconds: number;
    topic: StudyTopic;
  } | null>(null);

  const [isStarting, setIsStarting] = useState(false);

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
        condition: response.data.condition as 'guided' | 'chat',
        durationSeconds: response.data.durationSeconds,
        topic: sessionInfo.topic,
      });
      setPageState('task');
    }
  }, [sessionId, sessionInfo]);

  const handleEnd = useCallback(async () => {
    const response = await studyApi.endTask(sessionId);
    if (response.data) {
      const nextState = getStateFromResponse(response.data);
      if (nextState) {
        router.push(getRouteForState(sessionId, nextState));
      }
    }
  }, [sessionId, router]);

  const progress = getProgress('task');

  if (pageState === 'loading') {
    return (
      <div className="flex h-dvh flex-col overflow-hidden">
        <StudyHeader
          currentStep={progress.currentStep}
          totalSteps={progress.totalSteps}
          stepLabel={progress.label}
        />
        <div className="flex flex-1 items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="size-8 animate-spin text-muted-foreground" />
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
        <div className="flex flex-1 items-center justify-center">
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
        <TaskContainer
          condition={taskData.condition}
          durationSeconds={taskData.durationSeconds}
          onEnd={handleEnd}
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
