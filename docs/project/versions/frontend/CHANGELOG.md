# Frontend Changelog

All notable changes to the Financial Agent Frontend will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.11] - 2025-10-26

### Added
- feat: Agent mode toggle UI (v2 Copilot vs v3 Agent)


## [0.8.0] - 2025-10-10

### Added
- Add admin health dashboard page with database statistics, implement admin-only navigation


## [0.7.7] - 2025-10-08

### Added
- feat(ux): Assistant responses now fill full chat width (removed max-w-3xl and mr-8)
- feat(ux): Consistent, prominent display for analysis content (mimics Gemini layout)

## [0.7.6] - 2025-10-08

### Added
- feat(ux): NEUTRAL Stochastic signal uses yellow text (rgb(255, 215, 0)) on white background
- feat(ux): Completed dynamic color implementation for all signal types (OVERBOUGHT/OVERSOLD/NEUTRAL)

## [0.7.5] - 2025-10-08

### Added
- feat(ux): Stochastic signals now show color indicators (🔴 OVERBOUGHT, 🟢 OVERSOLD, 🟡 NEUTRAL)
- feat(ux): Stochastic signals display meaning in table (e.g., "OVERBOUGHT (Potential Sell Zone)")
- feat(ux): Recent signals show color emojis (🟢 BUY, 🔴 SELL) on independent lines
- feat(ux): Fibonacci analysis uses flexible lists instead of rigid tables
- feat(ux): Fibonacci levels are now collapsible (click to expand) - starts collapsed
- feat(ux): Key trends shown as numbered list (top 3 if available)

## [0.7.4] - 2025-10-08

### Fixed
- fix(ux): Tables now render properly with borders and styling (added table components to ReactMarkdown)
- fix(ux): Removed redundant Summary section from Stochastic analysis (duplicated table data)

## [0.7.3] - 2025-10-08

### Fixed
- fix(ux): Auto-scroll now scrolls to latest user message (like Gemini chat) instead of bottom

## [0.7.2] - 2025-10-08

### Added
- feat(ux): User messages for quick analysis button clicks (shows "Start X analysis for symbol...")
- feat(ux): Table-based analysis formatting for better readability
- feat(ux): Removed redundant explanatory text from analysis outputs

## [0.7.1] - 2025-10-08

### Added
- feat(ux): Auto-scroll to chat messages when new messages arrive
- feat(ux): BLUF-formatted analysis output (Bottom Line Up Front principle)

## [0.7.0] - 2025-10-08

### Added
- feat(auth): Frontend dual-token JWT authentication with auto-refresh


## [0.6.1] - 2025-10-08

### Added
- fix: Update nginx to listen on port 8080 for non-root compatibility


## [0.4.5] - 2025-10-08

### Added
- Add chat delete UI with optimistic updates and confirmation dialog


## [0.4.1] - 2025-10-07

### Fixed
- **API URL Fallback to Localhost** (Critical)
  - Fixed `VITE_API_URL` fallback logic treating empty string as falsy
  - Bug: `const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"`
  - Empty string is falsy in JavaScript, so fallback to localhost:8000 was triggered
  - Browser tried to connect to user's local machine instead of relative API URLs
  - Changed fallback to empty string for proper relative URL behavior
  - File: `frontend/src/services/authService.ts`

### Architecture
- **Clarified Pod Architecture**
  - Frontend and backend run in **separate pods** (not same pod)
  - Frontend pod serves static files via nginx
  - React JavaScript runs in **user's browser**, not in pod
  - Ingress routes: `/api/*` → backend pod, `/*` → frontend pod
  - Browser needs relative URLs to reach backend via ingress

## [0.4.0] - 2025-10-07

### Added
- **Authentication UI**
  - Login page with email/password fields
  - Registration flow: email → verification code → username/password
  - Forgot password flow with email verification
  - JWT token storage in localStorage
  - Auto-login after successful registration/password reset
  - Error handling and validation messages


### Planned
- Advanced charting with TradingView integration
- User authentication and session management
- Chat history persistence
- Mobile responsive design improvements

---

## [0.1.0] - 2025-10-04

**Initial Release** - Walking Skeleton Complete

### Added
- **Core UI Components**
  - Chat interface for conversational analysis
  - Message input with analysis parsing
  - Response display with formatted results
  - Loading states and error handling

- **Market Data Features**
  - Stock symbol search with autocomplete
  - Interval selection (1d/1h/5m)
  - Period selection (1mo/3mo/6mo/1y/2y)
  - Price chart visualization (placeholder)

- **Analysis Integration**
  - Fibonacci retracement analysis display
  - Fundamental analysis cards
  - Stochastic oscillator visualization
  - React Query for API state management

- **Infrastructure**
  - React 18 with TypeScript 5
  - Vite build system
  - TailwindCSS styling
  - Nginx production server
  - Docker multi-stage builds
  - Kubernetes deployment

- **API Client**
  - Axios-based API client with error handling
  - Environment-aware baseURL configuration
  - Request/response type definitions
  - Health check integration

### Fixed
- **Frontend BaseURL Hardcoded** (Critical Bug)
  - Smart baseURL detection for production vs development
  - Use relative URLs in production for nginx proxy
  - Prevents CORS errors in deployed environment

### Changed
- **Message Parsing**
  - Extract symbol from user messages
  - Parse interval and period preferences
  - Default to sensible values (1d, 3mo)

### Infrastructure
- **Deployment**
  - Azure Container Registry integration
  - Azure Kubernetes Service deployment
  - Nginx reverse proxy for API calls
  - Production-optimized builds

- **Development**
  - Hot module replacement (HMR)
  - ESLint and Prettier configuration
  - TypeScript strict mode

### Dependencies
- React 18.3.1
- TypeScript 5.7.3
- Vite 6.0.7
- TailwindCSS 3.4.17
- React Query (TanStack Query) 5.64.2
- Axios 1.7.9

### Breaking Changes
None - Initial release

### Known Issues
- No chart visualization (placeholder only)
- No conversation history persistence
- No user authentication
- Mobile UI needs optimization

---

## Version History

- **v0.1.0** (2025-10-04): Initial release - Walking skeleton complete
- **v0.2.0** (Planned): Advanced charting and UI improvements
- **v1.0.0** (Future): Production-ready with auth and full features
