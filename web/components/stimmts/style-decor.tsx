import {
  FESTLICH_GROUND,
  FESTLICH_TREE,
  GOLD_CORNER,
} from '@/lib/stimmts/style-themes';
import type { StyleId } from '@/lib/stimmts/styles';
import { cn } from '@/lib/utils';
import type { CSSProperties } from 'react';

// Every piece is drawn behind the result and ignores the pointer, so no
// ornament can cover or catch a tap meant for a control. None of it moves,
// so there is nothing for reduced motion to switch off.

const LAYER = 'pointer-events-none absolute';

/** Fibre and grain, and the binder holes punched down both edges. */
function PapierDecor() {
  const holes = (side: 'left' | 'right'): CSSProperties => ({
    backgroundImage: `radial-gradient(circle at ${side === 'left' ? '0' : '100%'} 50%, #cdb98d 6px, transparent 6.5px)`,
    backgroundSize: '12px 14px',
  });
  return (
    <>
      <span
        className={`${LAYER} inset-0`}
        style={{
          backgroundImage:
            'radial-gradient(rgba(110,80,30,0.13) 0.8px, transparent 1.3px), radial-gradient(rgba(110,80,30,0.09) 0.7px, transparent 1.2px), repeating-linear-gradient(0deg, rgba(110,80,30,0.04) 0 1px, transparent 1px 4px), repeating-linear-gradient(90deg, rgba(110,80,30,0.03) 0 1px, transparent 1px 7px)',
          backgroundSize: '6px 6px, 9px 9px, auto, auto',
          backgroundPosition: '0 0, 3px 4px, 0 0, 0 0',
          boxShadow: 'inset 0 0 40px rgba(150,110,40,0.28)',
        }}
      />
      <span className={`${LAYER} inset-y-0 left-0 w-3`} style={holes('left')} />
      <span
        className={`${LAYER} inset-y-0 right-0 w-3`}
        style={holes('right')}
      />
    </>
  );
}

/** The Reichstag dome as a line drawing above the result. */
function KuppelDecor() {
  return (
    <svg
      className={`${LAYER} left-1/2 top-5 -translate-x-1/2`}
      width="380"
      height="241"
      viewBox="0 0 300 190"
      fill="none"
      stroke="#7f9ab3"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="138" y="22" width="24" height="16" rx="2" />
      <path d="M150 12 V22" />
      <path d="M30 170 C30 92 88 38 150 38 C212 38 270 92 270 170" />
      <path d="M150 38 C118 58 92 110 88 170 M150 38 C132 70 120 120 119 170 M150 38 V170 M150 38 C182 58 208 110 212 170 M150 38 C168 70 180 120 181 170 M150 38 C100 56 58 110 56 170 M150 38 C200 56 242 110 244 170" />
      <path d="M44 128 Q150 146 256 128 M62 98 Q150 114 238 98 M88 70 Q150 84 212 70 M116 50 Q150 58 184 50" />
      <path d="M60 150 Q150 122 240 104" strokeDasharray="4 4" />
      <path d="M14 170 H286 M14 184 H286 M34 170 V184 M62 170 V184 M90 170 V184 M118 170 V184 M182 170 V184 M210 170 V184 M238 170 V184 M266 170 V184" />
    </svg>
  );
}

const NIGHT_STARS = [
  '8% 6%, #fff 0 1.2px, transparent 1.8px',
  '22% 14%, rgba(255,255,255,0.7) 0 1px, transparent 1.6px',
  '40% 4%, rgba(255,255,255,0.8) 0 1px, transparent 1.6px',
  '58% 11%, #fff 0 1.4px, transparent 2px',
  '92% 18%, rgba(255,255,255,0.7) 0 1px, transparent 1.6px',
  '12% 30%, rgba(255,255,255,0.6) 0 1px, transparent 1.6px',
  '86% 36%, #fff 0 1.2px, transparent 1.8px',
  '5% 48%, rgba(255,255,255,0.6) 0 1px, transparent 1.6px',
  '95% 55%, rgba(255,255,255,0.7) 0 1px, transparent 1.6px',
  '30% 24%, rgba(255,255,255,0.5) 0 0.8px, transparent 1.4px',
  '72% 27%, rgba(255,255,255,0.6) 0 1px, transparent 1.6px',
]
  .map((star) => `radial-gradient(circle at ${star})`)
  .join(', ');

