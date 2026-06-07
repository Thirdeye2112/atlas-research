/**
 * App.tsx — registration snippet
 * --------------------------------
 * Add the Research Lab page to Atlas Alpha's navigation and router.
 * PLACEMENT: artifacts/api-client-react/src/App.tsx
 *
 * The nav currently has 4 items: Dashboard | Scanner | Lab | Bot Lab
 * Add Research as a 5th item.
 *
 * ── 1. Add import (with other page imports) ──────────────────
 *
 *    import ResearchLab from './pages/ResearchLab'
 *
 * ── 2. Add route (inside your <Routes> or router config) ─────
 *
 *    <Route path="/research" element={<ResearchLab />} />
 *
 * ── 3. Add nav link (in your navigation component) ───────────
 *
 *    Example if Atlas Alpha uses a nav array pattern:
 *
 *    const navItems = [
 *      { path: '/',         label: 'Dashboard' },
 *      { path: '/scanner',  label: 'Scanner'   },
 *      { path: '/lab',      label: 'Lab'       },
 *      { path: '/bot-lab',  label: 'Bot Lab'   },
 *      { path: '/research', label: 'Research'  },  // ← ADD THIS
 *    ]
 *
 *    Example if Atlas Alpha uses inline JSX nav links:
 *
 *    <NavLink to="/research">Research</NavLink>
 *
 * ── 4. No other changes needed ───────────────────────────────
 *
 *    The Research page fetches exclusively from /api/research/*
 *    All data comes from the Research Engine DB (separate Postgres instance).
 *    It does not call any existing Atlas Alpha API endpoints.
 *    It has no side effects on Atlas Alpha's DB or in-memory state.
 *
 * ── 5. Verify ────────────────────────────────────────────────
 *
 *    Navigate to /research in your browser.
 *    If DATABASE_URL_RESEARCH is set and the Research Engine is running,
 *    the health panel should populate within 1–2 seconds.
 *
 *    If you see the yellow error banner, check:
 *      - DATABASE_URL_RESEARCH env var is set in your .env or Replit secrets
 *      - The atlas_research PostgreSQL instance is running
 *      - The atlas_research DB has data (run backfill first)
 */

// No code to add here — this file is instructions only.
// See the comments above for the exact lines to add in App.tsx.
