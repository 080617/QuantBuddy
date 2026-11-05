# GitHub Publication Checklist

## Completed repository preparation

- Core application code is separated into `frontend/` and `backend/`.
- Data/Qlib utilities are grouped under `scripts/` and `configs/`.
- Historical UI sources are contained in `docs/prototypes/`.
- Engineering reports are contained in `docs/reports/`.
- Current Community verification captures are contained in `docs/screenshots/community/`.
- The root `QuantBuddy_Community_Final.html` is the canonical bilingual standalone prototype; the superseded single-language copy was removed.
- Local datasets, environments, caches, logs, and generated outputs are excluded by `.gitignore`.
- A filename/content pattern scan found no private keys, common API-token formats, or hard-coded password assignments in the publishable tree.

## Required before public release

1. Select an open-source license and add a root `LICENSE` file.
2. Review the existing uncommitted frontend/backend feature work and create intentional commits.
3. Confirm that third-party images, market data, and reports are suitable for redistribution.
4. Review the final staged/unstaged diff, then create the GitHub remote and push only after approval.

## Latest local verification

- Frontend Vitest: 3 files and 20 tests passed.
- Frontend production build: passed; all 24 Next.js routes completed static/dynamic build analysis.
- Backend: all 143 tests passed in the isolated `.venv-futu` environment.
- Repository safety checks: no accidentally tracked local environment/build directories, private-key/token pattern hits, publishable files over 50 MB, broken primary README links, or `git diff --check` errors.
- Standalone Community HTML: bilingual language-layer syntax and canonical-file checks passed. Historical interaction and responsive-layout captures remain under `docs/screenshots/community/`.

