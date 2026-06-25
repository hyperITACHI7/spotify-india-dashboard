import { useState } from 'react';
import {
  BarChart2, TrendingUp, PieChart, Cloud, Table2, MessageSquare,
  GitBranch, Bell, Layers, ArrowUpRight, AlertTriangle, Lightbulb,
  Sparkles, Filter, RefreshCw, Star, ThumbsUp, ThumbsDown,
  ChevronDown, X, PlayCircle,
} from 'lucide-react';

// ─── Mini SVG trend line ────────────────────────────────────────────────────
function SparkLine({ color = 'var(--spotify-green)' }) {
  const pts = [55, 50, 58, 45, 52, 60, 57, 65, 62, 70, 68, 75];
  const w = 80, h = 32, pad = 2;
  const max = Math.max(...pts), min = Math.min(...pts);
  const x = (i) => pad + (i / (pts.length - 1)) * (w - pad * 2);
  const y = (v) => h - pad - ((v - min) / (max - min || 1)) * (h - pad * 2);
  const d = pts.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  return (
    <svg width={w} height={h}>
      <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.9" />
    </svg>
  );
}

// ─── Mini donut ─────────────────────────────────────────────────────────────
function MiniDonut() {
  const r = 18, cx = 22, cy = 22, sw = 7;
  const circ = 2 * Math.PI * r;
  const slices = [
    { pct: 42, color: '#1db954' },
    { pct: 30, color: '#e74c3c' },
    { pct: 28, color: '#f1c40f' },
  ];
  let off = 0;
  return (
    <svg width={44} height={44}>
      {slices.map((s, i) => {
        const dash = (s.pct / 100) * circ;
        const el = <circle key={i} cx={cx} cy={cy} r={r} fill="none"
          stroke={s.color} strokeWidth={sw}
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeDashoffset={-(off / 100) * circ}
          transform={`rotate(-90 ${cx} ${cy})`} />;
        off += s.pct;
        return el;
      })}
    </svg>
  );
}

