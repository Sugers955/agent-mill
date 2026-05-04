/**
 * widget-theme — minimal CSS bridge for widget iframe.
 *
 * Maps h3c-agent's Google-style design tokens into the iframe so widget
 * markup that uses utility classes (flex/gap/text-sm) renders consistently.
 * Intentionally trimmed vs agent-ide's widget-css-bridge — we only ship what
 * widget templates actually use.
 */

export function getWidgetIframeStyleBlock(): string {
  return `
:root {
  --color-bg: #ffffff;
  --color-bg-soft: #fafbfc;
  --color-bg-hover: #f8f9fa;
  --color-border: #e8eaed;
  --color-border-strong: #dadce0;
  --color-text: #202124;
  --color-text-body: #3c4043;
  --color-text-secondary: #5f6368;
  --color-text-meta: #80868b;
  --color-primary: #1a73e8;
  --color-primary-soft: #e8f0fe;
  --color-success: #1e8e3e;
  --color-warning: #f29900;
  --color-danger: #d93025;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --shadow-sm: 0 1px 2px rgba(60,64,67,.08), 0 1px 3px 1px rgba(60,64,67,.04);
  --shadow-md: 0 1px 2px rgba(60,64,67,.10), 0 2px 6px 2px rgba(60,64,67,.08);
}

/* Display / flex / grid */
.flex { display: flex; }
.inline-flex { display: inline-flex; }
.grid { display: grid; }
.flex-col { flex-direction: column; }
.flex-wrap { flex-wrap: wrap; }
.flex-1 { flex: 1 1 0%; }
.items-center { align-items: center; }
.items-start { align-items: flex-start; }
.justify-between { justify-content: space-between; }
.justify-center { justify-content: center; }
.grid-cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.grid-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.grid-cols-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }

/* Gap / spacing */
.gap-1 { gap: 4px; } .gap-2 { gap: 8px; } .gap-3 { gap: 12px; }
.gap-4 { gap: 16px; } .gap-6 { gap: 24px; }
.p-2 { padding: 8px; } .p-3 { padding: 12px; } .p-4 { padding: 16px; } .p-5 { padding: 20px; }
.px-3 { padding-left: 12px; padding-right: 12px; } .py-2 { padding-top: 8px; padding-bottom: 8px; }
.mb-2 { margin-bottom: 8px; } .mb-3 { margin-bottom: 12px; } .mb-4 { margin-bottom: 16px; }
.mt-2 { margin-top: 8px; } .mt-3 { margin-top: 12px; } .mt-4 { margin-top: 16px; }

/* Width / height */
.w-full { width: 100%; }
.h-full { height: 100%; }

/* Typography */
.text-xs { font-size: 11px; line-height: 1.5; }
.text-sm { font-size: 13px; line-height: 1.5; }
.text-base { font-size: 15px; line-height: 1.6; }
.text-lg { font-size: 18px; line-height: 1.5; }
.text-xl { font-size: 22px; line-height: 1.4; }
.font-medium { font-weight: 500; }
.font-semibold { font-weight: 600; }
.text-center { text-align: center; }
.uppercase { text-transform: uppercase; }
.tracking-wide { letter-spacing: 0.04em; }

/* Semantic typography helpers */
.text-title { font-size: 15px; font-weight: 500; color: #202124; line-height: 1.4; }
.text-body { font-size: 13px; color: #3c4043; line-height: 1.6; }
.text-caption { font-size: 11px; color: #5f6368; line-height: 1.5; }
.text-eyebrow { font-size: 11px; font-weight: 500; letter-spacing: 0.06em;
  text-transform: uppercase; color: #80868b; }

/* Colors — Google palette */
.bg-white { background-color: #ffffff; }
.bg-soft { background-color: #fafbfc; }
.bg-primary-soft { background-color: #e8f0fe; }
.bg-success-soft { background-color: #e6f4ea; }
.bg-warning-soft { background-color: #fef7e0; }
.bg-danger-soft { background-color: #fce8e6; }
.bg-neutral-soft { background-color: #f8f9fa; }
.text-primary { color: #1a73e8; }
.text-success { color: #1e8e3e; }
.text-warning { color: #f29900; }
.text-danger { color: #d93025; }
.text-neutral { color: #5f6368; }

/* Borders / radius / shadow */
.border { border: 1px solid #e8eaed; }
.rounded { border-radius: 8px; }
.rounded-md { border-radius: 12px; }
.rounded-lg { border-radius: 16px; }
.rounded-full { border-radius: 9999px; }
.shadow-sm { box-shadow: 0 1px 2px rgba(60,64,67,.08), 0 1px 3px 1px rgba(60,64,67,.04); }
.shadow-md { box-shadow: 0 1px 2px rgba(60,64,67,.10), 0 2px 6px 2px rgba(60,64,67,.08); }

/* Form elements (pre-styled) */
input[type="text"], input[type="number"], select, textarea {
  height: 36px; padding: 0 12px;
  border: 1px solid #dadce0; border-radius: 8px;
  background: #ffffff; color: #202124;
  font: 500 13px 'Inter', system-ui, sans-serif;
  outline: none; transition: border-color .15s, box-shadow .15s;
}
input:focus, select:focus, textarea:focus {
  border-color: #1a73e8; box-shadow: 0 0 0 3px rgba(26,115,232,.15);
}
button {
  background: #ffffff; color: #3c4043;
  border: 1px solid #dadce0; border-radius: 8px;
  padding: 8px 16px; font: 500 13px 'Inter', system-ui, sans-serif;
  cursor: pointer; transition: background .15s, box-shadow .15s, transform .1s;
  box-shadow: 0 1px 2px rgba(60,64,67,.08);
}
button:hover { background: #f8f9fa; box-shadow: 0 1px 3px rgba(60,64,67,.12); }
button:active { transform: scale(0.98); background: #f1f3f4; }
button.primary { background: #1a73e8; color: #fff; border-color: #1a73e8; }
button.primary:hover { background: #185abc; border-color: #185abc; }
input[type="range"] {
  height: 4px; -webkit-appearance: none; appearance: none;
  background: #e8eaed; border-radius: 2px; outline: none; width: 100%;
}
input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none; width: 16px; height: 16px;
  border-radius: 50%; background: #1a73e8; cursor: pointer;
  border: 2px solid #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}

/* Streaming-friendly fade-in for new content blocks */
@keyframes widgetFadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
`
}
