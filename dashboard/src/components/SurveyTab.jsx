import { useState, useEffect } from 'react';
import { ExternalLink, ClipboardList, RefreshCw } from 'lucide-react';

const GOOGLE_FORM_URL  = 'https://forms.gle/9bbPY6W8S6HbuGmi9';
const GOOGLE_SHEET_ID  = '1JWM_qYtFULNIYO0BBTWZhGFbS8728NVo5FmctLdRHk4';
const GOOGLE_SHEET_GID = '1062731436';

const SHEET_URL = `https://docs.google.com/spreadsheets/d/${GOOGLE_SHEET_ID}/gviz/tq?tqx=out:json&gid=${GOOGLE_SHEET_GID}`;

// ── Parsing ───────────────────────────────────────────────────────────────────

function parseSheetsResponse(raw) {
  const json = JSON.parse(raw.replace(/^[^{]+/, '').replace(/[^}]+$/, ''));
  const rows = json.table.rows.map(r =>
    r.c.map(cell => (cell && cell.v !== null && cell.v !== undefined ? cell.v : ''))
  );
  return rows;
}

// Splits all rows into blocks separated by empty rows.
// Each block starting with a "COUNTA of …" cell is a pivot table.
function parsePivotBlocks(rows) {
  const blocks = [];
  let current = [];

  for (const row of rows) {
    const hasContent = row.some(c => c !== '' && c !== null && c !== undefined);
    if (!hasContent) {
      if (current.length > 0) { blocks.push(current); current = []; }
    } else {
      current.push(row);
    }
  }
  if (current.length > 0) blocks.push(current);

  return blocks
    .filter(b => b.length >= 3 && String(b[0][0]).toLowerCase().startsWith('counta'))
    .map(block => {
      const [titleRow, headerRow, ...dataRows] = block;
      const colDimension = String(titleRow[1] || '').trim();
      const rowDimension = String(headerRow[0] || '').trim();
      // Collect non-empty column labels (skip first cell which is the row dimension name)
      const colLabels = headerRow
        .slice(1)
        .map(c => String(c === null || c === undefined ? '' : c).trim())
        .filter(c => c !== '');
      return { colDimension, rowDimension, colLabels, dataRows };
    });
}

// ── Cross-tab table component ─────────────────────────────────────────────────