// ─── Card preview visuals ────────────────────────────────────────────────────
const PREVIEW = {
  kpi: (
    <div style={{ display: 'flex', gap: '6px' }}>
      {[['Reviews','8.2k','var(--text-base)'],['Avg Rating','3.2★','#f1c40f'],['Sentiment','-0.18','#e74c3c'],['Neg %','38%','#e74c3c']].map(([l,v,c],i)=>(
        <div key={i} style={{flex:1,background:'rgba(255,255,255,0.06)',borderRadius:'6px',padding:'6px 8px'}}>
          <div style={{fontSize:'9px',color:'var(--text-subdued)',marginBottom:'2px'}}>{l}</div>
          <div style={{fontSize:'14px',fontWeight:'900',color:c}}>{v}</div>
        </div>
      ))}
    </div>
  ),
  trend: (
    <div style={{display:'flex',alignItems:'flex-end',gap:'8px'}}>
      <SparkLine />
      <div style={{fontSize:'11px',color:'var(--spotify-green)',fontWeight:'700'}}>↑ +12%</div>
    </div>
  ),
  donut: (
    <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
      <MiniDonut />
      <div style={{fontSize:'9px',display:'flex',flexDirection:'column',gap:'3px'}}>
        {[['42%','Positive','#1db954'],['30%','Negative','#e74c3c'],['28%','Neutral','#f1c40f']].map(([p,l,c])=>(
          <div key={l} style={{display:'flex',alignItems:'center',gap:'4px'}}>
            <span style={{width:6,height:6,borderRadius:'50%',background:c,display:'inline-block'}}/>
            <span style={{color:'var(--text-subdued)'}}>{p} {l}</span>
          </div>
        ))}
      </div>
    </div>
  ),
  bar: (
    <div style={{display:'flex',flexDirection:'column',gap:'4px'}}>
      {[['Playlist restrictions',82,'#e74c3c'],['Excessive ads',74,'#e74c3c'],['Offline broken',55,'#f1c40f'],['Great Daily Mix',32,'#1db954']].map(([l,p,c])=>(
        <div key={l}>
          <div style={{display:'flex',justifyContent:'space-between',fontSize:'9px',color:'var(--text-subdued)',marginBottom:'2px'}}>
            <span>{l}</span><span>{p}%</span>
          </div>
          <div style={{height:'4px',background:'rgba(255,255,255,0.06)',borderRadius:'2px',overflow:'hidden'}}>
            <div style={{width:`${p}%`,height:'100%',background:c,borderRadius:'2px'}}/>
          </div>
        </div>
      ))}
    </div>
  ),
  keywords: (
    <div style={{display:'flex',flexWrap:'wrap',gap:'5px'}}>
      {[['playlist',15,'#e74c3c'],['ads',13,'#e74c3c'],['discover',14,'#1db954'],['algorithm',11,'#f1c40f'],['crash',12,'#e74c3c'],['offline',10,'#f1c40f'],['lyrics',9,'#1db954']].map(([w,s,c])=>(
        <span key={w} style={{fontSize:`${s}px`,color:c,fontWeight:'700'}}>{w}</span>
      ))}
    </div>
  ),
  matrix: (
    <div style={{borderRadius:'6px',overflow:'hidden',border:'1px solid var(--divider)'}}>
      {[['Song Discovery',62,'#e74c3c',true],['Playlists & Lib',71,'#e74c3c',false],['Ads Experience',84,'#e74c3c',false]].map(([t,n,c,sel])=>(
        <div key={t} style={{display:'flex',alignItems:'center',gap:'6px',padding:'5px 8px',background:sel?'rgba(29,185,84,0.08)':'transparent',borderLeft:sel?'2px solid #1db954':'2px solid transparent',borderBottom:'1px solid var(--divider)',fontSize:'9px'}}>
          <span style={{flex:1,color:'var(--text-base)',fontWeight:sel?'700':'400'}}>{t}</span>
          <span style={{color:c,fontWeight:'700'}}>{n}%</span>
        </div>
      ))}
    </div>
  ),
  reviews: (
    <div style={{display:'flex',flexDirection:'column',gap:'4px'}}>
      {[[1,'#e74c3c','NEG','Playlist limited to 3 songs on free plan…'],[5,'#1db954','POS','Discover Weekly nailed it this week!']].map(([s,c,l,t])=>(
        <div key={t} style={{padding:'6px 8px',background:'rgba(255,255,255,0.03)',border:'1px solid var(--divider)',borderRadius:'6px'}}>
          <div style={{display:'flex',justifyContent:'space-between',marginBottom:'3px'}}>
            <div style={{display:'flex',gap:'1px'}}>{Array.from({length:5}).map((_,i)=><Star key={i} size={8} fill={i<s?'#f1c40f':'none'} color={i<s?'#f1c40f':'var(--divider)'}/>)}</div>
            <span style={{fontSize:'8px',fontWeight:'700',padding:'1px 5px',borderRadius:'500px',background:`${c}20`,color:c}}>{l}</span>
          </div>
          <p style={{fontSize:'9px',color:'var(--text-subdued)',margin:0}}>{t}</p>
        </div>
      ))}
    </div>
  ),
  hierarchy: (
    <div style={{borderRadius:'6px',overflow:'hidden',border:'1px solid var(--divider)'}}>
      {[['Song Discovery','10 sub-topics',true,false],['↳ Recommendation relevance','193 reviews',false,true],['↳ Repetitive suggestions','169 reviews',false,true]].map(([l,b,bold,sub])=>(
        <div key={l} style={{display:'flex',justifyContent:'space-between',padding:sub?'4px 8px 4px 20px':'6px 8px',background:bold?'rgba(29,185,84,0.06)':'transparent',borderBottom:'1px solid var(--divider)',fontSize:'9px'}}>
          <span style={{color:'var(--text-base)',fontWeight:bold?'700':'400'}}>{l}</span>
          <span style={{color: bold ? 'var(--spotify-green)' : 'var(--text-subdued)',fontWeight:bold?'700':'400',fontSize:'8px'}}>{b}</span>
        </div>
      ))}
    </div>
  ),
  filters: (
    <div style={{display:'flex',flexWrap:'wrap',gap:'4px'}}>
      {[['Last 30 Days','#1db954'],['v9.0.2','#1db954'],['1–2 Stars','#1db954'],['Topic: Playlists','#f1c40f']].map(([l,c])=>(
        <div key={l} style={{display:'flex',alignItems:'center',gap:'3px',padding:'2px 8px',borderRadius:'500px',background:`${c}18`,border:`1px solid ${c}40`,fontSize:'9px',fontWeight:'700',color:c}}>
          {l}<X size={7}/>
        </div>
      ))}
    </div>
  ),
  scrape: (
    <div>
      <div style={{height:'6px',background:'rgba(255,255,255,0.06)',borderRadius:'3px',overflow:'hidden',marginBottom:'4px'}}>
        <div style={{width:'75%',height:'100%',background:'#1db954',borderRadius:'3px'}}/>
      </div>
      <div style={{fontSize:'9px',color:'var(--text-subdued)',display:'flex',justifyContent:'space-between'}}>
        <span>Deep AI analysis: 120/200 reviews…</span><span>75%</span>
      </div>
    </div>
  ),
};

