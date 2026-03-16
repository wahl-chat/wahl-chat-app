'use client';

import {
  StudyExplorationWrapper,
  StudyHeader,
  type StudyState,
  type StudyTopic,
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
  const taskNumber = Number.parseInt(params.taskNumber as string) as 1 | 2;

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
  } | null>(null);

  const [isStarting, setIsStarting] = useState(false);

  // Load session on mount
  useEffect(() => {
    async function loadSession() {
      const response = await studyApi.getSession(sessionId);

      console.log(response);

      if (response.error) {
        setError(response.error);
        setPageState('error');
        return;
      }

      if (response.data) {
        const session = response.data;
        const taskKey = taskNumber.toString();
        const chatId = session.chatIds?.[taskKey];

        // If task already started, go directly to task
        if (chatId && session.currentCondition) {
          setTaskData({
            chatId,
            condition: session.currentCondition,
            durationSeconds: session.taskDurationSeconds,
          });
          setPageState('task');
          return;
        }

        // Show intro - need topic and condition info
        // The backend should provide this based on the group assignment
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
  }, [sessionId, taskNumber]);

  const handleStart = useCallback(async () => {
    setIsStarting(true);
    const response = await studyApi.startTask(sessionId, taskNumber);

    if (response.error) {
      setError(response.error);
      setPageState('error');
      return;
    }

    if (response.data) {
      setTaskData({
        chatId: response.data.chatId,
        condition: response.data.condition as 'guided' | 'chat',
        durationSeconds: response.data.durationSeconds,
      });
      setPageState('task');
    }
  }, [sessionId, taskNumber]);

  const handleEnd = useCallback(async () => {
    const response = await studyApi.endTask(sessionId, taskNumber);
    if (response.data) {
      const nextState = getStateFromResponse(response.data);
      if (nextState) {
        router.push(getRouteForState(sessionId, nextState));
      }
    }
  }, [sessionId, taskNumber, router]);

  const state: StudyState = taskNumber === 1 ? 'task_1' : 'task_2';
  const progress = getProgress(state);

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
            taskNumber={taskNumber}
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
          <StudyExplorationWrapper chatId={taskData.chatId} />
        </TaskContainer>
      </div>
    );
  }

  return null;
}
