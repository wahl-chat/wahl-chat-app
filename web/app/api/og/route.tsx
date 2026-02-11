import { ImageResponse } from 'next/og';

async function loadGoogleFont(font: string, text: string) {
  const url = `https://fonts.googleapis.com/css2?family=${font}&text=${encodeURIComponent(text)}`;
  const css = await (await fetch(url)).text();
  const resource = css.match(
    /src: url\((.+)\) format\('(opentype|truetype)'\)/,
  );

  if (resource) {
    const response = await fetch(resource[1]);
    if (response.status === 200) {
      return await response.arrayBuffer();
    }
  }

  throw new Error('failed to load font data');
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);

    const hasPartyImageUrl = searchParams.has('partyImageUrl');
    const hasBackgroundColor = searchParams.has('backgroundColor');

    if (!hasPartyImageUrl) {
      return new Response('Party image URL is required', { status: 400 });
    }

    if (!hasBackgroundColor) {
      return new Response('Background color is required', { status: 400 });
    }

    const partyImageUrl = searchParams.get('partyImageUrl');
    const normalizedPartyImageUrl = partyImageUrl?.replace('.webp', '.png');

    const backgroundColor = searchParams.get('backgroundColor');

    const title = searchParams.get('title')?.slice(0, 100);

    return new ImageResponse(
      <div
        style={{
          backgroundColor: 'white',
          backgroundSize: '150px 150px',
          height: '100%',
          width: '100%',
          display: 'flex',
          textAlign: 'center',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          flexWrap: 'nowrap',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            justifyItems: 'center',
            gap: 36,
          }}
        >
          <svg
            viewBox="0 0 368 201"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="m62.353.301 13.954 37.462 3.014 9.012h.27l2.472-9.012L93.546.151h22.423l-28.3 92.012H75.101L63.197 58.649l-3.979-11.904h-.422l-4.249 11.754-12.99 33.634H28.84L.539.12h22.544l11.482 37.612 2.472 8.891h.27l3.015-8.89L54.125.27h8.228v.03ZM192.399 92.163h-25.858l-2.863-7.535-37.884-.271-4.37 7.806H98.85L139.055 0h16.003l37.341 92.163Zm-33.634-26.1-12.839-30.5-13.261 30.078 26.1.422ZM220.549.03v35.413h34.598V.03h22.001v92.163h-22.151V56.63h-34.448v35.563h-22.001V.03h22.001ZM312.862.03v72.06h26.492v20.103h-48.493V.181l22.001-.15ZM290.349 199.365H264.49l-2.863-7.535-37.884-.271-4.37 7.806H196.8l40.204-92.163h16.003l37.342 92.163Zm-33.635-26.13-12.838-30.5-13.261 30.078 26.099.422ZM367.081 107.473v18.596h-31.193l-.121 73.296-22.001-.151v-73.296h-30.801v-18.595l84.116.15ZM131.611 107.202v35.412h34.598v-35.412h22.001v92.163h-22.151v-35.563h-34.448v35.563H109.61v-92.163h22.001Z"
              fill="currentColor"
            />
            <path
              d="m60.334 176.128-23.69-23.689 10.248-10.277 13.441 13.441 31.585-31.584 10.278 10.277-41.862 41.832Z"
              fill="#ED3833"
            />
            <path
              d="M68.47 177.273c-3.887 2.14-8.136 3.225-12.778 3.225-3.737 0-7.203-.693-10.398-2.109-.904-.392-1.687-.935-2.501-1.387l-17.179 4.159 5.666-17.57c-1.235-3.135-1.868-6.48-1.868-10.006 0-3.647.693-7.113 2.049-10.398a27.57 27.57 0 0 1 5.546-8.559c2.32-2.411 5.093-4.34 8.257-5.757 3.195-1.416 6.66-2.109 10.398-2.109 4.008 0 7.715.783 11.151 2.32a27.681 27.681 0 0 1 5.094 3.014l14.466-14.918a48.706 48.706 0 0 0-11.543-7.324c-5.937-2.682-12.296-4.038-19.138-4.038-6.57 0-12.748 1.235-18.595 3.677-5.847 2.471-10.94 5.846-15.31 10.186-4.37 4.34-7.836 9.373-10.398 15.1-2.562 5.726-3.828 11.904-3.828 18.444 0 6.57 1.266 12.719 3.828 18.475 2.562 5.756 6.028 10.759 10.398 15.039 4.37 4.28 9.493 7.655 15.31 10.126 5.847 2.472 12.025 3.677 18.595 3.677 7.474 0 14.376-1.567 20.705-4.731 6.33-3.135 11.694-7.414 16.064-12.779l-14.497-14.346c-2.44 3.587-5.605 6.45-9.493 8.589ZM367.051 72.09h-19.138v20.103h19.138V72.09Z"
              fill="currentColor"
            />
          </svg>

          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M18 6 6 18" />
            <path d="m6 6 12 12" />
          </svg>

          <img
            src={normalizedPartyImageUrl}
            alt="Party"
            width="256"
            height="256"
            style={{
              backgroundColor: backgroundColor ?? 'white',
              borderRadius: '10px',
              objectFit: 'contain',
              padding: 24,
            }}
          />
        </div>
        {title && (
          <div
            style={{
              fontSize: 50,
              fontStyle: 'normal',
              fontFamily: 'Inter',
              letterSpacing: '-0.025em',
              color: 'black',
              marginTop: 30,
              padding: '0 120px',
              lineHeight: 1.4,
              whiteSpace: 'pre-wrap',
            }}
          >
            {title}
          </div>
        )}
      </div>,
      {
        width: 1200,
        height: 630,
        fonts: title
          ? [
              {
                name: 'Geist',
                data: await loadGoogleFont('Inter', title),
                style: 'normal',
              },
            ]
          : [],
      },
    );
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } catch (e: any) {
    console.log(`${e.message}`);
    return new Response(`Failed to generate the image`, {
      status: 500,
    });
  }
}
