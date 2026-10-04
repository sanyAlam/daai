# Dashboard (Phase 5 Minimal)

Next.js dashboard for local MVP visibility into governed action lifecycle.

## Required env (`apps/dashboard/.env.local`)

```bash
cp .env.local.example .env.local
```

```bash
DAAI_API_BASE_URL=http://127.0.0.1:8000
DAAI_SUPABASE_URL=https://your-project-ref.supabase.co
DAAI_SUPABASE_ANON_KEY=sb_publishable_your_project_publishable_key
DAAI_DASHBOARD_BASE_URL=http://127.0.0.1:3000
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

Use values from Supabase Dashboard:
- Project URL: `Project Settings` -> `Data API` -> `Project URL`
- Publishable key: `Project Settings` -> `Data API` -> `Publishable key`

Password reset emails redirect to `${NEXT_PUBLIC_SITE_URL}/reset-password`.
Add that exact route to Supabase Authentication redirect URLs for local and
deployed environments, for example `http://localhost:3000/reset-password`,
`http://localhost:3000/reset-password`, and `https://daaihq.com/reset-password`
when those hosts are active.

## Run locally

```bash
cd apps/dashboard
npm install
npm run dev
```

Required pages:

- `/` (redirects to `/home`, auth-protected)
- `/login`
- `/signup`
- `/forgot-password`
- `/reset-password`
- `/home`
- `/dashboard` (compatibility redirect to `/home`)
- `/dashboard/settings/security`
- `/workspaces/[workspaceId]`
- `/workspaces/[workspaceId]/setup`
- `/workspaces/[workspaceId]/actions`
- `/workspaces/[workspaceId]/actions/new`
- `/workspaces/[workspaceId]/runs`
- `/workspaces/[workspaceId]/runs/[actionRunId]`

## Vercel Monorepo Notes

- Preferred setup: set Vercel Project Root Directory to `apps/dashboard`.
- This app includes `apps/dashboard/vercel.json` with `framework: nextjs` for explicit framework detection.
- Repo root also includes `vercel.json` with monorepo-safe build/install commands targeting `apps/dashboard`, which helps when root directory is accidentally left at repository root.
