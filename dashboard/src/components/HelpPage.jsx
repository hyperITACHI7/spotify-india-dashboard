import { useState } from 'react';
import {
  BarChart2, TrendingUp, Cloud, Table2, MessageSquare,
  GitBranch, Bell, Lightbulb,
  Sparkles, Filter, RefreshCw, Star, ThumbsUp, ThumbsDown,
  ChevronDown, X, PlayCircle, Database, Wrench, TrendingDown,
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
  bar: (
    <div style={{display:'flex',flexDirection:'column',gap:'4px'}}>
      {[['Playlist limits',82,'#e74c3c'],['No ad skip',74,'#e74c3c'],['Offline broken',55,'#f1c40f'],['Discover Weekly',32,'#1db954']].map(([l,p,c])=>(
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
    <div style={{display:'flex',flexDirection:'column',gap:'6px'}}>
      <div style={{fontSize:'9px',color:'var(--text-subdued)',marginBottom:'2px'}}>FRUSTRATIONS</div>
      <div style={{display:'flex',flexWrap:'wrap',gap:'5px'}}>
        {[['no ad skip',13],['bad shuffle',9],['ads forced',11]].map(([w,s])=>(
          <span key={w} style={{fontSize:'11px',color:'#e74c3c',fontWeight:'700',padding:'2px 8px',borderRadius:'500px',background:'rgba(231,76,60,0.12)',border:'1px solid rgba(231,76,60,0.25)'}}>{w} <span style={{opacity:0.6,fontSize:'9px'}}>{s}</span></span>
        ))}
      </div>
      <div style={{fontSize:'9px',color:'var(--text-subdued)',marginBottom:'2px',marginTop:'4px'}}>PRAISE</div>
      <div style={{display:'flex',flexWrap:'wrap',gap:'5px'}}>
        {[['daily mix',14],['lyrics sync',8]].map(([w,s])=>(
          <span key={w} style={{fontSize:'11px',color:'#1db954',fontWeight:'700',padding:'2px 8px',borderRadius:'500px',background:'rgba(29,185,84,0.12)',border:'1px solid rgba(29,185,84,0.25)'}}>{w} <span style={{opacity:0.6,fontSize:'9px'}}>{s}</span></span>
        ))}
      </div>
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
  hypothesis: (
    <div style={{display:'flex',flexDirection:'column',gap:'6px'}}>
      <div style={{fontSize:'9px',color:'var(--text-subdued)',fontWeight:'700',textTransform:'uppercase'}}>H1 · Ads Experience</div>
      <div style={{fontSize:'10px',color:'var(--text-base)',lineHeight:'1.4'}}>Free-tier ad density is the single largest churn driver, cited in 84% of negative Ads reviews.</div>
      <div style={{padding:'5px 8px',background:'rgba(29,185,84,0.06)',borderRadius:'5px',border:'1px solid rgba(29,185,84,0.15)'}}>
        <div style={{fontSize:'8px',fontWeight:'700',color:'#1db954',textTransform:'uppercase',marginBottom:'2px'}}>Recommended Solution</div>
        <div style={{fontSize:'9px',color:'var(--text-base)'}}>Add a 5-second skip button after each ad for free-tier users.</div>
      </div>
    </div>
  ),
  synthesis: (
    <div style={{display:'flex',flexDirection:'column',gap:'6px'}}>
      {[['EXECUTIVE SUMMARY','#1db954'],['KEY PROBLEM AREAS','#1db954'],['ROOT CAUSE ANALYSIS','#1db954'],['RECOMMENDED ACTIONS','#1db954']].map(([l,c])=>(
        <div key={l} style={{fontSize:'8px',fontWeight:'700',color:c,letterSpacing:'0.06em'}}>{l}</div>
      ))}
    </div>
  ),
  datamode: (
    <div style={{display:'flex',gap:'6px'}}>
      <div style={{flex:1,padding:'8px',borderRadius:'6px',background:'rgba(29,185,84,0.08)',border:'1px solid rgba(29,185,84,0.3)',textAlign:'center'}}>
        <div style={{fontSize:'9px',fontWeight:'700',color:'#1db954'}}>LIVE</div>
        <div style={{fontSize:'8px',color:'var(--text-subdued)',marginTop:'2px'}}>Scraped data</div>
      </div>
      <div style={{flex:1,padding:'8px',borderRadius:'6px',background:'rgba(255,255,255,0.04)',border:'1px solid var(--divider)',textAlign:'center'}}>
        <div style={{fontSize:'9px',fontWeight:'700',color:'var(--text-subdued)'}}>SNAPSHOT</div>
        <div style={{fontSize:'8px',color:'var(--text-subdued)',marginTop:'2px'}}>10k frozen reviews</div>
      </div>
    </div>
  ),
  scrape: (
    <div>
      <div style={{fontSize:'9px',color:'#1db954',fontWeight:'700',marginBottom:'6px'}}>Stage 1 — Fetching + Sentiment (fast)</div>
      <div style={{height:'5px',background:'rgba(255,255,255,0.06)',borderRadius:'3px',overflow:'hidden',marginBottom:'8px'}}>
        <div style={{width:'100%',height:'100%',background:'#1db954',borderRadius:'3px'}}/>
      </div>
      <div style={{fontSize:'9px',color:'var(--text-subdued)',fontWeight:'700',marginBottom:'6px'}}>Stage 2 — NLP topic analysis (background)</div>
      <div style={{height:'5px',background:'rgba(255,255,255,0.06)',borderRadius:'3px',overflow:'hidden'}}>
        <div style={{width:'55%',height:'100%',background:'rgba(29,185,84,0.5)',borderRadius:'3px'}}/>
      </div>
      <div style={{fontSize:'8px',color:'var(--text-subdued)',marginTop:'4px'}}>Dashboard unlocks after Stage 1. Topics appear as NLP completes.</div>
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
};

// ─── Widget cards config ─────────────────────────────────────────────────────
const WIDGETS = [
  {
    group: 'Overview',
    items: [
      {
        icon: BarChart2, color: '#1db954', preview: 'kpi',
        title: 'KPI Cards',
        desc: 'Four headline numbers — total reviews, avg rating, sentiment score (−1 to +1), and % negative. Update instantly on every filter change.',
        tips: ['Sentiment below −0.1 is a warning sign. Below −0.3 is a P0 signal.', 'Avg rating and sentiment score can diverge — a 3★ average can still have highly negative sentiment if reviews are polarised.'],
        interact: null,
      },
      {
        icon: TrendingUp, color: '#1db954', preview: 'trend',
        title: 'Sentiment Trend',
        desc: 'Line chart showing how sentiment shifts over time. Use it to spot regressions after app updates and confirm whether issues are worsening or improving.',
        tips: ['A sudden dip usually follows a bad app update — confirm by switching the Version filter to that release.', 'Use "Last 30 Days" to zoom into recent events without noise from older reviews.'],
        interact: 'Hover the chart to see the exact sentiment score and review count for each time bucket.',
      },
    ],
  },
  {
    group: 'Topic Intelligence',
    items: [
      {
        icon: BarChart2, color: '#e74c3c', preview: 'bar',
        title: 'Top Issues Bar',
        desc: 'Horizontal bars ranking the most-mentioned issue labels by volume, extracted by the NLP pipeline from high-severity negative reviews. Red = complaint; green = praise.',
        tips: ['This only populates after NLP has run (scrape required for live mode).', 'Filter to 1-star reviews to isolate the harshest feedback and see which issues spike.'],
        interact: null,
      },
      {
        icon: Table2, color: '#1db954', preview: 'matrix',
        title: 'Topic Sentiment Matrix',
        desc: 'One row per topic — review count, % negative, trend direction, and an AI-generated or rule-based summary of the core issue. NLP must complete for summaries to appear.',
        tips: ['% negative above 60 with high volume = P0 fix.', 'The trend arrow shows whether the topic is getting worse (↑ negative) or better over the last 7 days vs prior period.', 'Summaries are generated by Groq LLM if credits are available, otherwise by a rule-based extractor.'],
        interact: 'Click any row to filter Review Excerpts to that topic. The page auto-scrolls down to the review list. Green left border = selected topic.',
      },
      {
        icon: GitBranch, color: '#a855f7', preview: 'hierarchy',
        title: 'Topic Hierarchy Explorer',
        desc: 'Expands each topic into its specific sub-issues with review counts and % negative per sub-topic. Shows which sub-topic is most painful before you read a single review.',
        tips: ['The green badge on each topic row shows how many sub-topics have real review data.', 'Rows labelled "no data yet" are taxonomy-defined categories that no scraped review matched — expected for niche topics.'],
        interact: 'Click a topic row to expand it. Sub-topics with data show review count and % negative.',
      },
    ],
  },
  {
    group: 'Review Exploration',
    items: [
      {
        icon: Cloud, color: '#f1c40f', preview: 'keywords',
        title: 'Keyword Buzz',
        desc: 'NLP-extracted issue labels sorted into two tabs: Frustrations (issues appearing mostly in negative reviews) and Praise (issues appearing mostly in positive reviews). Max 3 words per label for reliable matching.',
        tips: ['Labels are extracted by the NLP pipeline — they reflect what the AI identified as the core issue in each review, not just words that appear in the text.', 'A label appearing in both negative and positive reviews defaults to Frustrations.', 'This only shows meaningful data after NLP has run on scraped reviews.'],
        interact: 'Click any label to filter Review Excerpts to reviews the NLP linked to that issue. Click again or press ✕ to clear. Charts do NOT reload — only the review list updates.',
      },
      {
        icon: MessageSquare, color: '#3b82f6', preview: 'reviews',
        title: 'Review Excerpts',
        desc: 'The actual review text, one card per review, with star rating, sentiment badge, date, platform, and NLP-extracted issue tags. Sits directly below the Topic Matrix and auto-scrolls there when you click a topic row.',
        tips: ['Filter to 1–2 stars + a specific topic to find the most actionable critical feedback.', '1-star reviews are never marked Positive — the sentiment engine is rating-aware and overrides VADER for extreme ratings.', 'The issue tags on each card come from LLM extraction (first 20 reviews after scraping) or the rule-based extractor (remaining reviews).'],
        interact: 'Click a topic row in the Matrix above — the page scrolls here and filters automatically. Combine with a Keyword Buzz click for pinpoint results.',
      },
    ],
  },
  {
    group: 'AI Features',
    items: [
      {
        icon: Bell, color: '#e74c3c', preview: null,
        title: 'Alerts',
        desc: 'Auto-generated CRITICAL / WARNING / INFO signals based on statistical thresholds — negative sentiment spikes, rating drops, version regressions, and anomaly events.',
        tips: ['CRITICAL = investigate today. WARNING = monitor. INFO = healthy signal.', 'Alerts dynamically respect your active filters — filter to a specific version to see its alerts only.'],
        interact: null,
      },
      {
        icon: Lightbulb, color: '#f1c40f', preview: 'hypothesis',
        title: 'AI Hypothesis Cards',
        desc: 'Five grounded product hypotheses generated by Groq after reading the full topic matrix, worst review excerpts, trends, and clusters. Each card includes: evidence (specific numbers), a concrete solution, expected metric impact, and an A/B experiment design.',
        tips: ['Hypotheses only generate after NLP has populated the topic matrix — the "topic analysis still running" state appears otherwise.', 'Evidence cites real numbers from the data (e.g. "38 reviews, 76% negative") — not invented.', 'High-confidence hypotheses have strong evidence in the data; Low-confidence are exploratory starting points.'],
        interact: null,
      },
      {
        icon: Sparkles, color: '#1db954', preview: 'synthesis',
        title: 'AI Synthesis',
        desc: 'A structured 4-section product briefing generated by Groq from the full cross-topic analysis: Executive Summary → Key Problem Areas → Root Cause Analysis → Recommended Product Actions. Uses real topic volumes, negative percentages, and review excerpts.',
        tips: ['Each section is grounded in the actual data — problem areas cite topic names and percentages, not generic observations.', 'Recommended Actions are concrete and implementable (not vague like "improve UX") with named success criteria.', 'Apply filters before loading — the synthesis only analyses what is currently visible.'],
        interact: null,
      },
    ],
  },
  {
    group: 'Controls',
    items: [
      {
        icon: Filter, color: '#1db954', preview: 'filters',
        title: 'Filter Bar',
        desc: 'Narrows ALL widgets by Timeframe / App Version / Star Rating / Platform. Active filters appear as dismissible chips. Yellow chips (Keyword Buzz selection, Topic selection) only affect the review list — charts do not reload.',
        tips: ['Green chips = global filters (reload all charts). Yellow chips = review list drill-down only.', 'Search has a 300ms debounce — type naturally without triggering per-keystroke reloads.'],
        interact: 'Click ✕ on any chip to remove that filter individually. "Reset all" clears everything including topic and keyword selections.',
      },
      {
        icon: Database, color: '#3b82f6', preview: 'datamode',
        title: 'Data Mode',
        desc: 'Two modes: Snapshot (10,000 frozen Spotify India reviews, always available, instant load — great for exploring the dashboard) and Live (uses your most recently scraped data, requires at least one scrape).',
        tips: ['Snapshot mode is the default on first load — no scraping needed.', 'Switching modes clears all AI caches so Hypothesis Cards and AI Synthesis regenerate from the new dataset.', 'Live mode shows a "no data" state until you scrape at least once in the current session.'],
        interact: 'The mode indicator (SNAPSHOT / LIVE) is in the top header. Click it or use the Scrape modal to switch.',
      },
      {
        icon: RefreshCw, color: '#1db954', preview: 'scrape',
        title: 'Scrape Live Reviews',
        desc: 'Pulls fresh Play Store + App Store reviews in two stages. Stage 1 (fast): fetches reviews and runs VADER sentiment — dashboard unlocks immediately. Stage 2 (background): NLP pipeline runs topic extraction, issue labelling, and AI summaries while you explore.',
        tips: ['The dashboard is usable after Stage 1 completes. Topic widgets show a progress bar while Stage 2 runs in the background.', 'LLM extraction is capped at 20 reviews per scrape to stay within Groq free-tier limits — the 20 most negative reviews are prioritised. The rest get rule-based issue extraction.', 'Start with 50–100 reviews for a quick refresh. Larger scrapes give richer topic data but take longer for Stage 2 to complete.'],
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
            AI-powered intelligence from live Spotify India reviews. Click any widget card below to learn what it shows and how to interact with it.
          </p>
        </div>
      </div>

      {/* ── Quick-start flow ────────────────────────────────────────────── */}
      <div style={{ marginBottom: '36px' }}>
        <p style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-subdued)', marginBottom: '14px' }}>
          Get started in 4 steps
        </p>
        {/* auto-fit collapses to 2×2 on mobile instead of squishing 4 columns */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1px', background: 'var(--divider)', borderRadius: '12px', overflow: 'hidden' }}>
          {[
            { n: '01', icon: Database,   t: 'Choose a mode',   d: 'Start in Snapshot for an instant demo with 10k reviews, or scrape live data for real-time analysis.' },
            { n: '02', icon: Filter,     t: 'Apply filters',   d: 'Narrow by date range, app version, star rating, or platform to focus on what matters.' },
            { n: '03', icon: Table2,     t: 'Explore topics',  d: 'Click a row in the Topic Matrix. The page scrolls to matching reviews automatically.' },
            { n: '04', icon: Sparkles,   t: 'Read AI insights', d: 'Hypothesis Cards give concrete product fixes. AI Synthesis gives the full executive briefing.' },
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
