// The decorations of each Stil on the share image, drawn by next/og: plain
// SVG shapes and solid fills only. The style board draws its textures with
// CSS gradients, which next/og draws poorly or not at all, so its dots,
// stars and snow are SVG circles here.
//
// Inside an <svg>, next/og writes the elements out as they are and never
// calls a component, so every shape here comes from a plain function that
// returns elements, and there are no fragments.
//
// Every shape is placed in reference units: the board's 360-unit square,
// scaled so its shorter side fits the image. On the story and the link
// preview the canvas is longer than 360 units in one direction, and the
// shapes keep to its edges.

import {
  SHARE_FORMATS,
  type ShareImageData,
  type ShareTheme,
} from '@/lib/stimmts/share-image';
import type { StyleId } from '@/lib/stimmts/styles';
import type { CSSProperties, ReactNode } from 'react';

type Format = ShareImageData['format'];

const GOLD = '#c9a85c';

/** Pixels per reference unit. */
export function decorScale(format: Format): number {
  const { width, height } = SHARE_FORMATS[format];
  return Math.min(width, height) / 360;
}

type Canvas = { W: number; H: number; format: Format };

/** Dots on a regular grid, the board's tiled radial-gradient textures. */
function grid(
  { W, H }: Canvas,
  step: [number, number],
  offset: [number, number],
  r: number,
  fill: string,
): ReactNode[] {
  const dots: ReactNode[] = [];
  for (let y = offset[1]; y < H; y += step[1]) {
    for (let x = offset[0]; x < W; x += step[0]) {
      dots.push(
        <circle key={`${x},${y},${r}`} cx={x} cy={y} r={r} fill={fill} />,
      );
    }
  }
  return dots;
}

/** Half-discs along every edge, like the perforation of a tear-off slip. */
function perforation({ W, H }: Canvas): ReactNode[] {
  const fill = '#cdb98d';
  const holes: ReactNode[] = [];
  for (let y = 6; y < H; y += 12) {
    holes.push(<circle key={`l${y}`} cx={0} cy={y} r={5} fill={fill} />);
    holes.push(<circle key={`r${y}`} cx={W} cy={y} r={5} fill={fill} />);
  }
  for (let x = 6; x < W; x += 12) {
    holes.push(<circle key={`t${x}`} cx={x} cy={0} r={5} fill={fill} />);
    holes.push(<circle key={`b${x}`} cx={x} cy={H} r={5} fill={fill} />);
  }
  return holes;
}

function drawPapier(canvas: Canvas) {
  return (
    <g>
      {grid(canvas, [6, 6], [3, 3], 0.8, 'rgba(110,80,30,0.14)')}
      {grid(canvas, [9, 9], [6, 7], 0.7, 'rgba(110,80,30,0.10)')}
      {perforation(canvas)}
    </g>
  );
}

const DOME_LINE = '#7f9ab3';

function drawKuppel({ W, H }: Canvas) {
  const posts: number[] = [];
  for (let x = 36; x < W - 12; x += 36) {
    // The middle of the balustrade stays open, as on the board.
    if (Math.abs(x - W / 2) > 18) {
      posts.push(x);
    }
  }
  // Lower and flatter than on the board, so the balustrade stays in the
  // bottom margin, under the footer's text.
  const railTop = H - 18;
  const railBottom = H - 7;
  return (
    <g>
      <g
        transform={`translate(${(W - 360) / 2 + 10} 4) scale(1.133)`}
        fill="none"
        stroke={DOME_LINE}
        strokeWidth={1.4}
        strokeLinecap="round"
      >
        <rect x={138} y={22} width={24} height={16} rx={2} />
        <path d="M150 12 V22" />
        <path d="M30 170 C30 92 88 38 150 38 C212 38 270 92 270 170" />
        <path d="M150 38 C118 58 92 110 88 170 M150 38 C132 70 120 120 119 170 M150 38 V170 M150 38 C182 58 208 110 212 170 M150 38 C168 70 180 120 181 170 M150 38 C100 56 58 110 56 170 M150 38 C200 56 242 110 244 170" />
        <path d="M44 128 Q150 146 256 128 M62 98 Q150 114 238 98 M88 70 Q150 84 212 70 M116 50 Q150 58 184 50" />
      </g>
      <g fill="none" stroke={DOME_LINE} strokeWidth={1.4}>
        <path d={`M12 ${railTop} H${W - 12} M12 ${railBottom} H${W - 12}`} />
        {posts.map((x) => (
          <path key={x} d={`M${x} ${railTop} V${railBottom}`} />
        ))}
      </g>
    </g>
  );
}

