# Click to Do Linux — Build & Packaging Automation
.PHONY: sync install daemon capture settings stop build clean

sync:
	uv sync

install: sync
	uv run click-to-do install

daemon:
	uv run click-to-do daemon

capture:
	uv run click-to-do capture

settings:
	uv run click-to-do settings

stop:
	uv run click-to-do stop

build:
	uv build

clean:
	rm -rf dist/ build/ *.egg-info
