Excellent. This is a robust and modern approach to software development. Here’s a detailed guide for the coding and implementation style you've described.

---

### ## Coding Style & Standards

The goal is to use modern, stable language features and enforce consistency with best-in-class tooling.

#### **Python (Backend)**

* **Version**: Standardize on **Python 3.12**. It's the latest stable release with significant performance and syntax improvements.
* **Key Syntax & Features to Use**:
    * **Modern Type Hinting**: Use the `|` union operator (e.g., `str | int` instead of `Union[str, int]`) and built-in generic types (e.g., `list[str]` instead of `List[str]`).
    * **Structural Pattern Matching**: Use `match...case` for complex conditional logic where it improves readability over long `if/elif/else` chains.
    * **f-strings**: Exclusively use f-strings for string formatting.
    * **Data Classes**: Use `@dataclass` for simple data-holding objects instead of manual `__init__` methods. For API models, FastAPI's Pydantic models are preferred.
* **Tooling (configured in `pyproject.toml`)**:
    * **Formatter**: **Black**. It's non-negotiable and auto-formats code to a consistent style, ending all debates.
    * **Linter**: **Ruff**. This is the modern standard. It's incredibly fast and replaces a dozen older tools like Flake8, isort, and pyupgrade. It will check for errors, enforce best practices, and automatically sort imports.
    * **Type Checker**: **Mypy**. Run this in your CI pipeline to enforce static type safety, catching bugs before runtime.

#### **TypeScript (Frontend)**

* **Version**: Use the **latest stable TypeScript 5.x version**. Avoid release candidates or beta versions for stability.
* **Key Syntax & Features to Use**:
    * **ES Modules**: Use `import`/`export` syntax exclusively.
    * **Modern Features**: Leverage optional chaining (`?.`), nullish coalescing (`??`), and other modern ECMAScript features.
    * **`satisfies` Operator**: Use the `satisfies` keyword to validate that a type matches a contract without changing its inferred type, which is great for configuration objects.
* **Tooling**:
    * **Formatter**: **Prettier**. The industry standard for formatting TypeScript, HTML, and CSS. Like Black, it's opinionated and enforces a single style.
    * **Linter**: **ESLint**. Use it with the official TypeScript plugin (`@typescript-eslint/eslint-plugin`) to catch code-quality issues and potential bugs specific to TypeScript.
    * **Project Setup**: Initialize the project using a modern build tool like **Vite**, which will pre-configure most of this tooling for you.

---

### ## Implementation Methodology: "Infra-First Walking Skeleton"

This approach focuses on building a fully connected, end-to-end "slice" of the application first. This de-risks the project by proving that all the core infrastructure components can communicate before you invest time in complex features.

#### **Local-First Development with Docker Compose**

The entire application stack should be defined in a `docker-compose.yml` file. This is critical for local verification.

* **Services Defined**:
    * `backend`: The FastAPI application.
    * `frontend`: The Vite/React development server.
    * `db`: A standard **MongoDB** container (as a local stand-in for ApsaraDB for MongoDB).
    * `cache`: A standard **Redis** container (as a local stand-in for ApsaraDB for Redis).
* **Benefit**: Anyone can clone the repository and run `docker-compose up` to have the entire development environment running in minutes.

#### **Milestone-Based Progression**

We will build the application in clear, verifiable stages.