// ─── Widget cards config ─────────────────────────────────────────────────────
const WIDGETS = [
  {
    group: 'Overview',
    items: [
      {
        icon: BarChart2, color: '#1db954', preview: 'kpi',
        title: 'KPI Cards',
        desc: 'Four headline numbers — total reviews, avg rating, sentiment score, and % negative.',
        tips: ['Sentiment ranges from −1 to +1. Below −0.1 is a warning.', 'These update whenever you change a filter.'],
        interact: null,
      },
      {
        icon: TrendingUp, color: '#1db954', preview: 'trend',
        title: 'Sentiment Trend',
        desc: 'Line chart showing how sentiment shifts over time. Spot regressions after updates.',
        tips: ['A sudden dip usually follows a bad app update — confirm with the Version filter.', 'Use "Last 30 Days" to zoom in on recent events.'],
        interact: 'Hover the chart to see the exact sentiment and review count for each period.',
      },
      {
        icon: PieChart, color: '#f1c40f', preview: 'donut',
        title: 'Sentiment Donut',
        desc: 'Splits reviews into Positive, Negative, and Neutral at a glance.',
        tips: ['Red (Negative) above 35% of the circle needs attention.', 'Neutral reviews are often mixed — worth reading to understand fence-sitters.'],
        interact: null,
      },
    ],
  },
  {
    group: 'Topic Intelligence',
    items: [
      {
        icon: BarChart2, color: '#e74c3c', preview: 'bar',
        title: 'Top Issues Bar',
        desc: 'Horizontal bars ranking the most-mentioned complaint categories by volume.',
        tips: ['Red bars = complaints; green bars = praise.', 'Filter to 1-star reviews to isolate the harshest feedback.'],
        interact: null,
      },
      {
        icon: Table2, color: '#1db954', preview: 'matrix',
        title: 'Topic Sentiment Matrix',
        desc: 'One row per topic — review count, avg sentiment, % positive/negative, trend, and an AI-generated core issue summary.',
        tips: ['Red % negative above 60 with high volume = P0 fix.', 'The Core Issue Summary is generated from real review text, not labels.'],
        interact: 'Click a row to filter the Review Excerpts below to that topic. The page auto-scrolls. Green left border = selected.',
      },
      {
        icon: GitBranch, color: '#a855f7', preview: 'hierarchy',
        title: 'Topic Hierarchy',
        desc: 'Expands each topic into specific sub-issues. Shows which sub-topics have the most negative reviews.',
        tips: ['The green badge shows how many sub-topics have real review data before you expand.', 'Dimmed rows with "no data yet" are taxonomy-defined but unmatched in current reviews.'],
        interact: 'Click a topic row to expand it. Sub-topics with data show review count and % negative.',
      },
    ],
  },
  {
    group: 'Review Exploration',
    items: [
      {
        icon: Cloud, color: '#f1c40f', preview: 'keywords',
        title: 'Keyword Cloud',
        desc: 'Most-used words sized by frequency. Red = appears in negative reviews; green = positive.',
        tips: ['Large red words are your priority action items.', 'Clicking a keyword does NOT reload the charts — only the review list updates.'],
        interact: 'Click any word to filter Review Excerpts to only reviews containing it. Click again or press ✕ to clear.',
      },
      {
        icon: MessageSquare, color: '#3b82f6', preview: 'reviews',
        title: 'Review Excerpts',
        desc: 'The actual review text, one card per review, with star rating, sentiment badge, date, platform, and extracted issue tags.',
        tips: ['Filter to 1–2 stars + a topic to find the most actionable critical feedback.', '1-star reviews are never marked Positive — the sentiment engine is rating-aware.'],
        interact: 'Select a topic in the Matrix above to pre-filter. Combine with a keyword for pinpoint results.',
      },
    ],
  },
  {
    group: 'AI Features',
    items: [
      {
        icon: Bell, color: '#e74c3c', preview: null,
        title: 'Alerts',
        desc: 'Auto-generated CRITICAL / WARNING / INFO signals based on statistical thresholds.',
        tips: ['CRITICAL = fix today. WARNING = monitor. INFO = healthy.', 'Alerts dynamically respect your active filters.'],
        interact: null,
      },
      {
        icon: Layers, color: '#a855f7', preview: null,
        title: 'Priority Matrix',
        desc: 'Issues plotted on Volume vs Severity axes. Top-right quadrant = fix first.',
        tips: ['High severity + low volume = edge case but risky (e.g. data loss).', 'Low severity + high volume = hurts perception even if non-critical.'],
        interact: null,
      },
      {
        icon: AlertTriangle, color: '#f1c40f', preview: null,
        title: 'Anomaly Alerts',
        desc: 'Statistical anomaly detection — flags days or versions that deviate from baseline.',
        tips: ['Anomalies usually appear 1–2 days after an app update ships.', 'Cross-reference with the Trend chart to confirm spike vs trend shift.'],
        interact: null,
      },
      {
        icon: Lightbulb, color: '#f1c40f', preview: null,
        title: 'Hypothesis Cards',
        desc: 'AI-generated "if-then" hypotheses based on data patterns — starting points for A/B test ideas.',
        tips: ['Low-confidence hypotheses are exploratory. Treat them as questions, not answers.'],
        interact: null,
      },
      {
        icon: Sparkles, color: '#1db954', preview: null,
        title: 'AI Synthesis',
        desc: 'A 200–300 word narrative summary of the entire visible dataset, written by Groq after analysing hundreds of reviews.',
        tips: ['Best read after applying filters — it summarises only what is currently visible.', 'If Groq credits are exhausted a rule-based summary is shown instead.'],
        interact: 'Click "Regenerate" to refresh with the current filter context.',
      },
    ],
  },
  {
    group: 'Controls',
    items: [
      {
        icon: Filter, color: '#1db954', preview: 'filters',
        title: 'Filter Bar & Active Context',
        desc: 'Narrows ALL widgets by Timeframe / App Version / Rating / Platform / Keyword. Active filters show as dismissible chips.',
        tips: ['Green chips = global (affect all widgets). Yellow chips = review list only — no chart reload.', 'Search has a 300 ms debounce — type naturally.'],
        interact: 'Click ✕ on any chip to remove just that filter. "Reset all" clears everything.',
      },
      {
        icon: RefreshCw, color: '#1db954', preview: 'scrape',
        title: 'Scrape Live Reviews',
        desc: 'Fetches fresh Play Store + App Store reviews, runs VADER sentiment analysis, then optionally runs Groq LLM deep analysis.',
        tips: ['Stages: Fetching → Analyzing Sentiment → Deep AI Analysis.', 'If Groq credits run out the bar stops at Deep AI Analysis — VADER data is still saved.', 'Scrape 100–500 for a quick refresh; 1 000+ for a thorough session.'],
        interact: null,
      },
    ],
  },
];