function CrossTabTable({ block }) {
  const { rowDimension, colDimension, colLabels, dataRows } = block;

  return (
    <div className="card" style={{ marginBottom: '24px' }}>
      <div style={{ marginBottom: '16px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: '700' }}>
          {rowDimension}
          <span style={{ color: 'var(--text-subdued)', fontWeight: '400', margin: '0 8px' }}>×</span>
          {colDimension}
        </h3>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table className="table-container">
          <thead>
            <tr>
              <th style={{ minWidth: '160px' }}>{rowDimension}</th>
              {colLabels.map((label, i) => (
                <th key={i} style={{ textAlign: 'right', minWidth: '80px' }}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataRows.map((row, i) => {
              const label     = String(row[0] ?? '');
              const isTotal   = label.toLowerCase().includes('grand total');
              const values    = Array.from({ length: colLabels.length }, (_, j) => row[j + 1]);

              return (
                <tr
                  key={i}
                  className="table-row"
                  style={isTotal ? { borderTop: `1px solid var(--divider)` } : {}}
                >
                  <td style={{
                    fontSize: '13px',
                    fontWeight: isTotal ? '700' : '500',
                    color: isTotal ? 'var(--text-base)' : 'var(--text-subdued)',
                  }}>
                    {label}
                  </td>
                  {values.map((val, j) => {
                    const empty = val === '' || val === null || val === undefined;
                    return (
                      <td key={j} style={{
                        textAlign: 'right',
                        fontWeight: isTotal ? '700' : '400',
                        color: empty
                          ? 'var(--text-essential-subdued)'
                          : isTotal
                            ? 'var(--spotify-green)'
                            : 'var(--text-base)',
                      }}>
                        {empty ? '—' : val}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function SurveyTab() {
  const [blocks, setBlocks]         = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [lastFetched, setLastFetched] = useState(null);
  const [fetchTrigger, setFetchTrigger] = useState(0);

  const fetchData = () => {
    setLoading(true);
    setError('');
    setFetchTrigger(t => t + 1);
  };

  useEffect(() => {
    let cancelled = false;
    fetch(SHEET_URL)
      .then(r => r.text())
      .then(raw => {
        if (cancelled) return;
        const rows   = parseSheetsResponse(raw);
        const parsed = parsePivotBlocks(rows);
        setBlocks(parsed);
        setLastFetched(new Date());
      })
      .catch(() => {
        if (!cancelled) setError(
          'Could not load sheet data. Make sure the Google Sheet is shared as "Anyone with the link → Viewer".'
        );
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fetchTrigger]);

  return (
    <div>
      {/* Header */}
      <header style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '32px', fontWeight: '900', letterSpacing: '-0.02em' }}>User Research</h2>
        <p style={{ color: 'var(--text-subdued)', marginTop: '4px' }}>
          Survey responses from Spotify India users · live from Google Sheets
        </p>
      </header>

      {/* Contribute banner */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
        gap: '16px', flexWrap: 'wrap',
        padding: '20px 24px', borderRadius: '8px', marginBottom: '32px',
        background: 'linear-gradient(135deg, rgba(29,185,84,0.12) 0%, rgba(29,185,84,0.04) 100%)',
        border: '1px solid rgba(29,185,84,0.2)',
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
          <ClipboardList size={22} color="var(--spotify-green)" style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <p style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-base)', marginBottom: '4px' }}>
              Want to contribute your insights?
            </p>
            <p style={{ fontSize: '13px', color: 'var(--text-subdued)', lineHeight: '1.5' }}>
              Take our 2-minute survey about your Spotify experience in India. Your responses help shape product decisions directly.
            </p>
          </div>
        </div>
        <a
          href={GOOGLE_FORM_URL}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '7px',
            padding: '10px 20px', borderRadius: '500px',
            backgroundColor: 'var(--spotify-green)', color: '#000',
            fontSize: '13px', fontWeight: '700',
            textDecoration: 'none', flexShrink: 0,
            transition: 'background-color 0.1s, transform 0.1s',
          }}
          onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'var(--spotify-green-hover)'; e.currentTarget.style.transform = 'scale(1.04)'; }}
          onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'var(--spotify-green)'; e.currentTarget.style.transform = 'scale(1)'; }}
        >
          Open Survey <ExternalLink size={13} />
        </a>
      </div>

      {/* Results header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <h3 style={{ fontSize: '18px', fontWeight: '700' }}>Survey Results</h3>
        <button
          onClick={fetchData}
          disabled={loading}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            background: 'transparent', border: 'none',
            color: 'var(--text-subdued)', fontSize: '12px', fontWeight: '700',
            cursor: loading ? 'default' : 'pointer', transition: 'color 0.15s',
          }}
          onMouseEnter={e => { if (!loading) e.currentTarget.style.color = 'var(--text-base)'; }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-subdued)'; }}
        >
          <RefreshCw size={13} className={loading ? 'spin' : ''} />
          {lastFetched
            ? `Updated ${lastFetched.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
            : 'Refresh'}
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <p className="loading" style={{ textAlign: 'center', padding: '48px 0' }}>
          Loading survey data…
        </p>
      )}

      {/* Error */}
      {!loading && error && (
        <div style={{
          padding: '16px', borderRadius: '8px', marginBottom: '24px',
          backgroundColor: 'rgba(231,76,60,0.06)', border: '1px solid rgba(231,76,60,0.2)',
          display: 'flex', gap: '10px', alignItems: 'flex-start',
        }}>
          <span style={{ fontSize: '16px' }}>⚠️</span>
          <p style={{ fontSize: '13px', color: 'var(--text-subdued)', lineHeight: '1.5' }}>{error}</p>
        </div>
      )}

      {/* Pivot tables */}
      {!loading && !error && blocks.length > 0 &&
        blocks.map((block, i) => <CrossTabTable key={i} block={block} />)
      }

      {/* No pivot tables found */}
      {!loading && !error && blocks.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '48px 32px' }}>
          <ClipboardList size={40} color="var(--text-essential-subdued)" style={{ margin: '0 auto 16px' }} />
          <p style={{ fontSize: '16px', fontWeight: '700', marginBottom: '8px' }}>No pivot tables found</p>
          <p style={{ fontSize: '13px', color: 'var(--text-subdued)', maxWidth: '400px', margin: '0 auto', lineHeight: '1.6' }}>
            Make sure your pivot tables start with a "COUNTA of…" header cell and are separated by an empty row between each table.
          </p>
        </div>
      )}
    </div>
  );
}
