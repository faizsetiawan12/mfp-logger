# Issue Tracker: GitHub

Issues and PRDs live as GitHub issues. Use `gh` for all operations.

## Repository

GitHub repository: `faizsetiawan12/mfp-logger`.

## Conventions

- Create: `gh issue create --title "..." --body "..."`
- Read: `gh issue view <number> --comments`
- List: `gh issue list --state open`
- Comment: `gh issue comment <number> --body "..."`
- Close: `gh issue close <number> --comment "..."`
- Infer the repository from `git remote -v`.
- Pull requests are not a triage/request surface.
- When a skill says "publish to the issue tracker," create a GitHub issue.
- When a skill says "fetch the relevant ticket," use `gh issue view <number> --comments`.