// ─── Single widget card ──────────────────────────────────────────────────────
function WidgetCard({ icon: Icon, color, preview, title, desc, tips, interact }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      onClick={() => setOpen(o => !o)}
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${open ? color + '40' : 'var(--divider)'}`,
        borderRadius: '12px',
        cursor: 'pointer',
        transition: 'border-color 0.2s, background 0.2s',
        overflow: 'hidden',
      }}
      onMouseEnter={e => { if (!open) e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; }}
      onMouseLeave={e => { if (!open) e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
    >
      {/* Card header */}
      <div style={{ padding: '16px 18px', display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
        <div style={{
          width: 36, height: 36, borderRadius: '8px', flexShrink: 0,
          background: `${color}18`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={18} color={color} />
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
            <span style={{ fontWeight: '700', fontSize: '13px', color: 'var(--text-base)' }}>{title}</span>
            <ChevronDown size={14} color="var(--text-subdued)" style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', flexShrink: 0 }} />
          </div>
          <p style={{ fontSize: '11px', color: 'var(--text-subdued)', margin: '4px 0 0', lineHeight: 1.5 }}>{desc}</p>
        </div>
      </div>

      {/* Expanded detail */}
      {open && (
        <div style={{ borderTop: `1px solid ${color}25`, padding: '14px 18px 16px', background: `${color}06` }}>

          {/* Preview */}
          {preview && PREVIEW[preview] && (
            <div style={{ padding: '12px', background: 'rgba(0,0,0,0.25)', borderRadius: '8px', marginBottom: '12px' }}>
              {PREVIEW[preview]}
            </div>
          )}

          {/* Interaction hint */}
          {interact && (
            <div style={{
              display: 'flex', gap: '8px', alignItems: 'flex-start',
              padding: '8px 10px', borderRadius: '8px',
              background: 'rgba(29,185,84,0.08)', border: '1px solid rgba(29,185,84,0.2)',
              marginBottom: '10px',
            }}>
              <span style={{ fontSize: '12px', flexShrink: 0 }}>🖱️</span>
              <span style={{ fontSize: '11px', color: 'var(--text-base)', lineHeight: 1.5 }}>{interact}</span>
            </div>
          )}

          {/* Tips */}
          {tips?.length > 0 && (
            <ul style={{ margin: 0, padding: '0 0 0 16px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
              {tips.map((t, i) => (
                <li key={i} style={{ fontSize: '11px', color: 'var(--text-subdued)', lineHeight: 1.5 }}>{t}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────
export default function HelpPage() {
  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', paddingBottom: '60px' }}>

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(29,185,84,0.15) 0%, rgba(0,0,0,0) 60%)',
        border: '1px solid rgba(29,185,84,0.15)',
        borderRadius: '16px',
        padding: '32px 36px',
        marginBottom: '36px',
        display: 'flex',
        alignItems: 'center',
        gap: '24px',
      }}>
        <div style={{ width: 56, height: 56, borderRadius: '14px', background: 'rgba(29,185,84,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <PlayCircle size={32} color="var(--spotify-green)" />
        </div>
        <div>
          <h2 style={{ fontSize: '26px', fontWeight: '900', letterSpacing: '-0.02em', marginBottom: '6px' }}>
            How to Use Discovery
          </h2>
          <p style={{ color: 'var(--text-subdued)', fontSize: '13px', lineHeight: 1.6, maxWidth: '540px' }}>
            Automated intelligence from live Spotify India reviews. Click any widget card below to learn what it shows and how to interact with it.
          </p>
        </div>
      </div>

      {/* ── Quick-start flow ────────────────────────────────────────────── */}
      <div style={{ marginBottom: '36px' }}>
        <p style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-subdued)', marginBottom: '14px' }}>
          Get started in 4 steps
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1px', background: 'var(--divider)', borderRadius: '12px', overflow: 'hidden' }}>
          {[
            { n: '01', icon: RefreshCw, t: 'Scrape data',    d: 'Click "Scrape Live Reviews" in the header to pull fresh app store reviews.' },
            { n: '02', icon: Filter,    t: 'Apply filters',  d: 'Narrow by date, version, star rating, or platform using the filter bar.' },
            { n: '03', icon: Table2,    t: 'Pick a topic',   d: 'Click a row in the Topic Matrix to filter reviews to that category.' },
            { n: '04', icon: Sparkles,  t: 'Read insights',  d: 'Dig into Review Excerpts, AI summaries, and Hypothesis Cards.' },
          ].map(({ n, icon: I, t, d }, i) => (
            <div key={i} style={{ background: 'var(--bg-elevated)', padding: '20px 18px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <span style={{ fontSize: '11px', fontWeight: '900', color: 'var(--spotify-green)', fontVariantNumeric: 'tabular-nums' }}>{n}</span>
                <I size={14} color="var(--spotify-green)" />
              </div>
              <div style={{ fontWeight: '700', fontSize: '13px', color: 'var(--text-base)', marginBottom: '4px' }}>{t}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-subdued)', lineHeight: 1.5 }}>{d}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Colour legend ───────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: '20px', marginBottom: '36px', flexWrap: 'wrap' }}>
        {[
          [ThumbsUp,   '#1db954', 'Positive sentiment'],
          [ThumbsDown, '#e74c3c', 'Negative sentiment'],
          [null,       '#f1c40f', 'Neutral / mixed'],
        ].map(([I, c, l], i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-subdued)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: c, display: 'inline-block', flexShrink: 0 }} />
            {l}
          </div>
        ))}
      </div>

      {/* ── Widget groups ────────────────────────────────────────────────── */}
      {WIDGETS.map(({ group, items }) => (
        <div key={group} style={{ marginBottom: '32px' }}>
          <p style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-subdued)', marginBottom: '12px' }}>
            {group}
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '12px', alignItems: 'start' }}>
            {items.map(card => <WidgetCard key={card.title} {...card} />)}
          </div>
        </div>
      ))}
    </div>
  );
}
