import { permanentRedirect } from 'next/navigation';

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

/** The feed's prototype address; the feed now lives at /. */
async function AktuellRedirect({ searchParams }: Props) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(await searchParams)) {
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item !== undefined) {
        params.append(key, item);
      }
    }
  }
  const query = params.toString();
  permanentRedirect(query ? `/?${query}` : '/');
}

export default AktuellRedirect;
