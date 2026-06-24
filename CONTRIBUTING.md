# Contributing to Agent Mill

We welcome contributions! Here's how to get started.

## Reporting Issues

- Search [existing issues](https://github.com/Sugers955/agent-mill/issues) first
- Use the issue template (bug report / feature request)
- Include: steps to reproduce, expected vs actual behavior, environment info

## Submitting Pull Requests

1. Fork the repository
2. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/your-feature
   ```
3. Make your changes
4. Ensure code quality:
   ```bash
   cd frontend && npm run typecheck && npm run build
   cd backend && python -m py_compile app/main.py
   ```
5. Commit with clear message:
   ```bash
   git commit -m "feat: add xxx"
   ```
6. Push and open a PR:
   ```bash
   git push origin feat/your-feature
   ```

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat:     New feature
fix:      Bug fix
docs:     Documentation
refactor: Code refactoring
style:    Formatting only
perf:     Performance improvement
test:     Adding tests
chore:    Build/config changes
```

## Code Standards

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0 async
- **Frontend**: Vue 3 Composition API (`<script setup>`), TypeScript
- **CSS**: Use CSS variables (`var(--m-*)`), never hardcode colors
- **Comments**: Chinese for business logic, English for technical code

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
