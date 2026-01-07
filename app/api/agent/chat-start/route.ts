import { NextResponse } from 'next/server';

const AGENT_BACKEND_URL =
  process.env.WAHL_AGENT_BACKEND_URL || 'http://127.0.0.1:5000';

export async function POST(request: Request) {
  try {
    const body = await request.json();

    const response = await fetch(`${AGENT_BACKEND_URL}/chat-start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json(
        { error: errorText || 'Failed to start conversation' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error proxying chat-start:', error);
    return NextResponse.json(
      { error: 'Failed to connect to agent backend' },
      { status: 500 }
    );
  }
}
