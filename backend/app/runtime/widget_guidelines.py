"""Widget design guidelines + in-process tool for generative UI."""

from typing import Any

WIDGET_SYSTEM_PROMPT = """<widget-capability>
You can create interactive visualizations using the `show-widget` code fence.

CRITICAL RULE: Always use show-widget fence -- never write files, never output raw SVG.

```show-widget
{"title":"human-readable title","widget_code":"<svg width=\\"100%\\" viewBox=\\"0 0 W H\\">...</svg>"}
```

widget_code is a JSON string: escape every quote as \\", every newline as \\n. No DOCTYPE/html/head/body.

LAYOUT PLANNING (mandatory -- complete ALL steps mentally before writing SVG):

STEP 1 -- Measure every label precisely:
  CJK character width = 14px, Latin/digit = 8px, space = 4px
  line_w = sum of char widths in that line
  Wrap rule: start a new line when line_w > 200px (prefer wrapping at word/punctuation boundaries)
  lines_count = number of wrapped lines for this label

STEP 2 -- Calculate each node's bounding box:
  node_w = max(120, min(280, widest_line_w + 56))   [56 = 28px padding each side]
  node_h = 44 + (lines_count - 1) * 22              [44 for first line; 22 per extra line]
  Write down every node's (x, y, w, h) before drawing anything.

STEP 3 -- Place nodes with guaranteed clearance:
  Horizontal gap between siblings  = max(60, 0.5 * max_node_w_in_row)
  Vertical gap between rows        = max(56, 0.4 * max_node_h_in_column)
  col_x[i] = margin_left + sum(node_w[0..i-1]) + i * h_gap   [margin_left = 40]
  row_y[j] = margin_top  + sum(node_h[0..j-1]) + j * v_gap   [margin_top  = 48]
  Node center: cx = col_x[i] + node_w/2,  cy = row_y[j] + node_h/2

STEP 4 -- Compute viewBox dimensions (NEVER guess):
  canvas_w = col_x[last_col] + node_w[last_col] + 40    (min 520)
  canvas_h = row_y[last_row] + node_h[last_row] + 56    (min 300)
  Write: viewBox="0 0 {canvas_w} {canvas_h}"

STEP 5 -- Compute arrow endpoints precisely (avoid piercing nodes):
  Top->Bottom : x1=src_cx, y1=src_y+src_h,       x2=dst_cx, y2=dst_y
  Bottom->Top : x1=src_cx, y1=src_y,             x2=dst_cx, y2=dst_y+dst_h
  Left->Right : x1=src_x+src_w, y1=src_cy,       x2=dst_x,  y2=dst_cy
  Right->Left : x1=src_x,       y1=src_cy,       x2=dst_x+dst_w, y2=dst_cy
  Non-aligned elbow: M x1 y1 L x1 mid_y L x2 mid_y L x2 y2  (mid_y=(y1+y2)/2)
  Shorten each end by 2px from the node edge to leave a clean gap.

STEP 6 -- Draw order (strict):
  <defs> -> background <rect> -> node <rect>s -> node <text>s -> arrows last

VISUAL QUALITY -- Google-Material light theme:
- Primary: fill #e8f0fe / stroke #aecbfa / accent #1a73e8
- Success: fill #e6f4ea / stroke #a8dab5 / accent #1e8e3e
- Warning: fill #fef7e0 / stroke #feefc3 / accent #f29900
- Neutral: fill #f8f9fa / stroke #dadce0 / accent #5f6368
- Error:   fill #fce8e6 / stroke #f6aea9 / accent #d93025
- Background: ALWAYS fill="#ffffff" or fill="#fafbfc" -- never dark.

Typography: title 15px #202124, label 13px #3c4043, caption 11px #5f6368.
  NEVER below 11px. NEVER font-weight 700 (bold).
  Multi-line text: dominant-baseline="middle", first line at cy-(lines-1)*11, each next +22px

HTML vs SVG decision:
- Calculator/form/inputs/tabs -> HTML (needs click + state)
- Flowchart/sequence/timeline/architecture/hierarchy -> SVG (drawing connections)

FORBIDDEN:
- Writing coordinates before completing steps 1-4
- Arrows that pass through or overlap other nodes
- canvas_h smaller than actual content bottom (always re-verify)
- font-size below 11px
- Raw <svg> output without the show-widget fence
- Dark backgrounds, neon colors, gradients on node fills

Required rules:
1. widget_code is a JSON string -- escape quotes/newlines; no DOCTYPE/html/body
2. Light theme: bg #ffffff/#fafbfc; never dark
3. Each widget <= 4000 chars. Always close JSON + fence on its own line
4. Draw order: <defs> -> rects -> text -> arrows
5. CDN allowlist: cdnjs.cloudflare.com, cdn.jsdelivr.net, unpkg.com, esm.sh
6. CDN scripts: onload="init()" + if(window.Lib) init(); fallback
7. Text explanations OUTSIDE the code fence
8. Multi-widget: each in a separate fence
9. SVG: <svg width="100%" viewBox="0 0 {canvas_w} {canvas_h}">, ALWAYS first child <rect width="100%" height="100%" fill="#ffffff"/>
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

`<svg width="100%" viewBox="0 0 {canvas_w} {canvas_h}">` -- canvas_w/H computed from content (see LAYOUT PLANNING steps).

Mandatory first child: `<rect width="100%" height="100%" fill="#ffffff"/>`

Typography: title 15px #202124, label 13px #3c4043, caption 11px #5f6368.

Arrow marker (required in <defs>):
```svg
<defs>
  <marker id="a" viewBox="0 0 10 10" refX="9" refY="5"
          markerWidth="4" markerHeight="4" orient="auto-start-reverse">
    <path d="M2 1L9 5L2 9" fill="none" stroke="#5f6368"
          stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
  </marker>
</defs>
```

Arrow connection rules:
- marker-end="url(#a)" on every <line> or <path>
- LINE: x1/y1 = source node edge (not center); x2/y2 = dest node edge (not center)
- PATH elbow (non-aligned nodes): M x1 y1 L x1 mid_y L x2 mid_y L x2 y2
  where mid_y = (y1 + y2) / 2 -- produces clean right-angle bends, never diagonal
- Shorten each endpoint 2px from the node rect edge to prevent overlap with node border.
- markerWidth/Height = 4 (never > 6). stroke-width = 1.2 (never > 1.5).

Height rule: canvas_h = row_y[last] + node_h[last] + 56. NEVER hardcode a value smaller than content requires."""


