# Build the project
[group('dev')]
build:
  uv python install
  uv sync
