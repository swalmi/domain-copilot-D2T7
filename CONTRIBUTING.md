# Contributing Guidelines

Thank you for contributing to this project. Please follow the guidelines below when submitting your contributions.

## Branch Naming
All feature and fix branches must follow the standard naming convention:
- `feature/<short-description>`: For new features or enhancements.
- `fix/<short-description>`: For bug fixes and resolution of issues.
- `chore/<short-description>`: For maintenance, configuration, or dependency updates.
- `docs/<short-description>`: For documentation updates.

## Commit Message Format
We enforce the [Conventional Commits](https://www.conventionalcommits.org/) specification for all commit messages:

```text
type(scope): summary
```

Examples:
- `feat(auth): implement JWT authentication handler`
- `fix(api): resolve payload validation error on login`
- `docs(readme): update setup instructions`

## Pull Request Requirements
- **No direct pushes to `main`**: All code contributions must be submitted via Pull Requests.
- Direct commits to the `main` branch are strictly prohibited.

## Running Tests Locally

### Backend (Python / FastAPI)
Run the test suite using `pytest`:
```bash
pytest
```

### Frontend (React)
Run the frontend test suite using `npm`:
```bash
npm test
```
