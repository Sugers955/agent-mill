"""Widget design guidelines + in-process tool for generative UI."""

from typing import Any

WIDGET_SYSTEM_PROMPT = """<widget-capability>
You can create interactive visualizations using the `show-widget` code fence.

CRITICAL RULE: Always use show-widget fence — never write files, never output raw SVG.

```show-widget
{"title":"human-readable title","widget_code":"<svg width=\\"100%\\" viewBox=\\"0 0 W H\\">...</svg>"}
```

widget_code is a JSON string: escape every quote as \\", every newline as \\n. No DOCTYPE/html/head/body.

LAYOUT PLANNING — do these mentally BEFORE writing any SVG element:
1. Measure every label (CJK 1.8x, Latin 1x). Wrap at 13 CJK / 18 Latin chars per line.
2. node_w = max(120, min(260, longest_line_chars * 8 + 48)); node_h = 48 + (extra_lines * 20)
3. Grid layout: top-bottom flow uses x_center = 40 + col_i * (max_node_w + 60); y_top = 40 + row_j * (max_node_h + 50)
4. viewBox W = rightmost_right_edge + 40 (min 500); H = bottommost_bottom_edge + 48 (min 300)
5. Draw order: <defs> first → background rect → node rects → text → arrows last

VISUAL QUALITY — Google-Material light theme:
- Primary: fill #e8f0fe / stroke #aecbfa / accent #1a73e8
- Success: fill #e6f4ea / stroke #a8dab5 / accent #1e8e3e
- Warning: fill #fef7e0 / stroke #feefc3 / accent #f29900
- Neutral: fill #f8f9fa / stroke #dadce0 / accent #5f6368
- Error:   fill #fce8e6 / stroke #f6aea9 / accent #d93025
- Background: ALWAYS fill="#ffffff" or fill="#fafbfc" — never dark.

Typography: title 15px #202124, label 13px #3c4043, caption 11px #5f6368. NEVER below 11px. NEVER bold (700).

HTML vs SVG decision:
- Calculator/form/inputs/tabs → HTML (needs click + state)
- Flowchart/sequence/timeline/architecture/hierarchy → SVG (drawing connections)

FORBIDDEN:
- Text positioned without measuring node width first → overflow
- Arrows drawn through other nodes
- font-size below 11px
- Raw <svg> output without the show-widget fence
- Dark backgrounds, neon colors, gradients on node fills

Required rules (always apply):
1. widget_code is a JSON string — escape quotes/newlines; no DOCTYPE/html/head/body
2. Light theme: bg #ffffff/#fafbfc; never dark
3. Each widget ≤ 4000 chars. Always close JSON + fence on its own line
4. Streaming order: <defs> → rects → text → arrows
5. CDN allowlist: cdnjs.cloudflare.com, cdn.jsdelivr.net, unpkg.com, esm.sh
6. CDN scripts: onload="init()" + if(window.Lib) init(); fallback
7. Text explanations OUTSIDE the code fence
8. Multi-widget: each in a separate fence
9. SVG: <svg width="100%" viewBox="0 0 680 H">, ALWAYS first child <rect width="100%" height="100%" fill="#ffffff"/>
10. Title: human-readable in user's language

Call `load_widget_guidelines` for extended specs (interactive, chart, mockup, art, diagram).
</widget-capability>"""


CORE_DESIGN_SYSTEM = """## Core Design System

### Philosophy
- Premium light: warm white (#fafbfc) and pure white (#ffffff) surfaces; never dark.
- Google Material restraint: 1a73e8 indigo accent, 8/12/16 radius scale, soft shadows.
- Crisp hierarchy: title 15px / body 13px / caption 11px. Three sizes max.

### Streaming order
- SVG: <defs> first → visual elements immediately.
- HTML: <style> (short) → content → <script> last.

### Layout rhythm
- Outer container padding: 20px; card padding: 16px; section gap: 16px; item gap: 8-12px"""


UI_COMPONENTS = """## UI components (HTML widgets)

### Tokens
- Surface: #fafbfc outer, #ffffff cards
- Borders: 1px solid #e8eaed
- Radius: 8px inner, 12px outer
- Shadow: 0 1px 2px rgba(60,64,67,.08), 0 1px 3px 1px rgba(60,64,67,.04)
- Typography: 15px title #202124, 13px body #3c4043, 11px caption #5f6368

### Patterns
1. Stat card grid — 3-col metrics dashboard
2. Horizontal bar comparison — labels + percentages
3. Tag/chip row — pill-shaped semantic tags
4. List with icons — left dot + text + meta-right
5. Toggle button group — segmented control"""


