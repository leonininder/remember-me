# assets

Placeholder for demo media (GIF / MP4 / SVG) shown above the fold in the root README.

Until a real capture is recorded, use:

1. Terminal output from `remember-me demo`
2. The Mermaid diagram in the root README

Suggested filename when ready: `demo.gif` (linked from README hero).

## How to capture `demo.gif`

**Goal:** show install → demo → hydrate decision in under ~30 seconds of screen time.

### Option A — asciinema + agg (preferred, reproducible)

```bash
# from repo root, with editable install
pip install -e ".[dev]"
asciinema rec /tmp/remember-me-demo.cast -c 'remember-me demo'
# convert to GIF (https://github.com/asciinema/agg)
agg /tmp/remember-me-demo.cast assets/demo.gif
```

### Option B — macOS screenshot video

1. Open Terminal at repo root; run `pip install -e ".[dev]" && remember-me demo`.
2. Capture with Cmd+Shift+5 → Record Selected Portion (keep the window tight).
3. Convert MOV → GIF with ffmpeg, e.g.:

```bash
ffmpeg -i ~/Desktop/demo.mov -vf "fps=12,scale=960:-1:flags=lanczos" -loop 0 assets/demo.gif
```

### Option C — static PNG fallback

If GIF tooling is unavailable, drop `demo.png` (terminal screenshot) and update the README image path. Prefer GIF when possible.

### Checklist before linking from README

- [ ] No API keys, tokens, or real PII visible
- [ ] Offline FakeJev path only (do not imply live cloud)
- [ ] Filename `assets/demo.gif` (or update README link)
- [ ] File size ideally &lt; 5 MB for GitHub README load
