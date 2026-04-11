# Factory

This directory contains the unattended linear-run scaffold for bounded
workflow jobs.

Primary entrypoint from a prepared sandbox:

```bash
make factory-run
```

Resume entrypoint from a prepared sandbox:

```bash
make factory-run-resume RUN_DIR=.factory-runs/<run-dir>
```

Global entrypoint from anywhere:

```bash
ccc factory-run /abs/path/to/repo-or-sandbox
```

Runner files:

- `factory/claude-linear.json`
- `factory/run_sequence.sh`
- `factory/run_single_job.sh`
- `factory-jobs/`
