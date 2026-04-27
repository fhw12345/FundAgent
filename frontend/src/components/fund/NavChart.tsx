import { useState, useMemo } from "react";

export interface NAVPoint {
  date: string;
  nav: number;
  change_pct: number;
}

type Range = "week" | "month" | "year";

const RANGE_LABEL: Record<Range, string> = {
  week: "周",
  month: "月",
  year: "年",
};

const RANGE_DAYS: Record<Range, number> = {
  week: 5,
  month: 22,
  year: 250,
};

interface Props {
  points: NAVPoint[];
  defaultRange?: Range;
}

export default function NavChart({ points, defaultRange = "month" }: Props) {
  const [range, setRange] = useState<Range>(defaultRange);

  const sliced = useMemo(() => {
    const n = RANGE_DAYS[range];
    return points.slice(-n);
  }, [points, range]);

  if (sliced.length === 0) {
    return <div className="text-sm text-gray-400 py-8 text-center">暂无净值数据</div>;
  }

  const navValues = sliced.map((p) => p.nav);
  const minNav = Math.min(...navValues);
  const maxNav = Math.max(...navValues);
  const last = sliced[sliced.length - 1];
  const first = sliced[0];
  const periodChangePct = first.nav ? ((last.nav - first.nav) / first.nav) * 100 : 0;
  const isUp = periodChangePct >= 0;
  const strokeColor = isUp ? "#ef4444" : "#10b981";
  const fillId = isUp ? "navGradRed" : "navGradGreen";

  const W = 600;
  const H = 160;
  const PAD = 10;
  const range_v = maxNav - minNav || 1;
  const stepX = (W - PAD * 2) / (sliced.length - 1 || 1);

  const path = sliced
    .map((p, i) => {
      const x = PAD + i * stepX;
      const y = H - PAD - ((p.nav - minNav) / range_v) * (H - PAD * 2);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  const areaPath = `${path} L${(PAD + (sliced.length - 1) * stepX).toFixed(1)} ${H - PAD} L${PAD} ${H - PAD} Z`;

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs text-gray-500">
          区间涨幅{" "}
          <span className={isUp ? "text-red-600 font-medium" : "text-emerald-600 font-medium"}>
            {isUp ? "+" : ""}
            {periodChangePct.toFixed(2)}%
          </span>
        </div>
        <div className="flex items-center gap-1 bg-gray-50 rounded-lg p-0.5">
          {(["week", "month", "year"] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                range === r
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {RANGE_LABEL[r]}
            </button>
          ))}
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-40">
        <defs>
          <linearGradient id="navGradRed" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ef4444" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="navGradGreen" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill={`url(#${fillId})`} />
        <path
          d={path}
          fill="none"
          stroke={strokeColor}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>

      <div className="grid grid-cols-2 mt-2 text-xs text-gray-500">
        <div>
          最低 <span className="text-gray-700 font-medium">{minNav.toFixed(4)}</span>
        </div>
        <div className="text-right">
          最高 <span className="text-gray-700 font-medium">{maxNav.toFixed(4)}</span>
        </div>
      </div>
    </div>
  );
}