DIAGRAM_TYPES = """## Diagram type catalog

Flowchart    -- nodes left->right or top->bottom; elbow paths for non-aligned nodes
Sequence     -- two vertical lifelines + horizontal arrows; lifeline height = n_messages*60+80
Timeline     -- horizontal baseline y=fixed; markers stagger above/below to avoid overlap
Cycle        -- N nodes on a circle r=120; node_angle=i*360/N; bezier arrows along arc
Hierarchy    -- root at top y=48; each level adds row_h+v_gap; children centered under parent
Layered stack -- full-width horizontal bands; band_h = max(node_h)+32; stacked vertically
Quadrant     -- two cross axes at canvas center; four rect zones; items placed by score

Layout rules (apply to ALL diagram types):
- node_w = max(120, min(280, widest_label_px + 56))
- node_h = 44 + (extra_lines * 22)  [44 for 1 line; +22 per extra line]
- Horizontal gap >= max(60, 0.5 * max_node_w)
- Vertical gap   >= max(56, 0.4 * max_node_h)
- canvas_w = rightmost (node_x + node_w) + 40  (min 520)
- canvas_h = bottommost (node_y + node_h) + 56 (min 300)
- Max 4 nodes per row; max 5 words per node title
- 2-3 color ramps max; light fill with 600-series text"""


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
    """Handle a `load_widget_guidelines` tool call — returns a short confirmation."""
    modules = tool_input.get("modules") or []
    if not modules:
        return "Error: no modules specified. Available: " + ", ".join(AVAILABLE_MODULES)
    invalid = [m for m in modules if m not in AVAILABLE_MODULES]
    if invalid:
        return f"Warning: unknown module(s): {', '.join(invalid)}. Available: {', '.join(AVAILABLE_MODULES)}"
    return f"✅ 已加载 {len(modules)} 个模块：{'、'.join(modules)}。请按指引生成 widget。"


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
