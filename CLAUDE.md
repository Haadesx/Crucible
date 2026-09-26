<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **HackMongo** (2578 symbols, 4848 relationships, 173 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact before editing.** Use `impact({target: "symbolName", direction: "upstream"})` or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .`; report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
- MUST warn on HIGH/CRITICAL `risk` pre-edit; never use `riskSharedAxes` to waive a HIGH/CRITICAL `risk` warning. Compare File/symbol: MCP File omits axes; Graph-RAG expands File.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- **MUST use `query({search_query: "concept"})` for concepts/flows, `context({name: "symbolName"})` for a named symbol, or `impact` for blast radius, on read-only callers, dependencies, imports, or execution flow.** Graph first; text search only for empty/`UNKNOWN`/literals.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/HackMongo/context` | Codebase overview, check index freshness |
| `gitnexus://repo/HackMongo/clusters` | All functional areas |
| `gitnexus://repo/HackMongo/processes` | All execution flows |
| `gitnexus://repo/HackMongo/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

<!-- october:canvas-guide:start -->
# Working in this app (built with October)

This project is built inside **October**, a spatial canvas where each app **screen/route shows up as its own node**. October discovers screens by scanning the route files on disk, so how you structure routes is exactly what the user sees on the canvas.

## One screen = one route file

Give every screen its own route and its own component file, and register each route in the app's router. Use flat, lowercase, hyphenated route paths (e.g. `/sign-up`).

## When the user asks for a flow or multiple screens

Onboarding, a wizard, "a few screens", steps, a set of screens — **create one separate route file per screen.** Never put multiple screens inside a single component: no internal step/pager/carousel state standing in for separate screens, and no extra screen components exported from one file. One screen = one file = one route, so each shows up as its own node on the canvas.

## Dependencies

When you import a new package, add it to `package.json` in the same change (for Expo / React Native, run `npx expo install <pkg>` so it picks a compatible version and writes `package.json` for you). Anything missing from `package.json` disappears on a clean install and crashes the app.

## Working with other agents

If you're connected to October's bus (the october-bus MCP tools), you can bring on helper agents. Use `add_terminal` or `add_chat` without a target to share the current workspace's files; `checkoutId` or `joinTaskOf` selects an existing working location. Use `createWorkspace:{requestId,name,isolated:true}` for independent work in a separate workspace. Keep requestId stable on retry. Creation returns the child workspace, canvas and node references. Use `list_children`, `message_child`, `get_child_status` and `stop_child` for your children across workspaces; they reply with `message_parent`. Same-workspace agents retain ordinary connections and `message_peer`.
<!-- october:canvas-guide:end -->
