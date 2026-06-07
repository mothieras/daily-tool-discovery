# Troubleshooting

Most failures are the GitHub token. Run this before anything else:

```
grep GITHUB_TOKEN ~/.hermes/.env                                       # configured for the cron wrapper?
python3 -c "import os; print(len(os.environ.get('GITHUB_TOKEN','')))"  # set in THIS env? (0 = not set)
```

- All curated sources empty / `metadata_error_status: 403` → `GITHUB_TOKEN` is not set in the env where `run.py` runs. Export it, or add `GITHUB_TOKEN=...` to `~/.hermes/.env`.
- `401`, or candidate quality suddenly collapses → the token expired or is invalid. Replace it.
