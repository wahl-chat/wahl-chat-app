import { AGENT_BACKEND_URL } from '@/lib/agent/backend-config';
import { NextResponse } from 'next/server';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ conversationId: string }> },
) {
  try {
    const { conversationId } = await params;

    const response = await fetch(
      `${AGENT_BACKEND_URL}/conversation-stage/${conversationId}`,
      {
        method: 'GET',
      },
    );

    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json(
        { error: errorText || 'Failed to get conversation stage' },
        { status: response.status },
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error proxying conversation-stage:', error);
    return NextResponse.json(
      { error: 'Failed to connect to agent backend' },
      { status: 500 },
    );
  }
}
