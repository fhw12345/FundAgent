# Frontend Changelog

All notable changes to the Financial Agent Frontend will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2025-10-07

### Added
- feat: Add username/password login UI with registration flow (email → code → credentials)


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