/**
 * Stars as fractions of the canvas, so they spread over every format. They
 * keep to the top edge and the side margins, where no format has text.
 */
const STARS: [x: number, y: number, r: number, opacity: number][] = [
  [0.3, 0.05, 1.2, 1],
  [0.62, 0.02, 1, 0.7],
  [0.5, 0.03, 1.3, 1],
  [0.97, 0.38, 1, 0.7],
  [0.03, 0.3, 1, 0.6],
  [0.03, 0.62, 1, 0.6],
  [0.97, 0.7, 1, 0.6],
];

function drawNacht({ W, H }: Canvas, theme: ShareTheme) {
  const skyline = '#141d40';
  // The board's moon sits top right, where this image has its wordmark; the
  // gap between the logo and the wordmark is free on every format.
  const moon = { cx: W * 0.42, cy: 14 + 12 };
  return (
    <g>
      {STARS.map(([x, y, r, opacity]) => (
        <circle
          key={`${x},${y}`}
          cx={x * W}
          cy={y * H}
          r={r}
          fill={`rgba(255,255,255,${opacity})`}
        />
      ))}
      {/* A crescent: the moon with the sky laid over most of it. */}
      <circle cx={moon.cx} cy={moon.cy} r={12} fill="#f1e9c8" />
      <circle cx={moon.cx - 7} cy={moon.cy - 3} r={12} fill={theme.canvas} />
      <g transform={`translate(${(W - 300) / 2} ${H - 190})`} fill={skyline}>
        <path d="M30 170 C30 92 88 38 150 38 C212 38 270 92 270 170 Z" />
        <rect x={138} y={22} width={24} height={16} rx={2} />
      </g>
      <rect x={0} y={H - 22} width={W} height={22} fill={skyline} />
    </g>
  );
}

/** Lights on a sagging wire, one board-width at a time across the top. */
function garland(W: number): ReactNode[] {
  const LIGHTS = [24, 73, 122, 171, 220, 269, 318, 367];
  const copies: ReactNode[] = [];
  for (let left = 0; left < W; left += 360) {
    copies.push(
      <g key={left} transform={`translate(${left} 0) scale(${360 / 390})`}>
        <path
          d="M-5 6 Q48 40 97 10 Q146 40 195 10 Q244 40 293 10 Q342 40 395 6"
          fill="none"
          stroke="#6b5b45"
          strokeWidth={1.6}
        />
        {LIGHTS.map((x, i) => {
          const y = i === 0 || i === LIGHTS.length - 1 ? 29 : 31;
          return (
            <g key={x}>
              <circle cx={x} cy={y} r={10} fill="rgba(255,210,120,0.32)" />
              <ellipse cx={x} cy={y} rx={4.5} ry={6.5} fill="#ffe9b0" />
            </g>
          );
        })}
      </g>,
    );
  }
  return copies;
}

/** The snow bank's visible height: low enough to stay under the footer. */
const SNOW_HEIGHT: Record<Format, number> = { square: 18, story: 44, link: 18 };

/** The tree's shapes, in a 90 by 120 box. */
function treeShapes() {
  return (
    <g>
      <polygon
        points="45,16 66,42 56,42 76,70 64,70 86,100 4,100 26,70 14,70 34,42 24,42"
        fill="#1d5a3c"
      />
      <rect x={40} y={100} width={10} height={14} fill="#6b4528" />
      <polygon
        points="45,2 48,10 56,10 50,15 52,23 45,18 38,23 40,15 34,10 42,10"
        fill="#f4dc8e"
      />
      {[
        [38, 36],
        [54, 58],
        [30, 64],
        [44, 88],
        [66, 92],
        [20, 92],
      ].map(([cx, cy]) => (
        <circle key={`${cx},${cy}`} cx={cx} cy={cy} r={3} fill="#fff1c4" />
      ))}
    </g>
  );
}

/**
 * Festlich's tree as an element of its own. The square has no free corner
 * for it (the footer fills the bottom), so it stands at the end of the
 * period row instead.
 */
export function FestiveTree({ width }: { width: number }) {
  return (
    <svg width={width} height={(width * 120) / 90} viewBox="0 0 90 120">
      {treeShapes()}
    </svg>
  );
}

