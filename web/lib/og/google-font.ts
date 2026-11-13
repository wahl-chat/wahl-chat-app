/**
 * One Google font, cut down to the characters in `text`, for next/og's
 * ImageResponse. `font` is the family as the Google Fonts CSS API spells it,
 * with any axis selection ("Bricolage+Grotesque:wght@800").
 */
export async function loadGoogleFont(font: string, text: string) {
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
