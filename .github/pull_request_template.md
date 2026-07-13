## Summary

<!-- Describe what changed and why. -->

## Target Branch

- Normal development targets `dev`.
- Only a release promotion PR from `dev` may target `prod`.

## Type of Change

- [ ] Bug fix
- [ ] Feature
- [ ] Documentation
- [ ] Tests
- [ ] Refactor
- [ ] CI/build

## Checklist

- [ ] I searched existing issues and pull requests.
- [ ] I added or updated tests where needed.
- [ ] I updated README, docs, or changelog where needed.
- [ ] I removed secrets, tokens, cookies, private prompts, and local files from the diff.
- [ ] I ran `just lint`.
- [ ] I ran `just test`.
- [ ] I ran `uv run --group docs mkdocs build --strict`.
- [ ] I ran `uv build`.
- [ ] This PR targets `dev`, or it is the release promotion from `dev` to `prod`.

## Notes

<!-- Add screenshots, logs, compatibility notes, or follow-up work if relevant. -->