/** Stars and a crescent moon over the dome's dark silhouette. */
function NachtDecor() {
  return (
    <>
      <span
        className={`${LAYER} inset-x-0 top-0 h-[640px]`}
        style={{ backgroundImage: NIGHT_STARS }}
      />
      <span
        className={`${LAYER} right-[26px] top-[22px] size-[34px] rounded-full shadow-[inset_-10px_-4px_0_0_#f1e9c8]`}
      />
      <svg
        className={`${LAYER} bottom-0 left-1/2 -translate-x-1/2`}
        width="390"
        height="247"
        viewBox="0 0 300 190"
      >
        <path
          d="M30 170 C30 92 88 38 150 38 C212 38 270 92 270 170 Z"
          fill="#141d40"
        />
        <rect x="138" y="22" width="24" height="16" rx="2" fill="#141d40" />
        <rect x="0" y="168" width="300" height="22" fill="#141d40" />
        <path
          d="M150 38 V170 M150 38 C118 58 92 110 88 170 M150 38 C182 58 208 110 212 170 M44 128 Q150 146 256 128 M62 98 Q150 114 238 98"
          stroke="#1d2a55"
          strokeWidth="1.2"
          fill="none"
        />
      </svg>
    </>
  );
}

/** Bulb positions along the light string, in the string's own coordinates. */
const BULBS: readonly [number, number][] = [
  [24, 29],
  [48, 33],
  [73, 29],
  [122, 31],
  [146, 35],
  [171, 31],
  [220, 31],
  [244, 35],
  [269, 31],
  [318, 31],
  [342, 34],
  [367, 29],
];

const TREE_LIGHTS: readonly [number, number][] = [
  [38, 36],
  [54, 40],
  [30, 62],
  [50, 58],
  [62, 66],
  [22, 92],
  [42, 86],
  [60, 92],
  [74, 94],
];

/** A string of lights, falling snow, a snowy ground and a lit tree. */
function FestlichDecor() {
  return (
    <>
      <span
        className={`${LAYER} inset-0`}
        style={{
          backgroundImage:
            'radial-gradient(circle, rgba(255,255,255,0.85) 0 1.3px, transparent 1.8px), radial-gradient(circle, rgba(255,255,255,0.6) 0 1.8px, transparent 2.4px), radial-gradient(circle, rgba(255,255,255,0.5) 0 0.9px, transparent 1.4px)',
          backgroundSize: '37px 41px, 61px 53px, 23px 29px',
          backgroundPosition: '0 0, 17px 9px, 9px 21px',
        }}
      />
      <svg
        className={`${LAYER} left-1/2 top-0 -translate-x-1/2`}
        width="390"
        height="56"
        viewBox="0 0 390 56"
        fill="none"
      >
        <path
          d="M-5 6 Q48 40 97 10 Q146 40 195 10 Q244 40 293 10 Q342 40 395 6"
          stroke="#6b5b45"
          strokeWidth="1.6"
        />
        {BULBS.map(([cx, cy]) => (
          <g key={cx}>
            <circle cx={cx} cy={cy} r="10" fill="rgba(255,210,120,0.32)" />
            <rect
              x={cx - 2.5}
              y={cy - 10}
              width="5"
              height="4"
              rx="1"
              fill="#6b5b45"
            />
            <ellipse cx={cx} cy={cy} rx="4.5" ry="6.5" fill="#ffe9b0" />
          </g>
        ))}
      </svg>
      <span
        className={`${LAYER} inset-x-[-15%] rounded-t-[50%] bg-[#e3eaec]`}
        style={{
          bottom: -FESTLICH_GROUND.sink,
          height: FESTLICH_GROUND.height,
        }}
      />
      <svg
        className={`${LAYER} right-[34px]`}
        style={{ bottom: FESTLICH_TREE.lift }}
        width={FESTLICH_TREE.width}
        height={FESTLICH_TREE.height}
        viewBox="0 0 90 120"
      >
        <polygon
          points="45,16 66,42 56,42 76,70 64,70 86,100 4,100 26,70 14,70 34,42 24,42"
          fill="#1d5a3c"
        />
        <path
          d="M24 42 L56 42 M14 70 L64 70"
          stroke="#e3eaec"
          strokeWidth="1.5"
          opacity="0.6"
        />
        <rect x="40" y="100" width="10" height="14" fill="#6b4528" />
        <polygon
          points="45,2 48,10 56,10 50,15 52,23 45,18 38,23 40,15 34,10 42,10"
          fill="#f4dc8e"
        />
        {TREE_LIGHTS.map(([cx, cy]) => (
          <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="2.6" fill="#fff1c4" />
        ))}
      </svg>
    </>
  );
}

