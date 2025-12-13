# Backend Changelog

All notable changes to the Financial Agent Backend will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.7] - 2025-12-13

### Added
- feat: add get_stock_quote tool with market status API support


## [0.8.6] - 2025-12-10

### Added
- feat(compaction): Persist summary messages and delete old messages during context compaction
  - Added `is_summary` and `summarized_message_count` fields to `MessageMetadata`
  - Added `delete_old_messages_keep_recent()` method to `MessageRepository`
  - Compaction now persists summary to DB and cleans up old messages (keeps last N = `tail_messages_keep`)
  - Summary messages marked with `is_summary: true` are never deleted
- fix(portfolio): initialize OptimizedOrder priority to valid value to prevent ValidationError


## [0.8.5] - 2025-12-02

### Added
- feat(portfolio): Short position handling in order optimizer
  - Added `is_cover` field to `OptimizedOrder` model to identify cover orders
  - Automatic detection of short positions (negative quantity)
  - SELL decisions on short positions converted to BUY-to-cover orders
  - Cover orders execute with highest priority (risk reduction first)
  - Clear logging for short position conversions

### Changed
- refactor(portfolio): 3-phase architecture for portfolio analysis
  - Phase 1: Pure symbol research (concurrent, independent)
  - Phase 2: Single holistic decision call via `PortfolioDecisionList`
  - Phase 3: Programmatic order optimization (no additional LLM call)
  - Reduced LLM calls from N+1 to N+1 (research) + 1 (decision)
  - `SymbolAnalysisResult` no longer contains `decision` field
  - Added `PortfolioDecisionList` model for batch decisions
- refactor(config): Adjusted context window thresholds
  - `compact_threshold_ratio`: 0.5 → 0.75 (trigger at 75% instead of 50%)
  - `compact_target_ratio`: 0.1 → 0.25 (compress to 25% instead of 10%)

## [0.8.4] - 2025-11-29

### Added
- feat(portfolio): Failed order persistence with error tracking
  - Added `error_message` field to `PortfolioOrder` model for storing raw API error messages
  - Failed orders now saved to MongoDB with status="failed" and error details
  - Batch persistence using `create_many()` for failed orders
- feat(api): New `/api/portfolio/transactions` endpoint with filtering and pagination
  - Supports `limit`, `offset` pagination parameters
  - Supports `status` filter: "success" | "failed" | all
  - Returns `has_more` flag for UI "Show All" functionality
  - Query handles both plain status ("filled") and enum format ("OrderStatus.FILLED")

### Fixed
- fix(db): MongoDB sparse index for nullable `alpaca_order_id` field
  - Added `sparse=True` to allow multiple NULL values (failed orders have no Alpaca ID)
  - Fixes duplicate key error when persisting multiple failed orders

## [0.8.3] - 2025-11-28

### Added
- feat(portfolio): Structured output and order aggregation for portfolio analysis
  - Two-phase analysis with aggregation hook: Phase 1 (symbol analysis) → Phase 2 (order optimization) → Phase 3 (execution)
  - New Pydantic models: `TradingDecision`, `OptimizedOrder`, `OrderExecutionPlan`, `SymbolAnalysisResult`
  - `ainvoke_structured()` method in ReAct agent for reliable structured output extraction
  - Order optimizer module (`order_optimizer.py`) extracted from portfolio analysis agent
  - SELLs execute before BUYs to maximize buying power
  - Proportional scaling (Option A) when insufficient funds for all BUY orders
  - Eliminates unreliable regex parsing of LLM text responses

### Changed
- Refactored `portfolio_analysis_agent.py` to use structured output instead of regex parsing
- Extracted order aggregation/execution logic to separate `OrderOptimizer` class

## [0.8.2] - 2025-11-27

### Added
- feat(chat): auto-inject selected symbol from UI to agent context


## [0.8.1] - 2025-11-27

### Fixed
- **Watchlist Symbol Validation**: Enhanced validation with multi-layer fallback strategies
  - Primary: Exact symbol match in SYMBOL_SEARCH results
  - Fallback 1: High-confidence match (score >= 0.9)
  - Fallback 2: GLOBAL_QUOTE API direct validation
  - Added debug logging for troubleshooting validation failures
  - Fixes Bug #4: TSLA, AAPL, and other valid symbols now successfully validate

## [0.8.0] - 2025-11-26

### Added
- feat(portfolio): Unified portfolio-aware analysis prompt for holistic position management
  - Single prompt replacing 3 separate prompts (holdings, watchlist, market_movers)
  - Dynamic portfolio context injection (equity, buying_power, cash, all positions)
  - SWAP decision type for portfolio rebalancing recommendations
  - English-only prompt with language instruction placeholder
  - Position sizing suggestions based on total equity percentage

