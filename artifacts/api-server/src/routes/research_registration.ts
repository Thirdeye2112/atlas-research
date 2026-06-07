/**
 * index.ts — registration snippet
 * --------------------------------
 * Add these two lines to artifacts/api-server/src/index.ts
 *
 * 1. With the other route imports (top of file, after existing imports):
 *
 *      import { researchRouter } from './routes/research.js'
 *
 * 2. With the other app.use() calls (after existing route registrations):
 *
 *      app.use('/api/research', researchRouter)
 *
 * Also add to your .env (or Replit secrets):
 *
 *      DATABASE_URL_RESEARCH=postgresql://atlas:password@localhost:5432/atlas_research
 *
 * The research router uses a separate pg.Pool — it never touches Atlas Alpha's
 * Drizzle-managed database and cannot interfere with existing routes.
 *
 * Verify with:
 *   curl http://localhost:8080/api/research/metrics/latest
 */

// ── Existing imports (example) ──────────────────────────────
// import { stockRouter }    from './routes/stock.js'
// import { scannerRouter }  from './routes/scanner.js'
// import { marketRouter }   from './routes/market.js'
// import { watchlistRouter } from './routes/watchlist.js'
// import { backtestRouter } from './routes/backtest.js'

// ── ADD THIS ─────────────────────────────────────────────────
// import { researchRouter } from './routes/research.js'

// ── Existing app.use() calls (example) ──────────────────────
// app.use('/api/stock',     stockRouter)
// app.use('/api/scanner',   scannerRouter)
// app.use('/api/market',    marketRouter)
// app.use('/api/watchlist', watchlistRouter)
// app.use('/api/backtest',  backtestRouter)

// ── ADD THIS ─────────────────────────────────────────────────
// app.use('/api/research',  researchRouter)
