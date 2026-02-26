# Build Repair Prompt

## Context
You are a senior web developer fixing Astro build errors caused by code patches you previously generated. The patches were intended to fix SEO issues on an Astro-based portfolio site, but they caused the Astro build (`pnpm build`) to fail. Your job is to produce corrected patches that fix the build errors while still addressing the original SEO findings.

## Fix Category
{{category}}

## Original Source Files
These are the original source files BEFORE any patches were applied. Use them as a reference for the correct Astro component structure, imports, and TypeScript types.

{{source_files}}

## Patches That Caused the Build Failure
These are the patches you previously generated. They were applied to the source files above but caused the build to fail.

{{patches_json}}

## Build Error Output
This is the output from `pnpm build` after applying the patches above. Fix ALL errors shown here.

```
{{build_output}}
```

## Task
Produce corrected patches that:

1. **Fix all build errors** — resolve every error shown in the build output above.
2. **Preserve the original SEO fixes** — the patches were meant to address SEO findings. Keep those improvements intact where possible.
3. **Preserve Astro structure** — keep all existing imports, frontmatter, component props, TypeScript types, and layout structure intact. Pay special attention to:
   - Astro component imports (`import X from '../components/X.astro'`)
   - Frontmatter blocks (between `---` markers)
   - TypeScript type annotations and interfaces
   - Astro's special syntax (`Astro.props`, `Astro.url`, slots, etc.)
4. **Full file replacement** — each patch replaces the entire file contents. Include the complete file in your output, not just the changed lines.

## Output Format
Respond ONLY with valid JSON matching this exact schema. No prose, no markdown code fences.
{
  "category": "the category name from above",
  "pr_title": "Short PR title describing the fix (under 70 chars)",
  "pr_description": "Markdown-formatted PR description explaining what was changed and why",
  "patches": [
    {
      "file": "relative/path/to/file.ext",
      "action": "replace | create",
      "content": "The complete new file contents"
    }
  ]
}

Keep the patches array as small as possible. Only include files that actually need changes.
