/**
 * widget-sanitizer — sanitize widget HTML and build the iframe srcdoc.
 *
 * Two sanitize levels:
 *   - sanitizeForStreaming  : strip ALL on*, scripts, javascript:/data:; safe preview
 *   - sanitizeForIframe     : light strip (only dangerous embed tags); scripts run inside the sandbox
 *
 * The iframe is locked down: sandbox="allow-scripts" only (no same-origin),
 * CSP blocks connect-src, allow scripts only from a tight CDN whitelist.
 */

export const CDN_WHITELIST = [
  'cdnjs.cloudflare.com',
  'cdn.jsdelivr.net',
  'unpkg.com',
  'esm.sh',
]

const DANGEROUS_TAGS = /<(iframe|object|embed|meta|link|base|form)[\s>][\s\S]*?<\/\1>/gi
const DANGEROUS_VOID = /<(iframe|object|embed|meta|link|base)\b[^>]*\/?>/gi

export function sanitizeForStreaming(html: string): string {
  return html
    .replace(DANGEROUS_TAGS, '')
    .replace(DANGEROUS_VOID, '')
    .replace(/\s+on[a-z]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>"']*)/gi, '')
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<script\b[^>]*\/?>/gi, '')
    .replace(
      /\s+(href|src|action)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>"']*))/gi,
      (match, _attr, dq, sq, uq) => {
        const url = (dq ?? sq ?? uq ?? '').trim()
        if (/^\s*(javascript|data)\s*:/i.test(url)) return ''
        return match
      },
    )
}

export function sanitizeForIframe(html: string): string {
  return html.replace(DANGEROUS_TAGS, '').replace(DANGEROUS_VOID, '')
}