const GOLD = '#c9a85c';

/** One corner of the frame; the other three are this one mirrored. */
function GoldCorner({
  className,
  style,
}: {
  className?: string;
  style: CSSProperties;
}) {
  return (
    <svg
      className={cn(LAYER, className)}
      style={style}
      width={GOLD_CORNER.size}
      height={GOLD_CORNER.size}
      viewBox="0 0 64 64"
      fill="none"
      stroke={GOLD}
      strokeWidth="2"
    >
      <path d="M4 60 V22 Q4 4 22 4 H60" />
      <path d="M12 60 V26 Q12 12 26 12 H60" strokeWidth="1" />
      <circle cx="18" cy="18" r="3.5" fill={GOLD} />
      <path d="M28 4 Q36 -2 44 4 M4 28 Q-2 36 4 44" strokeWidth="1.4" />
    </svg>
  );
}

/** Leaf ellipses of a laurel branch: cx, cy, rotation. */
const LAUREL_LEAVES: readonly [number, number, number][] = [
  [28, 96, -55],
  [40, 92, 5],
  [19, 84, -47],
  [31, 80, 13],
  [12, 70, -39],
  [24, 66, 21],
  [9, 56, -31],
  [21, 52, 29],
  [10, 42, -23],
  [22, 38, 37],
  [14, 28, -15],
  [26, 24, 45],
  [20, 16, -7],
  [32, 12, 53],
];

function Laurel({ className }: { className: string }) {
  return (
    <svg
      className={`${LAYER} ${className}`}
      width="32"
      height="70"
      viewBox="0 0 50 110"
      fill={GOLD}
    >
      <path d="M40 106 Q8 66 30 6" stroke={GOLD} strokeWidth="2" fill="none" />
      {LAUREL_LEAVES.map(([cx, cy, angle]) => (
        <ellipse
          key={`${cx}-${cy}`}
          cx={cx}
          cy={cy}
          rx="3.5"
          ry="8"
          transform={`rotate(${angle} ${cx} ${cy})`}
        />
      ))}
    </svg>
  );
}

/** A double gold rule round the panel, ornamented corners and laurels. */
function GoldDecor() {
  const inset = GOLD_CORNER.inset;
  return (
    <>
      <span
        className={`${LAYER} inset-0`}
        style={{
          boxShadow: `inset 0 0 0 7px #12100b, inset 0 0 0 9px ${GOLD}, inset 0 0 0 12px #12100b, inset 0 0 0 13px rgba(201,168,92,0.6)`,
        }}
      />
      <GoldCorner style={{ left: inset, top: inset }} />
      <GoldCorner
        className="-scale-x-100"
        style={{ right: inset, top: inset }}
      />
      <GoldCorner
        className="-scale-y-100"
        style={{ left: inset, bottom: inset }}
      />
      <GoldCorner
        className="-scale-100"
        style={{ right: inset, bottom: inset }}
      />
      <Laurel className="left-[78px] top-[46px]" />
      <Laurel className="right-[78px] top-[46px] -scale-x-100" />
    </>
  );
}

const DECOR: Record<Exclude<StyleId, 'standard'>, () => React.JSX.Element> = {
  papier: PapierDecor,
  kuppel: KuppelDecor,
  nacht: NachtDecor,
  festlich: FestlichDecor,
  gold: GoldDecor,
};

function StyleDecor({ style }: { style: StyleId }) {
  if (style === 'standard') {
    return null;
  }
  const Decor = DECOR[style];
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      <Decor />
    </div>
  );
}

export default StyleDecor;
