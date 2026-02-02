.PHONY = build
build:
	uv python install
	uv sync
