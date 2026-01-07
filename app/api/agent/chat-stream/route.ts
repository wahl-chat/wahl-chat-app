const AGENT_BACKEND_URL =
  process.env.WAHL_AGENT_BACKEND_URL || 'http://127.0.0.1:5000';

export async function POST(request: Request) {
  try {
    const body = await request.json();

    const response = await fetch(`${AGENT_BACKEND_URL}/chat-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      return new Response(errorText || 'Failed to stream chat', {
        status: response.status,
      });
    }

    // Stream the response back to the client
    const stream = response.body;

    if (!stream) {
      return new Response('No response body', { status: 500 });
    }

    return new Response(stream, {
      headers: {
        'Content-Type': 'application/x-ndjson',
        'Transfer-Encoding': 'chunked',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  } catch (error) {
    console.error('Error proxying chat-stream:', error);
    return new Response('Failed to connect to agent backend', { status: 500 });
  }
}
