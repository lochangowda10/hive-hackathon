# Publishing SwingLens to GitHub & using phase versions

This repository already contains the FULL version history: one commit and
one tag per development phase, from the Phase-1 skeleton to the latest fix.

## One-time publish (2 commands after creating the repo)

1. On github.com → **New repository** → name it `swinglens` →
   **do NOT add a README/.gitignore** (keep it completely empty) → Create.
2. In this folder:

```
git remote add origin https://github.com/hanamaraddi9620adi/swinglens.git
git push -u origin main --tags
```

Git will ask you to sign in (browser popup or a Personal Access Token as
the password — create one at github.com → Settings → Developer settings).

## Using any version (the feature you wanted)

```
git tag                      # list all phase versions
git checkout phase-2.5       # time-travel to the indicator-toolbox build
git checkout main            # come back to the latest
git diff phase-3 phase-3.5   # see exactly what a phase changed
```

On github.com the same versions appear under the branch dropdown → **Tags**,
and under **Releases** if you promote them.

| Tag | What it is |
|---|---|
| phase-1 | Skeleton: auth, live charts, Ollama |
| phase-2 | Analyst Engine drawn on the chart |
| phase-2.1 | Chat triggers the real pipeline |
| phase-2.5 | 27 indicators + 10 chart types |
| phase-2.75 | Markets Explore + ticker strip |
| phase-3 | Newsroom + Pulse dashboard |
| phase-3.5 | Grounded AI + watch levels |
| phase-3.75 | Market scanner + chat history |
| phase-4.5-showcase | Docker, demo mode, deploy guide |
| phase-4-mirror | Portfolio import + Trader Mirror |
| phase-4.75 | Watchlist, alerts, Track Record |
| phase-4.75.1 (= main) | Blank-page hardening fixes |