### Changed
- Enhanced portfolio analysis with full portfolio context awareness
- Improved decision recommendations considering liquidity and diversification
- Value opportunity detection for market panic situations

## [0.7.1] - 2025-11-19

### Added
- feat: add OSS presigned download URLs for feedback images
- feat: dual authentication mode for OSSService (static credentials + STS)
- Add 15-min delayed intraday data, GLOBAL_QUOTE endpoint, fix error messages

### Performance
- Batch chunk streaming: Reduce SSE events by 90% (CHUNK_SIZE=10 chars/event vs 1 char/event)
- Reduces typical 1300-char response from 1300 events to 130 events

### Reliability
- Add circuit breaker for tool event queue (MAX_QUEUE_SIZE=100) to prevent memory exhaustion
- Fix deadlock in background streaming loop - check agent completion in timeout handler
- Fix generator early exit bug preventing final answer streaming

### Bug Fixes
- Fix feedback images not displaying in private bucket (presigned download URLs)
- Fix tool progress message injection causing assistant message displacement
- Add agent completion check in asyncio.TimeoutError handler
- Ensure streaming completes gracefully when agent finishes

## [0.7.0] - 2025-11-15

### Added
- feat(agent): add real-time tool execution streaming with SSE callbacks and strategic prompt engineering


## [0.6.2] - 2025-11-14

### Added
- perf: add 30-minute Redis caching to market movers endpoint to reduce API calls


## [0.6.1] - 2025-11-14

### Added
- fix(data): Complete AlphaVantage integration across all TickerDataService instantiations


## [0.6.1] - 2025-11-14

### Added
- fix(k8s): add namespace env var and RBAC permissions for metrics API


## [0.5.20] - 2025-11-12

### Added
- Skip deprecated yfinance tests pending Alpha Vantage implementation


## [0.5.18] - 2025-11-12

### Added
- Replace yfinance with hybrid Alpaca + Polygon.io for market data to fix ACK rate limiting


## [0.5.15] - 2025-11-11

### Added
- Fix exact symbol search bug - direct ticker validation now runs when Search returns empty results


## [0.5.13] - 2025-11-06

### Added
- Fixed portfolio chart timeout (asyncio.to_thread), order persistence (PortfolioOrderRepository), agent recursion limit (25→50)


## [0.5.12] - 2025-10-31

### Added
- fix(oss): Use HTTPS for presigned URLs to fix mixed content error


## [0.5.11] - 2025-10-31

### Added
- feat(feedback): Add image upload with OSS integration


## [0.5.9] - 2025-10-26

### Added
- feat: Add consistent system prompt to v3 (Agent mode) for unified UX


## [0.5.8] - 2025-10-26

### Added
- fix: Credit system integration for v2 (Copilot) and v3 (Agent) modes with token extraction


## [0.5.5] - 2025-10-24

### Added
- fix(database): Change chat list query to use updated_at sorting for Cosmos DB compatibility


## [0.5.5] - 2025-10-23

### Added
- Add production Langfuse observability configuration


## [0.5.4] - 2025-10-14

### Added
- Fix MongoDB index name conflict causing backend startup failure


## [0.5.3] - 2025-10-13

### Added
- Complete type safety - Resolve 107 mypy errors with comprehensive type annotations


## [0.5.0] - 2025-10-10

### Added
- Add admin health dashboard with database statistics monitoring, implement admin role-based access control


## [0.4.10] - 2025-10-09

### Added
- Remove 500+ lines of deprecated session management code, simplify ChatAgent to direct LLM wrapper, eliminate SessionManager bridge pattern


## [0.4.9] - 2025-10-09

### Added
- Security: Implement atomic token rotation using MongoDB transactions to prevent race conditions during refresh token renewal. Falls back to best-effort on standalone MongoDB.


## [0.4.8] - 2025-10-08

### Added
- feat(agent): Context-adaptive LLM response style (structured for initial analysis, conversational for follow-ups)
- feat(agent): Instruction for LLM to match formatting style from conversation history
- feat(agent): Simplified system prompt with less over-instruction

### Changed
- Removed mandatory rigid structure ("The Verdict", "The Evidence") for all responses
- Split instructions into "Initial Analysis" vs "Follow-Up Questions" patterns

## [0.4.7] - 2025-10-08

### Added
- security: Implement dual-token JWT authentication (access + refresh tokens)


## [0.4.6] - 2025-10-08

### Added
- Add RefreshToken models and repository for JWT token refresh mechanism


## [0.4.5] - 2025-10-08

### Added
- security: Add comprehensive security contexts and fix K8s linting


## [0.4.3] - 2025-10-08

### Added
- Add DELETE /api/chat/chats/{chat_id} endpoint for chat deletion


## [0.4.1] - 2025-10-07

