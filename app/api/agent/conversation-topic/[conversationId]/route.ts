import { NextResponse } from 'next/server';

const AGENT_BACKEND_URL =
    process.env.WAHL_AGENT_BACKEND_URL || 'http://127.0.0.1:5000';

export async function GET(
    request: Request,
    { params }: { params: Promise<{ conversationId: string }> }
) {
    try {
        const { conversationId } = await params;

        const response = await fetch(
            `${AGENT_BACKEND_URL}/conversation-topic/${conversationId}`,
            {
                method: 'GET',
            }
        );

        if (!response.ok) {
            const errorText = await response.text();
            return NextResponse.json(
                { error: errorText || 'Failed to get conversation topic' },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Error proxying conversation-topic:', error);
        return NextResponse.json(
            { error: 'Failed to connect to agent backend' },
            { status: 500 }
        );
    }
}

