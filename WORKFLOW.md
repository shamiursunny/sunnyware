# Sunnyware — Deploy & Push Workflow

**This is the canonical workflow for every Part (1-25). Locked permanently.**

## Dual-Remote Setup

| Remote | Purpose | URL |
|--------|---------|-----|
| `hf`   | Hugging Face Space (live deployment, auto-rebuild on push) | https://huggingface.co/spaces/shamiur/sunnyware |
| `origin` | GitHub (backup, history, future CI/CD) | https://github.com/shamiursunny/sunnyware |

## The Rule

**After every successful Part — and ONLY when the smoke test passes — push to BOTH remotes.**

Both remotes must end up at the **same commit hash**.

## Canonical Commands

```bash
cd /h/sunnyware

# Verify smoke test passes FIRST (never push broken code)
bash scripts/smoke_test.sh "https://shamiur-sunnyware.hf.space"

# Push to both remotes
git push hf main --force       # HF Space (auto-rebuild)
git push origin main           # GitHub (backup)

### File 2: `README.md` update (link to workflow)

```bash
cd /h/sunnyware

# Add a deployment section to README
cat >> README.md << 'EOF'

## Deployment Workflow

**Every successful Part is pushed to BOTH remotes — Hugging Face + GitHub.**

See [WORKFLOW.md](./WORKFLOW.md) for the locked dual-remote workflow.

- **HF Space:** https://huggingface.co/spaces/shamiur/sunnyware
- **GitHub:** https://github.com/shamiursunny/sunnyware

## Part Progress Log

| Part | Commit  | HF              | GitHub    | Status |
|------|---------|-----------------|-----------|--------|
| 1    | 76fcdde | Live            | Backed up | Done   |
| 2    | a190c3c | Live            | Backed up | Done   |
| 3    | d3b9dc3 | Live (LLM local)| Backed up | Done   |
| 4    | f0fd68e | Live            | Backed up | Done   |
