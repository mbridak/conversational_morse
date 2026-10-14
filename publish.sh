#!/bin/bash
uv tool uninstall -qq conversational_morse
rm -rf ./build/*
rm -rf ./dist/*
uv build
uv run --with twine twine check dist/*
python3 -m twine upload dist/*
