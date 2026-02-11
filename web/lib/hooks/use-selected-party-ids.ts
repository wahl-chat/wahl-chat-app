import { useSearchParams } from 'next/navigation';

function useSelectedPartyIds() {
  const searchParams = useSearchParams();

  return searchParams.getAll('party_id');
}

export default useSelectedPartyIds;
