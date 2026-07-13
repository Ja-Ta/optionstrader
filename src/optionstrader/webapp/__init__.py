"""Optional local web UI (docs/08) — a second consumer of the core library.

Imports core modules only; nothing in the core imports this package, and this
file must stay free of fastapi/jinja2 imports so `import optionstrader` works
without the [ui] extra installed. Entry point: the `optionstrader-ui` script
(`optionstrader.webapp.__main__:main`).
"""
