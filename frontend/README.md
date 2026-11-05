# QuantBuddy Frontend

The formal product frontend is a Next.js 16 application using React 19, TypeScript, Recharts, and Vitest.

## Setup

```powershell
pnpm install
pnpm dev
```

Open `http://localhost:3000`.

To connect the read-only local backend, copy `.env.example` to `.env.local` and keep the default local API URL unless your backend uses another port. Never commit `.env.local`.

## Commands

```powershell
pnpm test
pnpm build
pnpm lint
pnpm start
```

## Main areas

- Dashboard and product shell: `src/app/` and `src/components/layout/`
- Strategy and factor workspace: related components and services under `src/`
- Backtesting: `src/components/backtest/`
- Community: `src/components/community/`
- Paper/simulated-account UI: `src/components/paper/`
- Client adapters and API access: `src/services/`

The standalone `QuantBuddy_Community_Final.html` in the repository root is a separate bilingual, browser-local demonstration and does not replace the formal Next.js application.
