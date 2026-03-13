# Repository Guidelines

## Project Structure & Module Organization
- `ResearchDescription.md` captures the research goals and scope for Polymarket automation. Start here to understand intent and terminology.
- `src/` is reserved for implementation code (currently empty).
- `docs/` is reserved for design notes, experiments, and results (currently empty).
- `user_info` is a local-only reference file (ignored by git); avoid committing sensitive data.

## Build, Test, and Development Commands
- No build system or runtime entrypoint is defined yet.
- When adding tooling, document the exact commands here (e.g., `python -m pytest`, `make lint`).
- Real-time sports price streaming: `python3 src/collect_stream_sports_prices.py --output data/realtime/sports_ticks.jsonl --snapshot-output data/realtime/sports_latest_snapshot.json --batch-size 350 --max-connections 10`

## Coding Style & Naming Conventions
- Prefer Python for data analysis and prototyping, as suggested in `ResearchDescription.md`.
- Indentation: 4 spaces, UTF-8, and line length ≈ 100 chars.
- Naming: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- If you introduce formatting or linting (e.g., `ruff`, `black`), add the command and config paths.

## Testing Guidelines
- No test framework is set up yet.
- If you add tests, place them under `tests/` and name files `test_*.py`.
- Add a minimal CI-friendly command (e.g., `python -m pytest`).

## Commit & Pull Request Guidelines
- Current history shows short, informal commit messages (e.g., "up", "refactory"). Prefer concise, descriptive messages going forward, in either English or Chinese.
- Use a single-line summary, imperative tone (e.g., "Add Polymarket API client").
- PRs should include: scope summary, key decisions, and any new commands or data sources.

## Security & Data Handling
- Do not commit API keys, user IDs, or private datasets. Keep them in ignored files like `user_info` or a new `.env`.
- If you add data pipelines, document data sources, retention, and redaction steps.

## Agent-Specific Instructions
- When you create a Python script, include a concrete example command to run it (e.g., `python scripts/collect_markets.py --dry-run`).