**Milestone 1: The Bare Bones Skeleton (End-to-End Connectivity)**
The only goal is to prove that every piece of the infrastructure is connected.
1.  **Backend**: Create a single API endpoint: `GET /api/health`. This endpoint should connect to the database and cache to confirm connectivity, then return a success message like `{"status": "ok", "db_connected": true, "cache_connected": true}`.
2.  **Database/Cache**: Set up the `db` and `cache` services in Docker Compose.
3.  **Frontend**: Create a default Vite/React app. Modify the main page to make an API call to the backend's `/api/health` endpoint and display the status on the screen.
4.  **CI/CD**: Create a basic CI pipeline (e.g., GitHub Actions) that builds the backend Docker image, runs the tests (even if there's only one), and confirms the build doesn't fail.

✅ **Verification**: You can run `docker-compose up`, open your browser to the frontend, and see the "ok" status from the backend. This proves the entire request lifecycle works.

**Milestone 2: Authentication & Core Logic**
1.  **Backend**: Add the OAuth2 JWT validation middleware. Create a new, protected endpoint like `GET /api/me` that returns user info from the token.
2.  **Frontend**: Implement the OIDC login flow. After login, the app should be able to successfully call the protected `/api/me` endpoint.
3.  **Core Logic**: Implement the basic Fibonacci analysis function. Create a *temporary* endpoint that takes a symbol, runs the analysis, and returns the raw JSON data (no chart, no AI, no OSS).

✅ **Verification**: A user can log in on the frontend and retrieve analysis data from a protected backend endpoint.

**Milestone 3 and Beyond: Layering Features**
Now, you can add features one at a time, knowing the core infrastructure is solid.
* Implement chart generation and saving to **Alibaba Cloud OSS**.
* Integrate the **Qwen-VL model** API call to get AI summaries.
* Build out the final frontend components to display the chart and summary.
* Harden the CI/CD pipeline with deployment steps to ACK.

---

### ## Documentation & Organization

This ensures the project is maintainable and understandable for the long term.

* **API Documentation**: **Leverage FastAPI's auto-generation**. The OpenAPI (`/docs`) endpoint is your primary, always-up-to-date API reference. Configure your CI pipeline to automatically export this as a `openapi.json` file into the `/docs` directory on every build.
* **Architectural Decisions**: Use **Architecture Decision Records (ADRs)**. These are short markdown files in a `/docs/adr` folder. Each file documents a single important decision (e.g., `001-use-mongodb-for-analysis-storage.md`). It describes the context, the decision, and the consequences. This is perfect for referencing *why* choices were made.
* **Code Comments**: Write comments that explain the **"why," not the "what."** Assume the reader understands the syntax but needs to know the business logic or the reason for a complex implementation.
* **READMEs**: Maintain a `README.md` in each primary directory (`/backend`, `/frontend`) with specific instructions for setting up, running tests, and developing for that part of the application. The root `README.md` will provide a high-level overview and a link to the other docs.

---

## Financial Agent Platform Development

### Infrastructure-First Methodology
* **Walking Skeleton Approach**: Always implement complete end-to-end infrastructure before adding features. Prove connectivity (Frontend → API → Database → Cache) in Milestone 1 before proceeding to business logic.
* **Verification Requirements**: Create comprehensive testing guides (VERIFICATION_GUIDE.md) and ensure all services show healthy status before milestone completion.
* **Quality Gates**: Implement `make fmt && make test && make lint` commands as standard development workflow.

### Technology Stack Decisions
* **Backend**: Python 3.12 + FastAPI + Motor (async MongoDB) + Redis with modern syntax (| unions, match/case patterns)
* **Frontend**: React 18 + TypeScript 5 + Vite + TailwindCSS with strict type checking
* **Database Strategy**: 云数据库 MongoDB 版 for primary data + Alibaba Cloud Tablestore for chat messages + OSS for file storage
* **Development Environment**: Docker Compose with multi-stage builds, health checks, and volume mounting for hot reload

### Development Workflow Standards
* **Git Workflow**: Use semantic commits with comprehensive feature descriptions, milestone tagging (v1.0.0-milestone1), proper .gitignore before first commit
* **Documentation Strategy**: Keep architectural docs local (CLAUDE.md, specs, workflows), push only essential setup docs (README, verification guides) to public repos
* **Docker Strategy**: Multi-stage builds for production optimization, development vs production targets, health check integration

### Quality and Tooling Standards
* **Python**: Black formatting + Ruff linting + MyPy type checking with pyproject.toml configuration
* **TypeScript**: ESLint + Prettier with strict settings, satisfies operator usage, modern ES features
* **Testing**: Comprehensive test coverage with pytest (backend) + vitest (frontend), mock external dependencies
* **Deployment**: Kubernetes manifests for Alibaba Cloud ACK, GitHub Actions for CI/CD pipeline

### API Design & Validation Patterns
* **Search Endpoint Validation**: Always validate that suggested symbols have actual price data before returning them to users. Use `ticker.history(period="5d")` test in fallback validation to ensure symbols are tradeable, not just recognized by yfinance.
* **Root Cause Analysis Approach**: Fix validation issues at the source (search/autocomplete) rather than adding error handling downstream (price endpoints). Invalid symbols should never reach user selection.
* **yfinance API Patterns**:
  - Search API: `yf.Search(query).quotes` returns valid results
  - Some symbols (like APPL) exist as financial instruments but lack price history data
  - Always test data availability: `ticker.history().empty` before suggesting symbols
* **"Fix the source, not symptoms"**: When invalid data appears in UI, investigate why it's being suggested rather than adding validation downstream. Implement scalable validation that works for all edge cases rather than hardcoding fixes for specific symbols.