/** Build the receiver iframe's srcdoc. */
export function buildReceiverSrcdoc(styleBlock: string): string {
  const cspDomains = CDN_WHITELIST.map((d) => 'https://' + d).join(' ')
  const csp = [
    "default-src 'none'",
    `script-src 'unsafe-inline' 'unsafe-eval' ${cspDomains}`,
    "style-src 'unsafe-inline'",
    'img-src * data: blob:',
    'font-src * data:',
    "connect-src 'none'",
  ].join('; ')

  // Receiver script — listens for widget:update / widget:finalize from parent,
  // syncs iframe height back via widget:resize.
  const receiverScript = `(function(){
var root=document.getElementById('__root');
var _t=null,_first=true,_lastH=0,_streaming=false;
function _measure(){
  var r=root.getBoundingClientRect();
  var h=Math.ceil(r.height);
  // Defensive: when the model gave a viewBox shorter than the actual SVG
  // content, the element bounding box is smaller than what's drawn. Use
  // getBBox() to recover the true content extent and resize accordingly.
  var svg=root.querySelector('svg');
  if(svg&&typeof svg.getBBox==='function'){
    try{
      var bb=svg.getBBox();
      var svgRect=svg.getBoundingClientRect();
      var vb=svg.viewBox&&svg.viewBox.baseVal;
      var contentBottom=bb.y+bb.height;
      if(vb&&vb.width>0&&vb.height>0&&contentBottom>vb.height){
        var scale=svgRect.width/vb.width;
        h=Math.max(h,Math.ceil(contentBottom*scale+12));
      }
    }catch(e){}
  }
  // 12px safety margin avoids hairline cropping at the bottom.
  return h+12;
}
function _h(){
  if(_t)clearTimeout(_t);
  _t=setTimeout(function(){
    var h=_measure();
    if(h<60)h=60;
    if(h>0&&h!==_lastH){
      _lastH=h;
      parent.postMessage({type:'widget:resize',height:h,first:_first},'*');
    }
    _first=false;
  },40);
}
new ResizeObserver(_h).observe(root);

function setStreaming(on){
  _streaming=!!on;
  document.body.classList.toggle('is-streaming',_streaming);
}

function applyHtml(html){
  if(root.innerHTML===html)return;
  root.innerHTML=html;
  _h();
}

function finalizeHtml(html){
  var tmp=document.createElement('div');
  tmp.innerHTML=html;
  var ss=tmp.querySelectorAll('script');
  var scripts=[];
  for(var i=0;i<ss.length;i++){
    scripts.push({src:ss[i].src||'',text:ss[i].textContent||'',attrs:[]});
    for(var j=0;j<ss[i].attributes.length;j++){
      var a=ss[i].attributes[j];
      if(a.name!=='src')scripts[scripts.length-1].attrs.push({name:a.name,value:a.value});
    }
    ss[i].remove();
  }
  root.innerHTML=tmp.innerHTML;
  var cdn=scripts.filter(function(s){return !!s.src});
  var inline=scripts.filter(function(s){return !s.src&&s.text});
  function _appendInline(){
    for(var k=0;k<inline.length;k++){
      var s=document.createElement('script');
      s.textContent=inline[k].text;
      for(var j=0;j<inline[k].attrs.length;j++)
        s.setAttribute(inline[k].attrs[j].name,inline[k].attrs[j].value);
      root.appendChild(s);
    }
    _h();
    setTimeout(function(){parent.postMessage({type:'widget:scriptsReady'},'*')},50);
  }
  if(cdn.length===0){_appendInline()}
  else{
    var pending=cdn.length;
    function done(){pending--;if(pending<=0)_appendInline()}
    for(var i=0;i<cdn.length;i++){
      var n=document.createElement('script');
      n.src=cdn[i].src;n.onload=done;n.onerror=done;
      for(var j=0;j<cdn[i].attrs.length;j++){
        if(cdn[i].attrs[j].name!=='onload')n.setAttribute(cdn[i].attrs[j].name,cdn[i].attrs[j].value);
      }
      root.appendChild(n);
    }
  }
  _h();
}

window.addEventListener('message',function(e){
  if(!e.data)return;
  switch(e.data.type){
    case 'widget:setStreaming':setStreaming(e.data.on);break;
    case 'widget:update':setStreaming(true);applyHtml(e.data.html);break;
    case 'widget:finalize':
      setStreaming(false);
      finalizeHtml(e.data.html);
      // Re-measure several times to catch async growth (Chart.js render,
      // image decode, layout settling).
      setTimeout(_h,150);
      setTimeout(_h,400);
      setTimeout(_h,900);
      break;
  }
});

document.addEventListener('click',function(e){
  var a=e.target&&e.target.closest?e.target.closest('a[href]'):null;
  if(!a)return;
  var h=a.getAttribute('href');
  if(!h||h.charAt(0)==='#')return;
  e.preventDefault();
  parent.postMessage({type:'widget:link',href:h},'*');
});

window.__widgetSendMessage=function(t){
  if(typeof t!=='string'||t.length>500)return;
  parent.postMessage({type:'widget:sendMessage',text:t},'*');
};

parent.postMessage({type:'widget:ready'},'*');
})();`

  // Block AI-generated dark backgrounds defensively (override to light).
  const lightThemeOverride = `
svg > rect:first-child[fill*="#1"],
svg > rect:first-child[fill*="#0"],
svg > rect:first-child[fill="#000"],
svg > rect:first-child[fill="black"] {
  fill: #ffffff !important;
}`

  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<style>
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #ffffff; color: #3c4043;
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
  font-size: 14px; line-height: 1.6; }
html, body { height: 100%; }
#__root { width: 100%; min-height: 100%; height: fit-content; background: transparent; }

/* While streaming, force every direct child of #__root to fill the available
   width. We do NOT force a height — that lets the iframe naturally grow as
   the SVG/HTML content gets longer (ResizeObserver reports the true height). */
body.is-streaming #__root > svg {
  width: 100% !important;
  height: auto !important;
  display: block;
  max-width: 100%;
}
body.is-streaming #__root > div,
body.is-streaming #__root > section,
body.is-streaming #__root > article,
body.is-streaming #__root > main {
  width: 100% !important;
}

a { color: #1a73e8; text-decoration: none; }
a:hover { text-decoration: underline; }
button { cursor: pointer; }
${lightThemeOverride}
${styleBlock}
</style>
</head>
<body>
<div id="__root"></div>
<script>${receiverScript}</script>
</body>
</html>`
}