### Fixed
- **MongoDB Database Name Parsing** (Critical)
  - Fixed database name extraction to strip query parameters from Cosmos DB URLs
  - Bug: `mongodb://host/dbname?ssl=true` was parsed as `dbname?ssl=true` instead of `dbname`
  - Added validation to detect invalid characters in database names
  - Fixed in both `config.py` and `mongodb.py`
  - Hidden locally because local MongoDB doesn't use query parameters

### Added
- **Custom Exception Hierarchy**
  - Added `ConfigurationError` for configuration validation failures
  - Added `DatabaseError` for database connection/operation failures
  - Proper error categorization (400=user error, 500=database, 503=external service)

### Changed
- **Enhanced MongoDB Logging**
  - Log parsed vs raw database name when query parameters present
  - Log validation errors with detailed context (raw value, parsed value, invalid chars)
  - Added `error_type` field to all error logs for better debugging
  - Connection verification logged with `connection_verified=True`

## [0.4.0] - 2025-10-07

### Added
- **Authentication System**
  - Username/password registration with email verification
  - Email verification code system (6-digit codes, 5-min expiry)
  - Password-based login with JWT tokens
  - Forgot password flow with email verification
  - Bcrypt password hashing for security
  - Tencent Cloud SES integration for email delivery


### Planned
- LangChain agent integration
- Conversation history persistence
- AI chart interpretation with Qwen-VL
- User authentication system

---

## [0.1.0] - 2025-10-04

**Initial Release** - Walking Skeleton Complete

### Added
- **Core Infrastructure**
  - FastAPI application with health monitoring
  - MongoDB integration for data persistence
  - Redis caching for market data
  - Docker containerization
  - Kubernetes deployment configuration

- **Market Data Integration**
  - yfinance integration for stock data
  - Symbol search with validation
  - Price history retrieval (1d/1h/5m intervals)
  - Caching layer for market data (6-month expiry)

- **Financial Analysis Features**
  - Fibonacci retracement analysis with confidence scoring
  - Fundamental analysis (P/E, P/B, dividend yield, market cap)
  - Stochastic oscillator indicator (K%/D% calculations)
  - Support/resistance level detection
  - Price trend analysis

- **API Endpoints**
  - `GET /api/health` - Health check with database/cache status
  - `GET /api/market/search` - Symbol search with suggestions
  - `GET /api/market/price/{symbol}` - Historical price data
  - `POST /api/analysis/fibonacci` - Fibonacci analysis
  - `GET /api/analysis/fundamentals/{symbol}` - Fundamental analysis
  - `POST /api/analysis/stochastic` - Stochastic oscillator

- **Data Models**
  - Pydantic models for request/response validation
  - Type-safe API contracts
  - Comprehensive error handling

- **Testing**
  - Unit tests for analysis modules (100% coverage on stochastic)
  - Integration tests for API endpoints
  - Pytest configuration with coverage reporting

- **Code Quality**
  - Black formatting
  - Ruff linting
  - MyPy type checking
  - Pre-commit hooks

### Fixed
- **Dividend Yield Validation** (Critical Bug)
  - Smart detection for yfinance format inconsistencies
  - Handle both decimal (0.025) and percentage (0.71) formats
  - Cap at 25% to reject unrealistic data
  - Affected symbols: MSFT and others with inconsistent API responses

- **Symbol Validation**
  - Verify price data availability before suggesting symbols
  - Return only symbols with valid 5-day history
  - Prevent 422 errors from invalid symbol suggestions

### Changed
- **Error Handling**
  - Improved error messages for validation failures
  - Detailed 422 error responses with field-level errors
  - Graceful fallback for missing financial metrics

### Infrastructure
- **Deployment**
  - Azure Container Registry integration
  - Azure Kubernetes Service deployment
  - External Secrets Operator for secure configuration
  - Health probes (temporarily disabled for debugging)

- **Environment**
  - Development environment with hot reload
  - Staging environment on AKS dev namespace
  - CORS configuration for cross-origin requests

### Dependencies
- Python 3.12
- FastAPI 0.115.6
- Motor (async MongoDB) 3.6.0
- Redis 5.2.1
- yfinance 0.2.50
- Pandas 2.2.3
- NumPy 2.2.2
- Pydantic 2.10.6

### Breaking Changes
None - Initial release

### Migration Guide
No migration required - fresh installation.

### Known Issues
- Health check endpoint returns 400 (probes disabled temporarily)
- No authentication system (planned for v0.2.0)
- Manual deployment process (CI/CD planned for future)

### Security
- CORS configured for development (`["*"]`)
- TrustedHostMiddleware disabled in development
- Secrets managed via Azure Key Vault + External Secrets

---

## Version History

- **v0.1.0** (2025-10-04): Initial release - Walking skeleton complete
- **v0.2.0** (Planned): LangChain agent integration
- **v1.0.0** (Future): Production-ready release with authentication