function drawFestlich(canvas: Canvas) {
  const { W, H, format } = canvas;
  const snow = SNOW_HEIGHT[format];
  return (
    <g>
      {grid(canvas, [31, 37], [15.5, 18.5], 1.2, 'rgba(255,255,255,0.85)')}
      {grid(canvas, [53, 47], [41.5, 32.5], 1.7, 'rgba(255,255,255,0.6)')}
      {garland(W)}
      <ellipse
        cx={W / 2}
        cy={H + snow}
        rx={W * 0.7}
        ry={snow * 2}
        fill="#e3eaec"
      />
      {/* Only the story has a free corner below its footer. */}
      {format === 'story' && (
        <g
          transform={`translate(${W - 10 - 58} ${H - 14 - 78}) scale(${58 / 90})`}
        >
          {treeShapes()}
        </g>
      )}
    </g>
  );
}

/** One corner ornament, drawn for the top left and mirrored for the rest. */
function goldCorner(transform: string) {
  return (
    <g
      key={transform}
      transform={transform}
      fill="none"
      stroke={GOLD}
      strokeWidth={2.4}
    >
      <path d="M4 60 V22 Q4 4 22 4 H60" />
      <path d="M12 60 V26 Q12 12 26 12 H60" strokeWidth={1.2} />
      <circle cx={18} cy={18} r={4} fill={GOLD} />
    </g>
  );
}

function drawGold({ W, H }: Canvas) {
  // The corners are 44 units wide; their art is drawn in 64.
  const s = 44 / 64;
  return (
    <g>
      <rect
        x={7}
        y={7}
        width={W - 14}
        height={H - 14}
        fill="none"
        stroke={GOLD}
        strokeWidth={2}
      />
      <rect
        x={10.5}
        y={10.5}
        width={W - 21}
        height={H - 21}
        fill="none"
        stroke="rgba(201,168,92,0.6)"
        strokeWidth={1}
      />
      {[
        `translate(14 14) scale(${s})`,
        `translate(${W - 14} 14) scale(${-s} ${s})`,
        `translate(14 ${H - 14}) scale(${s} ${-s})`,
        `translate(${W - 14} ${H - 14}) scale(${-s} ${-s})`,
      ].map(goldCorner)}
    </g>
  );
}

const DECOR: Partial<
  Record<StyleId, (canvas: Canvas, theme: ShareTheme) => ReactNode>
> = {
  papier: drawPapier,
  kuppel: drawKuppel,
  nacht: drawNacht,
  festlich: drawFestlich,
  gold: drawGold,
};

/**
 * Everything a style draws behind the content, as one layer the size of the
 * image. Standard draws nothing, so its image stays as it was.
 */
export function ShareDecor({
  style,
  format,
  theme,
}: {
  style: StyleId;
  format: Format;
  theme: ShareTheme;
}) {
  const draw = DECOR[style];
  if (!draw) {
    return null;
  }
  const { width, height } = SHARE_FORMATS[format];
  const k = decorScale(format);
  const canvas = { W: width / k, H: height / k, format };
  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width,
        height,
        display: 'flex',
        // The board's paper glow: an inset shadow on a layer of its own.
        ...(style === 'papier'
          ? { boxShadow: `inset 0 0 ${30 * k}px rgba(150,110,40,0.3)` }
          : {}),
      }}
    >
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${canvas.W} ${canvas.H}`}
      >
        {draw(canvas, theme)}
      </svg>
    </div>
  );
}

/** A ring around the card, for the styles whose board card has one. */
export function cardFrame(
  style: StyleId,
  theme: ShareTheme,
  k: number,
): CSSProperties {
  if (style === 'festlich') {
    return {
      boxShadow: `0 0 0 ${3 * k}px ${theme.canvas}, 0 0 0 ${4 * k}px rgba(255,233,176,0.6)`,
    };
  }
  if (style === 'gold') {
    return {
      boxShadow: `0 0 0 ${3 * k}px ${theme.canvas}, 0 0 0 ${5 * k}px ${GOLD}`,
    };
  }
  return {};
}

/**
 * Kuppel's dome runs behind the header and the link: a patch of canvas
 * colour keeps the lines off the text.
 */
export function halo(
  style: StyleId,
  theme: ShareTheme,
  k: number,
): CSSProperties {
  if (style !== 'kuppel') {
    return {};
  }
  return {
    background: theme.canvas,
    boxShadow: `0 0 ${12 * k}px ${8 * k}px ${theme.canvas}`,
    borderRadius: 9999,
  };
}
