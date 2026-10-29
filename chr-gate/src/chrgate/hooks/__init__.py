"""chrgate-hook: one shared hook script for Claude Code and Codex.

cli.py reads one host payload from stdin; a per-host adapter (adapters/)
turns it into a neutral engine.Event and renders the engine.Decision back in
the host's output format; engine.py holds all behaviour; transcript.py reads
assistant text from a Codex rollout. The hook never mints, holds or sees a
plaintext witness: only the MCP server issues witnesses.
"""
