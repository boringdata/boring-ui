# Changelog

## Unreleased

- Go backend GA cutover: `boring.app.toml` now defaults to `backend.type = "go"` for boring-ui and both config loaders fall back to Go when the backend type is omitted. Python remains available via explicit `backend.type = "python"`.
