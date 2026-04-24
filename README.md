# FundAgent - 智能基金分析助手

AI-powered personal assistant for Chinese onshore mutual funds (场外基金) with multi-vendor LLM debate architecture.

## Features

- **Multi-Vendor LLM Debate**: Cross-vendor AI debate (Claude + GPT + Gemini) for higher quality analysis
- **Fund Analysis**: NAV trends, holdings analysis, sector exposure via AkShare
- **Screenshot Import**: Upload Alipay/天天基金 screenshots to import portfolio holdings (GPT-5.4 vision)
- **Daily Analysis**: Manual-trigger analysis with explicit 买入/持有/卖出 recommendations
- **Quarterly Reports**: PDF interpretation of fund quarterly reports (Gemini long context)
- **Conversational AI**: Natural language queries about your funds via streaming chat

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12 + FastAPI, MongoDB, Redis, LangChain + LangGraph |
| **Frontend** | React 18 + TypeScript 5, Vite, TailwindCSS |
| **LLM** | Agent Maestro proxy → GPT-5.4 / Claude Opus 4.7 / Gemini 3.1 Pro |
| **Data** | AkShare + 天天基金 crawler |
| **Deployment** | Docker Compose |

## Quick Start

```bash
# Prerequisites: Agent Maestro running in VS Code on localhost:23333

# Start all services
make dev

# Services:
# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000
# MongoDB:   localhost:27017
# Redis:     localhost:6379
```

## Architecture

See [Design Spec](docs/specs/2026-04-24-fundagent-design.md) for complete architecture.

### LLM Routing (Cross-Vendor Debate)

| Role | Default Model | Vendor |
|------|--------------|--------|
| Main Analyst | claude-opus-4.7 | Anthropic |
| Fundamentals | gpt-5.4 | OpenAI |
| News | gemini-3.1-pro-preview | Google |
| Debater | gemini-3.1-pro-preview | Google |
| Vision | gpt-5.4 | OpenAI |
| PDF Reader | gemini-3.1-pro-preview | Google |

## Development

```bash
cd backend && make test && make lint
docker compose exec frontend npm run lint
```

## Project Structure

```
fund-agent/
├── backend/               # FastAPI backend
│   ├── src/
│   │   ├── api/           # REST endpoints
│   │   ├── agent/         # LangGraph AI agent
│   │   ├── services/      # Business logic + data sources
│   │   └── database/      # MongoDB/Redis
│   └── tests/
├── frontend/              # React frontend
│   └── src/
│       ├── components/    # React components
│       └── services/      # API clients
├── docs/                  # Documentation
└── docker-compose.yml     # Local development
```
