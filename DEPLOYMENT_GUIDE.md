# CardWatch Deployment Guide

This guide covers deploying the CardWatch application to production.

## Architecture Overview

| Component | Service | URL |
|-----------|---------|-----|
| Frontend | Vercel | https://cardwatch-wine.vercel.app |
| Backend | Railway | https://cardwatch-api-production.up.railway.app |
| Database | Supabase (PostgreSQL) | aws-0-us-west-2.pooler.supabase.com |

---

## Prerequisites

### Required Accounts
- [Railway](https://railway.app) - Backend hosting
- [Vercel](https://vercel.com) - Frontend hosting
- [Supabase](https://supabase.com) - PostgreSQL database

### Install CLIs (one-time)
```bash
# These are run via npx, no global install needed
npx @railway/cli --version
npx vercel --version
```

---

## Environment Variables

### Backend (Railway)

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://postgres.xxx:password@aws-0-us-west-2.pooler.supabase.com:5432/postgres` |
| `SECRET_KEY` | JWT signing key (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`) | `hrdV32VmtnFsRVYNJmRO-aFuo8MEjkuzNXP5O5kxig4` |
| `CORS_ORIGINS` | Allowed frontend URLs | `https://cardwatch-wine.vercel.app,https://*.vercel.app` |
| `DEBUG` | Debug mode | `false` |
| `ENABLE_SCHEDULER` | Auto-start scraper jobs | `true` or `false` |
| `ANTHROPIC_API_KEY` | For AI search features | `sk-ant-...` |

### Frontend (Vercel)

| Variable | Description | Value |
|----------|-------------|-------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | `https://cardwatch-api-production.up.railway.app` |
| `NEXT_PUBLIC_GRAPHQL_URL` | GraphQL endpoint | `https://cardwatch-api-production.up.railway.app/graphql` |

---

## Deploying Updates

### Backend (Railway)

```bash
# Navigate to backend directory
cd /Users/nickjuelich/Desktop/Code/BulkBidding/backend

# Deploy to Railway
npx @railway/cli up
```

Railway will automatically:
- Detect Python project
- Install dependencies from `requirements.txt`
- Run the app using `Procfile`

### Frontend (Vercel)

```bash
# Navigate to frontend directory
cd /Users/nickjuelich/Desktop/Code/BulkBidding/frontend-nextjs

# Deploy to production
npx vercel --prod
```

Or deploy with environment variables:
```bash
npx vercel --prod \
  -e NEXT_PUBLIC_API_URL=https://cardwatch-api-production.up.railway.app \
  -e NEXT_PUBLIC_GRAPHQL_URL=https://cardwatch-api-production.up.railway.app/graphql
```

---

## First-Time Setup (New Environment)

### 1. Database Setup (Supabase)

1. Create account at https://supabase.com
2. Create new project
3. Go to **Settings → Database → Connection string**
4. Select **Session Pooler** (IPv4 compatible)
5. Copy the connection string

### 2. Migrate Data (if needed)

```bash
cd /Users/nickjuelich/Desktop/Code/BulkBidding/backend
source venv/bin/activate
python migrate_to_postgres_sync.py "postgresql://postgres.xxx:password@aws-0-us-west-2.pooler.supabase.com:5432/postgres"
```

### 3. Backend Setup (Railway)

```bash
cd /Users/nickjuelich/Desktop/Code/BulkBidding/backend

# Login to Railway
npx @railway/cli login

# Create new project (in Railway dashboard, select "Empty Project")
# Then link your local directory
npx @railway/cli link

# Deploy
npx @railway/cli up
```

Then in Railway dashboard:
1. Go to your service → **Variables**
2. Add all environment variables (see table above)
3. Go to **Settings → Networking → Generate Domain**

### 4. Frontend Setup (Vercel)

```bash
cd /Users/nickjuelich/Desktop/Code/BulkBidding/frontend-nextjs

# Login to Vercel
npx vercel login

# Deploy (first time will prompt for project setup)
npx vercel --prod \
  -e NEXT_PUBLIC_API_URL=https://YOUR-BACKEND.up.railway.app \
  -e NEXT_PUBLIC_GRAPHQL_URL=https://YOUR-BACKEND.up.railway.app/graphql
```

### 5. Update CORS

After frontend is deployed, update Railway's `CORS_ORIGINS`:
```
https://your-frontend.vercel.app,https://*.vercel.app
```

---

## Useful Commands

### Railway

```bash
# Check deployment status
npx @railway/cli status

# View logs
npx @railway/cli logs

# Open dashboard
npx @railway/cli open

# Set environment variable
npx @railway/cli variables set KEY=value
```

### Vercel

```bash
# List deployments
npx vercel ls

# View logs
npx vercel logs

# Set environment variable
npx vercel env add VARIABLE_NAME

# Alias a deployment
npx vercel alias [deployment-url] [custom-alias]
```

---

## Troubleshooting

### Backend won't start
1. Check Railway logs: `npx @railway/cli logs`
2. Verify `DATABASE_URL` is correct
3. Ensure all dependencies are in `requirements.txt`

### Frontend can't connect to backend
1. Check `CORS_ORIGINS` includes your frontend URL
2. Verify `NEXT_PUBLIC_API_URL` is correct
3. Check browser console for CORS errors

### Database connection issues
1. Use **Session Pooler** URL (port 5432), not Direct Connection
2. Ensure `?sslmode=require` is NOT in the URL (handled by driver)
3. For SQLAlchemy, use `postgresql+asyncpg://` prefix

### Missing dependencies
If Railway shows import errors:
1. Add missing package to `requirements.txt`
2. Redeploy: `npx @railway/cli up`

---

## File Structure

```
BulkBidding/
├── backend/
│   ├── app/                 # FastAPI application
│   ├── requirements.txt     # Python dependencies
│   ├── Procfile            # Railway start command
│   ├── runtime.txt         # Python version
│   └── .railwayignore      # Files to exclude from deploy
│
├── frontend-nextjs/
│   ├── app/                # Next.js pages
│   ├── components/         # React components
│   ├── lib/               # Utilities, GraphQL queries
│   └── .vercel/           # Vercel config (auto-generated)
│
└── DEPLOYMENT_GUIDE.md    # This file
```

---

## Current Production URLs

- **Frontend**: https://cardwatch-wine.vercel.app
- **Backend API**: https://cardwatch-api-production.up.railway.app
- **API Docs**: https://cardwatch-api-production.up.railway.app/docs
- **GraphQL Playground**: https://cardwatch-api-production.up.railway.app/graphql
