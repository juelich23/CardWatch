#!/usr/bin/env python3
"""
Pre-deployment checklist for CardWatch backend.
Run this before deploying to production.
"""
import os
import sys

def check(name: str, condition: bool, fix: str = ""):
    status = "✓" if condition else "✗"
    print(f"  {status} {name}")
    if not condition and fix:
        print(f"    → Fix: {fix}")
    return condition

def main():
    print("=" * 50)
    print("CardWatch Production Readiness Check")
    print("=" * 50)

    all_good = True

    # Environment checks
    print("\n📋 Environment Variables:")

    all_good &= check(
        "DATABASE_URL set",
        bool(os.getenv("DATABASE_URL")),
        "Set DATABASE_URL to your PostgreSQL connection string"
    )

    all_good &= check(
        "DATABASE_URL is PostgreSQL (not SQLite)",
        "postgresql" in os.getenv("DATABASE_URL", ""),
        "Change DATABASE_URL from sqlite to postgresql+asyncpg://..."
    )

    all_good &= check(
        "SECRET_KEY is not default",
        os.getenv("SECRET_KEY", "change-this") != "change-this-in-production",
        "Generate a secure key: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

    all_good &= check(
        "CORS_ORIGINS configured",
        os.getenv("CORS_ORIGINS", "*") != "*",
        "Set CORS_ORIGINS to your frontend URL(s)"
    )

    all_good &= check(
        "ANTHROPIC_API_KEY set (for AI features)",
        bool(os.getenv("ANTHROPIC_API_KEY")),
        "Set ANTHROPIC_API_KEY for AI search and translations"
    )

    # File checks
    print("\n📁 Required Files:")

    all_good &= check(
        "requirements.txt exists",
        os.path.exists("requirements.txt"),
        "Create requirements.txt with pip freeze"
    )

    all_good &= check(
        "Procfile exists",
        os.path.exists("Procfile"),
        "Create Procfile with: web: uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    )

    # Import checks
    print("\n📦 Dependencies:")

    try:
        import asyncpg
        all_good &= check("asyncpg installed (PostgreSQL driver)", True)
    except ImportError:
        all_good &= check(
            "asyncpg installed (PostgreSQL driver)",
            False,
            "pip install asyncpg"
        )

    try:
        import apscheduler
        all_good &= check("apscheduler installed", True)
    except ImportError:
        all_good &= check(
            "apscheduler installed",
            False,
            "pip install apscheduler"
        )

    # Summary
    print("\n" + "=" * 50)
    if all_good:
        print("✅ All checks passed! Ready for deployment.")
    else:
        print("❌ Some checks failed. Fix the issues above.")
    print("=" * 50)

    return 0 if all_good else 1

if __name__ == "__main__":
    sys.exit(main())
