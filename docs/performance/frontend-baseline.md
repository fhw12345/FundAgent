# Frontend Performance Baseline

**Collected**: 2025-12-23
**Build Date**: 2024-11-28
**Version**: 0.11.4

---

## Bundle Analysis

### JavaScript Bundles

| File | Size | Notes |
|------|------|-------|
| `index-CQxcxGzb.js` | **992.6 KB** | Main application bundle |
| `browser-ponyfill-CUWOGkon.js` | 10.1 KB | Cross-browser polyfills |
| **Total JS** | **1,002.7 KB** | 🟡 Could be optimized |

### CSS Bundles

| File | Size |
|------|------|
| `index-BELcyKUM.css` | 50.4 KB |

### Total Distribution

| Metric | Value |
|--------|-------|
| **Total /dist size** | 4.6 MB |
| **Includes** | JS, CSS, locales, favicon |

---

## Dependencies Analysis

### Large Dependencies (from package.json)

| Package | Purpose | Potential Impact |
|---------|---------|------------------|
| `react-markdown` | Markdown rendering | Tree-shakeable |
| `react-syntax-highlighter` | Code highlighting | Large bundle |
| `lightweight-charts` | TradingView charts | ~100KB |
| `lucide-react` | Icons | Tree-shakeable |
| `@tanstack/react-query` | Data fetching | Essential |
| `i18next` suite | Internationalization | ~50KB total |

### Optimization Opportunities

1. **react-syntax-highlighter**: Consider `prism-react-renderer` (smaller)
2. **Dynamic imports**: Lazy load markdown/chart components

---

## Core Web Vitals

### Targets

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| **LCP** | <2.5s | 2.5-4s | >4s |
| **FID** | <100ms | 100-300ms | >300ms |
| **CLS** | <0.1 | 0.1-0.25 | >0.25 |

### Measurement Required

```bash
# Run Lighthouse (requires Chrome)
npx lighthouse https://klinecubic.cn --view

# Local development
npx lighthouse http://localhost:3000 --view
```

---

## Build Configuration

### Vite Config (`vite.config.ts`)

- **Build tool**: Vite 5
- **TypeScript**: 5.2.2
- **React plugin**: @vitejs/plugin-react

### Current Issues

- TypeScript errors in test files blocking `tsc`
- Test globals not configured in tsconfig

---

## Optimization Recommendations

### High Priority

1. **Code Splitting**
   ```typescript
   // Lazy load routes
   const PortfolioDashboard = lazy(() => import('./pages/PortfolioDashboard'));
   const FeedbackPage = lazy(() => import('./pages/FeedbackPage'));
   ```

2. **Lazy Load Heavy Components**
   ```typescript
   // Chart components
   const ChartPanel = lazy(() => import('./components/chat/ChartPanel'));
   ```

### Medium Priority

3. **Bundle Analyzer**
   ```bash
   # Add to package.json scripts
   "build:analyze": "vite build && npx vite-bundle-analyzer"
   ```

4. **Replace react-syntax-highlighter**
   - Current: Large bundle
   - Alternative: `prism-react-renderer` (~3KB)

### Low Priority

5. **Image Optimization**
   - Add WebP support
   - Implement lazy loading

---

## Data Collection Commands

```bash
# Check bundle sizes
docker compose exec frontend find /app/dist/assets -name "*.js" -exec ls -lh {} \;

# Total dist size
docker compose exec frontend du -sh /app/dist

# Run build with report
docker compose exec frontend npm run build -- --report
```
