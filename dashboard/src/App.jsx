import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import API_URL from './config';
import { BarChart2, HelpCircle, ChevronLeft, ChevronRight, RefreshCw, ChevronDown, Database, Archive } from 'lucide-react';

const SpotifyLogo = ({ size = 32 }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="#1DB954" xmlns="http://www.w3.org/2000/svg" aria-label="Spotify">
    <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
  </svg>
);
import FilterPanel from './components/FilterPanel';
import ActiveContextBar from './components/ActiveContextBar';
import OverviewKpis from './components/OverviewKpis';
import TrendLineChart from './components/TrendLineChart';
import TopicSentimentMatrix from './components/TopicSentimentMatrix';
import TopIssuesBar from './components/TopIssuesBar';
import KeywordCloud from './components/KeywordCloud';
import DrillDownReviews from './components/DrillDownReviews';
import AlertsWidget from './components/AlertsWidget';
import AiSummaryCard from './components/AiSummaryCard';
import HypothesisCards from './components/HypothesisCards';
import TopicHierarchy from './components/TopicHierarchy';
import HelpPage from './components/HelpPage';

export default function App() {
  // ── Global filter states (affect ALL widgets) ──────────────────────────
  const [dateRange, setDateRange] = useState('All');
  const [version,   setVersion]   = useState('All');
  const [rating,    setRating]    = useState('All');
  const [platform,  setPlatform]  = useState('All');
  const [search,    setSearch]    = useState('');

  // ── Drill-down states (scope ONLY the review list at the bottom) ────────
  // These are intentionally NOT in the main useEffect dependency array so
  // clicking a topic row or a buzzword never triggers a full dashboard reload.
  const [selectedTopic,   setSelectedTopic]   = useState(null);
  const [selectedKeyword, setSelectedKeyword] = useState('');

  // ── UI states ───────────────────────────────────────────────────────────
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [activeNav, setActiveNav] = useState('discovery'); // 'discovery' | 'help'

  // ── Data mode ───────────────────────────────────────────────────────────
  const [dataMode, setDataMode] = useState(() => localStorage.getItem('dataMode') || 'snapshot');
  const [modeInfo, setModeInfo] = useState(null); // {snapshot: {reviews, scraped_at}, live: ...}
  const [modeMenuOpen, setModeMenuOpen] = useState(false);
  const modeMenuRef = useRef(null);
  // Gate: stats fetch must not run until the mode POST has been confirmed server-side.
  // Without this, stats and mode-sync race on every page load, causing the server's
  // default "snapshot" mode to answer the stats request before the POST arrives.
  const [modeReady, setModeReady] = useState(false);

  // ── Scraping states ─────────────────────────────────────────────────────
  const [sourceType,     setSourceType]     = useState('fallback_mock');
  const [isScraping,     setIsScraping]     = useState(false);
  const [showScrapeModal, setShowScrapeModal] = useState(false);
  const [scrapeLimit,    setScrapeLimit]    = useState(100);
  const [scrapeProgress, setScrapeProgress] = useState({
    status: 'idle', stage: '', current: 0, total: 0, message: '',
  });

  // ── Data states ─────────────────────────────────────────────────────────
  const [stats,    setStats]    = useState(null);
  const [matrix,   setMatrix]   = useState([]);
  const [keywords, setKeywords] = useState({ positive: [], negative: [] });
  const [loading,  setLoading]  = useState(true);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // ── Ref to scroll DrillDownReviews into view when a topic is selected ──
  const drilldownRef = useRef(null);

  // ── Sync mode to backend on mount and when dataMode changes ────────────
  // Sets modeReady=false to block stats while the mode POST is in flight,
  // then sets modeReady=true once the server confirms — which fires the stats fetch.
  useEffect(() => {
    setModeReady(false);
    axios.post(`${API_URL}/api/discovery/mode`, { mode: dataMode })
      .then(() => axios.get(`${API_URL}/api/discovery/mode`))
      .then(res => {
        setModeInfo(res.data.data);
        setModeReady(true);
      })
      .catch(() => setModeReady(true));
  }, [dataMode]);

  const handleModeChange = (newMode) => {
    localStorage.setItem('dataMode', newMode);
    setDataMode(newMode);
    // No setRefreshTrigger here — changing dataMode triggers the mode sync effect above,
    // which sets modeReady=true and fires the stats fetch automatically.
  };

  // Close mode menu on outside click
  useEffect(() => {
    const handler = (e) => {
      if (modeMenuRef.current && !modeMenuRef.current.contains(e.target)) {
        setModeMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ── Main data fetch ─────────────────────────────────────────────────────
  // selectedKeyword and selectedTopic are intentionally excluded — they only
  // affect the review list, not the charts / matrix / KPIs above it.
  useEffect(() => {
    if (!modeReady) return; // wait for mode POST to be confirmed before fetching
    setLoading(true);
    const params = {
      date_range: dateRange,
      version,
      rating,
      platform,
      search,
    };

    Promise.all([
      axios.get(`${API_URL}/api/discovery/stats`,    { params }),
      axios.get(`${API_URL}/api/discovery/topics`,   { params }),
      axios.get(`${API_URL}/api/discovery/keywords`, { params }),
    ])
      .then(([statsRes, topicsRes, keywordsRes]) => {
        setStats(statsRes.data.data);
        setMatrix(topicsRes.data.data);
        setKeywords(keywordsRes.data.data);
        setSourceType(statsRes.data.data.source_type || 'fallback_mock');
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load dashboard data:', err);
        setLoading(false);
      });
  }, [modeReady, dateRange, version, rating, platform, search, refreshTrigger]);

  // ── Filter handlers ─────────────────────────────────────────────────────
  const handleApplyFilters = (newFilters) => {
    setDateRange(newFilters.dateRange);
    setVersion(newFilters.version);
    setRating(newFilters.rating);
    setPlatform(newFilters.platform);
    setSearch(newFilters.search);
  };

  // Clear a single global filter without touching drill-down state
  const handleClearFilter = (key) => {
    handleApplyFilters({
      dateRange, version, rating, platform, search,
      [key]: key === 'search' ? '' : 'All',
    });
  };

  const handleResetFilters = () => {
    setDateRange('All');
    setVersion('All');
    setRating('All');
    setPlatform('All');
    setSearch('');
    setSelectedTopic(null);
    setSelectedKeyword('');
  };

  const handleRefresh = () => setRefreshTrigger(prev => prev + 1);

  // ── Topic selection with auto-scroll ───────────────────────────────────
  const handleSelectTopic = (topicId) => {
    setSelectedTopic(topicId);
    if (topicId && drilldownRef.current) {
      // Small delay so React renders the updated DrillDownReviews before scroll
      setTimeout(() => {
        drilldownRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 80);
    }
  };

  // ── Scrape flow ─────────────────────────────────────────────────────────
  const handleTriggerScrape = () => {
    if (isScraping) return;
    setIsScraping(true);
    setShowScrapeModal(false);
    setScrapeProgress({ status: 'running', stage: 'starting', current: 0, total: scrapeLimit, message: 'Starting scrape...' });

    axios.post(`${API_URL}/api/discovery/scrape?limit=${scrapeLimit}`)
      .then(res => {
        if (res.data.status === 'error') {
          setIsScraping(false);
          setScrapeProgress({ status: 'idle', stage: '', current: 0, total: 0, message: '' });
          alert(res.data.message);
          return;
        }
        if (res.data.status === 'started' || res.data.status === 'already_running') {
          // Track previous stage in closure so we can detect the ingestion→nlp transition
          let prevStage = '';
          const pollInterval = setInterval(() => {
            axios.get(`${API_URL}/api/discovery/scrape-progress`)
              .then(progRes => {
                const prog = progRes.data;
                setScrapeProgress(prog);
                // Refresh as soon as VADER-enriched data lands in the DB (before slow NLP)
                if (prevStage === 'ingestion' && prog.stage === 'nlp') {
                  handleRefresh();
                }
                prevStage = prog.stage;
                if (prog.status === 'completed') {
                  clearInterval(pollInterval);
                  handleRefresh();
                  setTimeout(() => {
                    setIsScraping(false);
                    setScrapeProgress({ status: 'idle', stage: '', current: 0, total: 0, message: '' });
                  }, 2000);
                } else if (prog.status === 'error') {
                  clearInterval(pollInterval);
                  setIsScraping(false);
                  setScrapeProgress({ status: 'idle', stage: '', current: 0, total: 0, message: '' });
                  alert('Scrape failed: ' + prog.message);
                }
              })
              .catch(() => {});
          }, 600);
        } else {
          handleRefresh();
          setIsScraping(false);
        }
      })
      .catch(err => {
        console.error('Scraper start failed:', err);
        setIsScraping(false);
        setScrapeProgress({ status: 'idle', stage: '', current: 0, total: 0, message: '' });
      });
  };

  const getSelectedTopicLabel = () => {
    if (!selectedTopic) return '';
    const row = matrix.find(r => r.id === selectedTopic);
    return row ? row.label : '';
  };

  // ── Shared filter props passed to widgets that need them ────────────────
  const filterProps = { dateRange, version, rating, platform, search };

  return (
    <div className="app-container">
      {/* ── Sidebar ───────────────────────────────────────────────────── */}
      <nav className={`sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
        {/* Logo area */}
        <div className="sidebar-logo-area">
          {!isSidebarCollapsed && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <SpotifyLogo size={32} />
              <span style={{ fontSize: '20px', fontWeight: '900', letterSpacing: '-0.01em', color: 'var(--text-base)' }}>
                Spotify
              </span>
            </div>
          )}
          {isSidebarCollapsed && <SpotifyLogo size={28} />}
          {!isSidebarCollapsed && (
            <button
              onClick={() => setIsSidebarCollapsed(v => !v)}
              style={{ background: 'none', border: 'none', color: 'var(--text-subdued)', cursor: 'pointer', display: 'flex', alignItems: 'center', padding: '4px', borderRadius: '4px', flexShrink: 0 }}
              onMouseOver={e => e.currentTarget.style.color = 'var(--text-base)'}
              onMouseOut={e  => e.currentTarget.style.color = 'var(--text-subdued)'}
              title="Collapse sidebar"
            >
              <ChevronLeft size={18} />
            </button>
          )}
        </div>

        {/* Expand button when collapsed */}
        {isSidebarCollapsed && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '4px 8px 8px' }}>
            <button
              onClick={() => setIsSidebarCollapsed(false)}
              style={{ background: 'none', border: 'none', color: 'var(--text-subdued)', cursor: 'pointer', display: 'flex', padding: '4px', borderRadius: '4px' }}
              onMouseOver={e => e.currentTarget.style.color = 'var(--text-base)'}
              onMouseOut={e  => e.currentTarget.style.color = 'var(--text-subdued)'}
              title="Expand sidebar"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        )}

        {/* Nav */}
        <div className="sidebar-nav">
          <div
            className={`nav-item ${activeNav === 'discovery' ? 'active' : ''}`}
            onClick={() => setActiveNav('discovery')}
            title={isSidebarCollapsed ? 'Discovery' : ''}
          >
            <BarChart2 size={22} />
            {!isSidebarCollapsed && <span>Discovery</span>}
          </div>
          <div
            className={`nav-item ${activeNav === 'help' ? 'active' : ''}`}
            onClick={() => setActiveNav('help')}
            title={isSidebarCollapsed ? 'How to Use' : ''}
          >
            <HelpCircle size={22} />
            {!isSidebarCollapsed && <span>How to Use</span>}
          </div>
        </div>

        {/* ── Login prompt ── */}
        <div style={{
          padding: '16px 8px',
          borderTop: '1px solid rgba(255,255,255,0.07)',
          marginTop: 'auto',
        }}>
          {isSidebarCollapsed ? (
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <div style={{
                width: '32px', height: '32px', borderRadius: '50%',
                backgroundColor: 'rgba(255,255,255,0.08)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: 'pointer',
              }}
                title="Log in to Spotify"
                onMouseEnter={e => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.14)'}
                onMouseLeave={e => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.08)'}
              >
                <svg viewBox="0 0 24 24" width="16" height="16" fill="var(--text-subdued)">
                  <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/>
                </svg>
              </div>
            </div>
          ) : (
            <div style={{ padding: '0 4px' }}>
              <p style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-base)', marginBottom: '4px' }}>
                Preview Spotify
              </p>
              <p style={{ fontSize: '11px', color: 'var(--text-subdued)', marginBottom: '16px', lineHeight: '1.4' }}>
                Log in to access all features
              </p>
              <button className="pill-button" style={{ width: '100%', justifyContent: 'center', padding: '10px 16px', fontSize: '13px' }}>
                Log in
              </button>
              <button style={{
                width: '100%', marginTop: '8px',
                background: 'transparent', border: '1px solid rgba(255,255,255,0.3)',
                borderRadius: '500px', padding: '10px 16px',
                fontSize: '13px', fontWeight: '700', color: 'var(--text-subdued)',
                cursor: 'pointer', transition: 'border-color 0.15s, color 0.15s',
              }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--text-base)'; e.currentTarget.style.color = 'var(--text-base)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.3)'; e.currentTarget.style.color = 'var(--text-subdued)'; }}
              >
                Sign up
              </button>
            </div>
          )}
        </div>
      </nav>

      {/* ── Main view ─────────────────────────────────────────────────── */}
      <main className="main-view">

        {/* ── Help page ─────────────────────────────────────────────── */}
        {activeNav === 'help' && <HelpPage />}

        {/* ── Discovery dashboard ───────────────────────────────────── */}
        {activeNav === 'discovery' && <>

        {/* Header */}
        <header style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h2 style={{ fontSize: '32px', fontWeight: '900', letterSpacing: '-0.02em' }}>Indian Market: Discovery Analysis</h2>
            <p style={{ color: 'var(--text-subdued)', marginTop: '4px' }}>Automated insights from live App Store &amp; Play Store reviews</p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '4px' }}>
            {/* Custom data mode dropdown */}
            <div ref={modeMenuRef} style={{ position: 'relative' }}>
              {/* Trigger pill */}
              <button
                onClick={() => setModeMenuOpen(v => !v)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '8px',
                  padding: '6px 12px 6px 14px',
                  borderRadius: '500px',
                  backgroundColor: dataMode === 'snapshot' ? 'rgba(241,196,15,0.08)' : 'rgba(29,185,84,0.08)',
                  border: `1px solid ${dataMode === 'snapshot' ? 'rgba(241,196,15,0.3)' : 'rgba(29,185,84,0.3)'}`,
                  color: dataMode === 'snapshot' ? '#f1c40f' : 'var(--spotify-green)',
                  fontSize: '12px', fontWeight: '700', cursor: 'pointer',
                  background: dataMode === 'snapshot' ? 'rgba(241,196,15,0.08)' : 'rgba(29,185,84,0.08)',
                  outline: 'none', whiteSpace: 'nowrap',
                  transition: 'border-color 0.15s, background 0.15s',
                }}
              >
                <span style={{
                  width: '7px', height: '7px', borderRadius: '50%', flexShrink: 0,
                  backgroundColor: dataMode === 'snapshot' ? '#f1c40f' : 'var(--spotify-green)',
                  boxShadow: dataMode === 'snapshot' ? '0 0 6px #f1c40f' : '0 0 6px var(--spotify-green)',
                }} />
                {dataMode === 'snapshot' ? 'Offline Snapshot' : 'Live Database'}
                <ChevronDown size={13} style={{
                  flexShrink: 0,
                  transform: modeMenuOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.2s',
                }} />
              </button>

              {/* Dropdown panel */}
              {modeMenuOpen && (
                <div style={{
                  position: 'absolute', top: 'calc(100% + 8px)', left: 0,
                  zIndex: 200, minWidth: '260px',
                  backgroundColor: '#1a1a2e',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '10px',
                  padding: '6px',
                  boxShadow: '0 12px 40px rgba(0,0,0,0.6)',
                }}>
                  {/* Snapshot option */}
                  <button
                    onClick={() => { handleModeChange('snapshot'); setModeMenuOpen(false); }}
                    style={{
                      width: '100%', display: 'flex', alignItems: 'flex-start', gap: '10px',
                      padding: '10px 12px', borderRadius: '7px', border: 'none', cursor: 'pointer',
                      backgroundColor: dataMode === 'snapshot' ? 'rgba(241,196,15,0.1)' : 'transparent',
                      textAlign: 'left', transition: 'background 0.15s',
                    }}
                    onMouseEnter={e => { if (dataMode !== 'snapshot') e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)'; }}
                    onMouseLeave={e => { if (dataMode !== 'snapshot') e.currentTarget.style.backgroundColor = 'transparent'; }}
                  >
                    <Archive size={15} color="#f1c40f" style={{ marginTop: '2px', flexShrink: 0 }} />
                    <div>
                      <div style={{ fontSize: '13px', fontWeight: '700', color: '#f1c40f', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        Offline Snapshot
                        {dataMode === 'snapshot' && (
                          <span style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '500px', backgroundColor: 'rgba(241,196,15,0.15)', color: '#f1c40f', fontWeight: '700' }}>Active</span>
                        )}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-subdued)', marginTop: '2px' }}>
                        {modeInfo?.snapshot
                          ? `${modeInfo.snapshot.reviews.toLocaleString()} reviews · frozen dataset`
                          : '10,000 reviews · frozen dataset'}
                      </div>
                      <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.3)', marginTop: '3px' }}>
                        Scraping disabled in this mode
                      </div>
                    </div>
                  </button>

                  <div style={{ height: '1px', backgroundColor: 'rgba(255,255,255,0.07)', margin: '4px 6px' }} />

                  {/* Live option */}
                  <button
                    onClick={() => { handleModeChange('live'); setModeMenuOpen(false); }}
                    style={{
                      width: '100%', display: 'flex', alignItems: 'flex-start', gap: '10px',
                      padding: '10px 12px', borderRadius: '7px', border: 'none', cursor: 'pointer',
                      backgroundColor: dataMode === 'live' ? 'rgba(29,185,84,0.1)' : 'transparent',
                      textAlign: 'left', transition: 'background 0.15s',
                    }}
                    onMouseEnter={e => { if (dataMode !== 'live') e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)'; }}
                    onMouseLeave={e => { if (dataMode !== 'live') e.currentTarget.style.backgroundColor = 'transparent'; }}
                  >
                    <Database size={15} color="var(--spotify-green)" style={{ marginTop: '2px', flexShrink: 0 }} />
                    <div>
                      <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--spotify-green)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        Live Database
                        {dataMode === 'live' && (
                          <span style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '500px', backgroundColor: 'rgba(29,185,84,0.15)', color: 'var(--spotify-green)', fontWeight: '700' }}>Active</span>
                        )}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-subdued)', marginTop: '2px' }}>
                        Scrape fresh reviews from the Play & App Store
                      </div>
                      <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.3)', marginTop: '3px' }}>
                        Snapshot data is preserved when you switch back
                      </div>
                    </div>
                  </button>
                </div>
              )}
            </div>

            <button
              onClick={() => (isScraping || dataMode === 'snapshot') ? null : setShowScrapeModal(true)}
              disabled={isScraping || dataMode === 'snapshot'}
              title={dataMode === 'snapshot' ? 'Switch to Live Database mode to scrape new reviews' : ''}
              className="pill-button"
              style={{ padding: '8px 20px', fontSize: '12px', opacity: (isScraping || dataMode === 'snapshot') ? 0.4 : 1, cursor: (isScraping || dataMode === 'snapshot') ? 'not-allowed' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
            >
              {isScraping && <RefreshCw size={14} className="spin" />}
              {isScraping ? 'Scraping live data...' : 'Scrape Live Reviews'}
            </button>
          </div>
        </header>

        {/* Scrape progress bar */}
        {isScraping && scrapeProgress.status === 'running' && (() => {
          const pct = scrapeProgress.total > 0
            ? Math.min(100, Math.round((scrapeProgress.current / scrapeProgress.total) * 100))
            : 0;
          const stageLabel =
            scrapeProgress.stage === 'starting'   ? 'Starting...'       :
            scrapeProgress.stage === 'ingestion'  ? (
              scrapeProgress.message.includes('Play Store')  ? 'Fetching Play Store' :
              scrapeProgress.message.includes('App Store')   ? 'Fetching App Store'  :
              scrapeProgress.message.includes('Analyzing')   ? 'Analyzing Sentiment' :
              scrapeProgress.message.includes('Storing')     ? 'Storing Reviews'     :
              'Ingesting Reviews'
            ) :
            scrapeProgress.stage === 'nlp' ? 'Deep AI Analysis' : 'Processing';
          return (
            <div style={{ marginBottom: '20px', padding: '16px 20px', borderRadius: '12px', backgroundColor: 'rgba(29, 185, 84, 0.06)', border: '1px solid rgba(29, 185, 84, 0.2)', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <RefreshCw size={14} className="spin" style={{ color: 'var(--spotify-green)' }} />
                  <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--spotify-green)' }}>{stageLabel}</span>
                </div>
                <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-base)' }}>{pct}%</span>
              </div>
              <div style={{ width: '100%', height: '10px', backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: '5px', overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, height: '100%', background: 'var(--spotify-green)', borderRadius: '5px', transition: 'width 0.5s ease-out' }} />
              </div>
              <p style={{ fontSize: '11px', color: 'var(--text-subdued)', margin: 0 }}>{scrapeProgress.message}</p>
            </div>
          );
        })()}

        {/* Scrape completion flash */}
        {scrapeProgress.status === 'completed' && (
          <div style={{ marginBottom: '20px', padding: '12px 20px', borderRadius: '12px', backgroundColor: 'rgba(29, 185, 84, 0.1)', border: '1px solid rgba(29, 185, 84, 0.25)', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '16px' }}>&#x2705;</span>
            <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--spotify-green)' }}>
              Scrape complete! {scrapeProgress.total} reviews fetched and analyzed. Dashboard is refreshing...
            </span>
          </div>
        )}

        {/* Global filter controls */}
        <FilterPanel
          dateRange={dateRange}
          version={version}
          rating={rating}
          platform={platform}
          search={search}
          onApply={handleApplyFilters}
          onReset={handleResetFilters}
        />

        {/* Active context bar — shows all active filters + drill-down chips in one line */}
        <ActiveContextBar
          dateRange={dateRange}
          version={version}
          rating={rating}
          platform={platform}
          search={search}
          selectedTopic={selectedTopic}
          selectedTopicLabel={getSelectedTopicLabel()}
          selectedKeyword={selectedKeyword}
          onClearFilter={handleClearFilter}
          onClearTopic={() => setSelectedTopic(null)}
          onClearKeyword={() => setSelectedKeyword('')}
          onResetAll={handleResetFilters}
        />

        {loading && !stats ? (
          <div style={{ padding: '80px 0', textAlign: 'center' }}>
            <p className="loading" style={{ fontSize: '18px' }}>Loading Spotify Discovery Dashboard...</p>
          </div>
        ) : (
          <>
            {/* ── 1. KPI Cards ──────────────────────────────────────── */}
            {stats && <OverviewKpis stats={stats} />}

            {/* ── 2. Trend chart + Sentiment donut ─────────────────── */}
            <div style={{ marginBottom: '24px' }}>
              {stats && <TrendLineChart trend={stats.trend} />}
            </div>

            {/* ── 3. Top issues bar + Keyword cloud ────────────────── */}
            <div className="issues-keywords-row">
              <div className="issues-keywords-card">{matrix && <TopIssuesBar matrix={matrix} />}</div>
              <div className="issues-keywords-card">
                <KeywordCloud
                  keywords={keywords}
                  selectedKeyword={selectedKeyword}
                  onSelectKeyword={setSelectedKeyword}
                />
              </div>
            </div>

            {/* ── 4. Topic Sentiment Matrix ─────────────────────────── */}
            <TopicSentimentMatrix
              matrix={matrix}
              selectedTopic={selectedTopic}
              onSelectTopic={handleSelectTopic}
            />

            {/* ── 5. Review drill-down (moved directly below matrix) ── */}
            {/* Scrolled into view automatically when a topic is selected */}
            <div ref={drilldownRef} style={{ scrollMarginTop: '16px' }}>
              <DrillDownReviews
                {...filterProps}
                selectedTopic={selectedTopic}
                onSelectTopic={handleSelectTopic}
                selectedTopicLabel={getSelectedTopicLabel()}
                selectedKeyword={selectedKeyword}
                refreshTrigger={refreshTrigger}
              />
            </div>

            {/* ── 6. Topic hierarchy (drill into sub-topics) ───────── */}
            <TopicHierarchy
              matrix={matrix}
              {...filterProps}
            />

            {/* ── 7. Alerts (actionable signal) ────────────────────── */}
            <div style={{ marginBottom: '24px' }}>
              <AlertsWidget
                stats={stats}
                {...filterProps}
                refreshTrigger={refreshTrigger}
                onRefresh={() => setRefreshTrigger(r => r + 1)}
              />
            </div>

            {/* ── 8. Hypothesis cards ──────────────────────────────── */}
            <HypothesisCards {...filterProps} refreshTrigger={refreshTrigger} />

            {/* ── 12. AI synthesis (deep analysis, read once/session) ─ */}
            <div style={{ marginBottom: '24px' }}>
              <AiSummaryCard {...filterProps} refreshTrigger={refreshTrigger} />
            </div>
          </>
        )}

        </> /* end dashboard */}
      </main>

      {/* ── Scrape modal ─────────────────────────────────────────────── */}
      {showScrapeModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="card" style={{ width: '400px', backgroundColor: 'var(--bg-elevated)', zIndex: 1001 }}>
            <h3 style={{ marginBottom: '16px', fontSize: '20px' }}>Scrape Live Reviews</h3>
            <p style={{ color: 'var(--text-subdued)', marginBottom: '24px', fontSize: '14px' }}>
              Select how many recent reviews to fetch and analyze. Larger amounts will take more time.
            </p>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontSize: '14px', fontWeight: 'bold' }}>Number of Reviews</span>
              <span style={{ fontSize: '14px', color: 'var(--spotify-green)', fontWeight: 'bold' }}>
                {scrapeLimit === 10000 ? 'All Data (10k+)' : scrapeLimit}
              </span>
            </div>

            <input
              type="range" min="100" max="10000" step="100"
              value={scrapeLimit}
              onChange={(e) => setScrapeLimit(parseInt(e.target.value))}
              style={{ width: '100%', marginBottom: '24px', accentColor: 'var(--spotify-green)' }}
            />

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '16px' }}>
              <button
                onClick={() => setShowScrapeModal(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-base)', cursor: 'pointer', fontWeight: 'bold', fontSize: '14px' }}
              >
                Cancel
              </button>
              <button onClick={handleTriggerScrape} className="pill-button" style={{ padding: '8px 24px' }}>
                Start Scraping
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Mobile bottom navigation (hidden on desktop via CSS) ──── */}
      <nav className="mobile-bottom-nav">
        <div
          className={`mobile-nav-item ${activeNav === 'discovery' ? 'active' : ''}`}
          onClick={() => setActiveNav('discovery')}
        >
          <BarChart2 size={22} />
          <span>Discovery</span>
        </div>
        <div
          className={`mobile-nav-item ${activeNav === 'help' ? 'active' : ''}`}
          onClick={() => setActiveNav('help')}
        >
          <HelpCircle size={22} />
          <span>How to Use</span>
        </div>
      </nav>
    </div>
  );
}
