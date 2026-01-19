import AgentEntryPoint from '@/components/agent/agent-entry-point';

interface PageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function AgentPage({ searchParams }: PageProps) {
  const params = await searchParams;
  return <AgentEntryPoint searchParams={params} />;
}
