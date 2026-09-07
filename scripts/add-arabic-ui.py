#!/usr/bin/env python3
"""Inject a visible Arabic/English prompt-language switch into the library UI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "library-pro.html", ROOT / "smart-search.html", ROOT / "prompt-details.html"]
MARK = "<!-- MM_ARABIC_UI_V1 -->"

CSS = """
<style id="mm-arabic-ui-style">
.mm-langbar{position:sticky;top:8px;z-index:50;display:flex;align-items:center;justify-content:center;gap:7px;margin:10px 0;padding:9px;background:#fff;border:1px solid #dbe3ef;border-radius:12px;box-shadow:0 4px 16px #00000010}.mm-langbar b{font-size:13px}.mm-langbar button{border:1px solid #cbd5e1;background:#f8fafc;color:#172033;border-radius:9px;padding:8px 13px;cursor:pointer;font-weight:700}.mm-langbar button.active{background:#312e81;color:#fff;border-color:#312e81}.mm-lang-note{font-size:11px;color:#64748b}
</style>
"""

JS = r"""
<script id="mm-arabic-ui-script">
(()=>{
  if(window.__MM_ARABIC_UI__) return; window.__MM_ARABIC_UI__=true;
  const KEY='mm_prompt_language'; let lang=localStorage.getItem(KEY)||'ar'; let map=new Map();
  const esc=s=>String(s??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  async function load(){try{const r=await fetch('./data/prompts.json?lang_ui='+Date.now(),{cache:'no-store'});const d=await r.json();(d.prompts||[]).forEach(p=>map.set(String(p.id),p));}catch(e){} render();}
  function getId(card){const b=card.querySelector('[data-details]');return b?String(b.getAttribute('data-details')):null;}
  function apply(){
    document.querySelectorAll('[data-mm-prompt]').forEach(el=>{const p=map.get(String(el.dataset.mmPrompt));if(!p)return;el.innerHTML=esc(lang==='ar'?(p.prompt_ar||p.prompt||''):(p.prompt||p.prompt_ar||''));});
    document.querySelectorAll('.mm-langbar button').forEach(b=>b.classList.toggle('active',b.dataset.lang===lang));
    const note=document.querySelector('.mm-lang-note');if(note)note.textContent=lang==='ar'?'العربية هي اللغة الافتراضية — الأصل الإنجليزي محفوظ':'English source is shown — الترجمة العربية محفوظة';
  }
  function scan(){document.querySelectorAll('article').forEach(card=>{const id=getId(card);if(!id)return;const p=card.querySelector('.prompt');if(p&&!p.dataset.mmPrompt){p.dataset.mmPrompt=id;}});apply();}
  function render(){scan();}
  function bar(){
    if(document.querySelector('.mm-langbar'))return;
    const bar=document.createElement('div');bar.className='mm-langbar';bar.innerHTML='<b>لغة البرومبت:</b><button data-lang="ar">🇪🇬 العربية</button><button data-lang="en">🇬🇧 English</button><span class="mm-lang-note"></span>';
    const main=document.querySelector('main')||document.body;main.prepend(bar);
    bar.querySelectorAll('button').forEach(b=>b.onclick=()=>{lang=b.dataset.lang;localStorage.setItem(KEY,lang);apply();});
  }
  bar(); load();
  new MutationObserver(()=>scan()).observe(document.body,{childList:true,subtree:true});
})();
</script>
"""

for path in FILES:
    if not path.exists():
        continue
    text = path.read_text(encoding='utf-8')
    if MARK in text:
        continue
    payload = MARK + CSS + JS
    if '</body>' in text:
        text = text.replace('</body>', payload + '</body>', 1)
    else:
        text += payload
    path.write_text(text, encoding='utf-8')
    print('patched', path)