COLOR_PALETTE = """## Color palette (Google-Material aligned)

| Ramp    | 50 (fill) | 200 (stroke) | 600 (text) |
|---------|-----------|--------------|------------|
| Indigo  | #e8f0fe   | #aecbfa      | #1a73e8    |
| Emerald | #e6f4ea   | #a8dab5      | #1e8e3e    |
| Amber   | #fef7e0   | #feefc3      | #f29900    |
| Slate   | #f8f9fa   | #dadce0      | #5f6368    |
| Rose    | #fce8e6   | #f6aea9      | #d93025    |
| Sky     | #e8f0fe   | #d2e3fc      | #1967d2    |

Contrast rules: light fill → dark text (600 series). NEVER white text on light fill."""


CHARTS_CHART_JS = """## Charts (Chart.js)

```html
<div style="position:relative;width:100%;height:280px"><canvas id="c"></canvas></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js" onload="init()"></script>
<script>
var chart;
function init(){
  chart=new Chart(document.getElementById('c'),{
    type:'line',
    data:{labels:['Jan','Feb','Mar','Apr','May'],datasets:[{data:[30,45,28,50,42],borderColor:'#1a73e8',backgroundColor:'rgba(26,115,232,0.1)',fill:true,tension:0.3}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}
  });
}
if(window.Chart) init();
</script>
```

Rules: canvas height on WRAPPER div only; responsive:true; legend disabled; bar borderRadius:6; line tension:0.3."""


SVG_SETUP = """## SVG setup

`<svg width="100%" viewBox="0 0 680 H">` — 680px fixed width, H = max content bottom + 60px.

Mandatory first line: `<rect width="100%" height="100%" fill="#ffffff"/>`

Typography: title 15px #202124, label 13px #3c4043, caption 11px #5f6368.

Arrow marker (required):
```svg
<defs>
  <marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="#5f6368" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
  </marker>
</defs>
```

Arrow size: markerWidth/Height = 4 standard, never > 6. stroke-width = 1.2 standard, never > 1.5."""


DIAGRAM_TYPES = """## Diagram type catalog

- Flowchart — nodes left→right or top→bottom; elbow connectors for non-aligned nodes
- Sequence — two vertical lifelines + horizontal arrows
- Timeline — horizontal baseline + staggered markers
- Cycle — 3-5 nodes on a circle, curved bezier arrows
- Hierarchy — root at top, vertical arrows to children
- Layered stack — full-width horizontal bands
- Quadrant — two cross axes, four quadrant rects

Design rules:
- ≤4 nodes per row, ≤5 words per node title
- Node min-width = chars * 8 + 56px
- Node min-height = 52px (1 line) / +22px per extra line
- 2-3 color ramps max
- Light fill → dark 600-series text"""


MODULE_SECTIONS: dict[str, list[str]] = {
    "interactive": [CORE_DESIGN_SYSTEM, UI_COMPONENTS, COLOR_PALETTE],
    "chart":       [CORE_DESIGN_SYSTEM, UI_COMPONENTS, COLOR_PALETTE, CHARTS_CHART_JS],
    "mockup":      [CORE_DESIGN_SYSTEM, UI_COMPONENTS, COLOR_PALETTE],
    "art":         [CORE_DESIGN_SYSTEM, SVG_SETUP, COLOR_PALETTE],
    "diagram":     [CORE_DESIGN_SYSTEM, COLOR_PALETTE, SVG_SETUP, DIAGRAM_TYPES],
}

AVAILABLE_MODULES = list(MODULE_SECTIONS.keys())


def get_guidelines(module_names: list[str]) -> str:
    """Assemble guidelines from requested modules; deduplicates shared sections."""
    seen: set[str] = set()
    parts: list[str] = []
    for mod in module_names:
        key = mod.lower().strip()
        for section in MODULE_SECTIONS.get(key, []):
            if section not in seen:
                seen.add(section)
                parts.append(section)
    return "\n\n\n".join(parts)


def handle_widget_tool_call(tool_input: dict[str, Any]) -> str:
    """Handle a `load_widget_guidelines` tool call — returns markdown guidelines."""
    modules = tool_input.get("modules") or []
    if not modules:
        return "Error: no modules specified. Available: " + ", ".join(AVAILABLE_MODULES)
    try:
        return f"## Widget Design Guidelines\n\n{get_guidelines(modules)}"
    except Exception as e:  # noqa: BLE001
        return f"Error loading guidelines: {e}"


WIDGET_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "load_widget_guidelines",
        "description": (
            "Load detailed design guidelines for generating visual widgets "
            "(SVG diagrams or interactive HTML). Call this BEFORE generating "
            "your first widget. Modules: interactive, chart, mockup, art, diagram."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "modules": {
                    "type": "array",
                    "items": {"type": "string", "enum": AVAILABLE_MODULES},
                    "description": "Module names to load",
                },
            },
            "required": ["modules"],
        },
    },
}
