# -*- coding: utf-8 -*-
"""클로드_시작하기_발표_v4.html 의 data-speaker-notes 를 뽑아
모바일에서 읽기 좋은 낭독본 페이지(낭독본_시작하기_v4.html)를 생성한다.

덱을 수정한 뒤 다시 실행하면 낭독본이 갱신된다.
    python _build_낭독본.py
"""
import re, html, os, sys, io, subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_dur_cache = {}


def probe(path):
    """data-duration 이 없는 클립은 ffprobe 로 실측한다."""
    if path in _dur_cache:
        return _dur_cache[path]
    val = 0.0
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                            '-of', 'csv=p=0', path], capture_output=True, text=True, timeout=20)
        val = float(r.stdout.strip())
    except Exception:
        pass
    _dur_cache[path] = val
    return val
BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, '클로드_시작하기_발표_v4.html')
OUT = os.path.join(BASE, '낭독본_시작하기_v4.html')
CPM = 315.0  # 한국어 발표 낭독 분당 글자수(공백 포함)

src = open(SRC, encoding='utf-8').read()
secs = list(re.finditer(r'<section\s+class="slide([^"]*)"([^>]*)>', src))
END = src.find('<div id="chrome"')


def attr(a, name):
    m = re.search(r'\b%s="([^"]*)"' % name, a)
    return html.unescape(m.group(1)) if m else ''


def text_of(frag):
    frag = re.sub(r'<!--.*?-->', ' ', frag, flags=re.S)
    frag = re.sub(r'<(script|style).*?</\1>', ' ', frag, flags=re.S)
    frag = re.sub(r'<[^>]+>', '\x00', frag)
    frag = html.unescape(frag)
    parts = [p.strip() for p in frag.split('\x00')]
    return [p for p in parts if p]


slides = []
for i, m in enumerate(secs):
    cls, a = m.group(1), m.group(2)
    start = m.end()
    end = secs[i + 1].start() if i + 1 < len(secs) else END
    frag = src[start:end]

    notes = attr(a, 'data-speaker-notes')
    spoken = re.sub(r'\s+', ' ', re.sub(r'\[[^\]]*\]', '', notes)).strip()

    def grab(c):
        mm = re.search(r'class="[^"]*\b%s\b[^"]*"[^>]*>(.*?)</' % c, frag, re.S)
        return ' '.join(text_of(mm.group(1))) if mm else ''

    title = grab('h-title') or grab('d-title') or grab('cover-title')
    lead = grab('h-lead') or grab('d-sub')
    eyebrow = grab('eyebrow') or grab('d-kicker')
    pn = re.search(r'class="pageno">([^<]*)<', frag)

    # 미디어 — 재생 버튼과 플레이스홀더
    # 주석 안의 자리표시자 버튼은 제외 — 실제로 렌더링되는 것만 센다
    live = re.sub(r'<!--.*?-->', ' ', frag, flags=re.S)
    media = []
    for tag in re.findall(r'<button[^>]*data-video="[^"]*"[^>]*>', live):
        vid = attr(tag, 'data-video')
        full = os.path.join(BASE, vid)
        exists = os.path.exists(full)
        dur = attr(tag, 'data-duration')
        dur = float(dur) if dur else (probe(full) if exists else 0.0)
        media.append({'src': vid, 'dur': dur, 'ok': exists})
    ph = 'placeholder' in live

    # 화면 요약 — fact 카드 제목
    facts = re.findall(r'class="fact-t">([^<]*)</div><div class="fact-d">([^<]*)', frag)

    slides.append({
        'no': i + 1, 'id': attr(a, 'id'), 'label': attr(a, 'data-label'),
        'part': attr(a, 'data-part'), 'divider': 'divider' in cls,
        'cover': attr(a, 'id') == 'cover',
        'pageno': pn.group(1) if pn else '', 'eyebrow': eyebrow,
        'title': title, 'lead': lead, 'notes': notes, 'spoken': spoken,
        'chars': len(spoken), 'secs': len(spoken) / CPM * 60,
        'media': media, 'placeholder': ph, 'facts': facts,
    })

tot_chars = sum(s['chars'] for s in slides)
tot_read = tot_chars / CPM
seen, tot_vid = set(), 0.0
for s in slides:
    for md in s['media']:
        if md['src'] in seen or not md['dur']:
            continue
        seen.add(md['src'])
        tot_vid += md['dur']


def cue(note):
    """대괄호 무대 지시를 칩으로, 나머지는 대사로."""
    out = []
    for piece in re.split(r'(\[[^\]]*\])', note):
        if not piece.strip():
            continue
        if piece.startswith('['):
            out.append('<span class="cue">%s</span>' % html.escape(piece[1:-1]))
        else:
            for sent in re.split(r'(?<=[.?!])\s+', piece.strip()):
                if sent.strip():
                    out.append('<span class="say">%s</span>' % html.escape(sent.strip()))
    return '\n'.join(out)


cards, cur_part = [], None
for s in slides:
    if s['part'] and s['part'] != cur_part:
        cur_part = s['part']
        cards.append('<h2 class="partbar" id="part-%d">%s</h2>' % (s['no'], html.escape(cur_part)))

    badge = s['pageno'] or '—'
    meta = ['<span class="m n">%s</span>' % html.escape(badge)]
    if s['chars']:
        meta.append('<span class="m">%d자 · 약 %d초</span>' % (s['chars'], round(s['secs'])))
    for md in s['media']:
        d = ('%.0f초' % md['dur']) if md['dur'] else '?'
        cl = 'm clip' + ('' if md['ok'] else ' bad')
        tail = '' if md['ok'] else ' · 파일 없음'
        meta.append('<span class="%s">▶ %s%s</span>' % (cl, d, tail))
    if s['placeholder']:
        meta.append('<span class="m bad">영상 미촬영</span>')

    head = []
    if s['eyebrow']:
        head.append('<div class="eyebrow">%s</div>' % html.escape(s['eyebrow']))
    head.append('<h3>%s</h3>' % html.escape(s['title'] or s['label']))
    if s['lead']:
        head.append('<p class="lead">%s</p>' % html.escape(s['lead']))

    scr = ''
    if s['facts']:
        rows = ''.join('<li><b>%s</b> %s</li>' % (html.escape(t), html.escape(d)) for t, d in s['facts'])
        scr = '<details class="screen"><summary>화면에 뜨는 내용 %d칸</summary><ul>%s</ul></details>' % (len(s['facts']), rows)

    body = cue(s['notes']) if s['notes'] else '<span class="none">정해진 발화 없음</span>'

    cards.append(
        '<article class="card%s" id="s%d">\n'
        '<div class="meta">%s</div>\n<div class="hd">%s</div>\n%s\n<div class="script">%s</div>\n</article>'
        % (' divider' if s['divider'] else '', s['no'], ''.join(meta), ''.join(head), scr, body)
    )

toc = ''.join(
    '<a href="#s%d"><b>%s</b>%s</a>' % (s['no'], html.escape(s['pageno'] or '·'), html.escape(s['label']))
    for s in slides
)

PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>낭독본 · 클로드 시작하기</title>
<meta name="description" content="클로드 시작하기 발표 v4 — 슬라이드 29장 낭독 대사와 무대 지시">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<style>
:root{--paper:#fdfcfa;--paper-2:#f6f2ea;--ink:#2b2a28;--muted:#736c62;--line:#e6ded1;
--teal:#5a9687;--teal-deep:#3f7a6d;--mustard-deep:#b07d12;--coral:#d66f53;--coral-deep:#c96a4f}
@media(prefers-color-scheme:dark){:root{--paper:#171614;--paper-2:#201e1b;--ink:#f0ece5;--muted:#a49b8f;--line:#38342e;
--teal:#7ab5a5;--teal-deep:#8ec4b4;--mustard-deep:#e0ad3c;--coral:#e2896c;--coral-deep:#e8886c}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);
font-family:"Pretendard Variable",Pretendard,-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
font-size:17px;line-height:1.72;letter-spacing:-.01em;
padding:0 0 calc(64px + env(safe-area-inset-bottom))}
.wrap{max-width:720px;margin:0 auto;padding:0 18px}
header.top{padding:38px 0 22px;border-bottom:3px solid var(--ink);margin-bottom:8px}
header.top .kick{font-size:12.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--coral-deep);font-weight:700}
header.top h1{margin:.32em 0 .1em;font-size:31px;line-height:1.22;letter-spacing:-.03em;font-weight:800}
header.top p{margin:.5em 0 0;color:var(--muted);font-size:14.5px;line-height:1.6}
.stats{display:flex;flex-wrap:wrap;gap:7px;margin-top:15px}
.stats span{background:var(--paper-2);border:1px solid var(--line);border-radius:999px;
padding:5px 12px;font-size:12.5px;font-variant-numeric:tabular-nums;color:var(--muted)}
.stats span b{color:var(--ink);font-weight:700}
details.toc{margin:16px 0 6px;border:1px solid var(--line);border-radius:12px;background:var(--paper-2)}
details.toc summary{cursor:pointer;padding:12px 15px;font-weight:700;font-size:14px;list-style:none}
details.toc summary::-webkit-details-marker{display:none}
details.toc summary::after{content:" ▾";color:var(--muted)}
details.toc[open] summary::after{content:" ▴"}
.toclist{display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:2px;padding:4px 9px 12px}
.toclist a{display:flex;gap:7px;align-items:baseline;text-decoration:none;color:var(--ink);
padding:6px 7px;border-radius:7px;font-size:13.5px;line-height:1.35}
.toclist a:active{background:var(--line)}
.toclist a b{color:var(--coral-deep);font-variant-numeric:tabular-nums;font-size:11.5px;min-width:19px}
h2.partbar{position:sticky;top:0;z-index:5;margin:34px -18px 14px;padding:11px 18px;
background:var(--ink);color:var(--paper);font-size:12.5px;font-weight:700;letter-spacing:.13em}
.card{border-top:1px solid var(--line);padding:24px 0 28px}
.card.divider{background:linear-gradient(var(--paper-2),var(--paper-2)) padding-box;
margin:0 -18px;padding:22px 18px 24px;border-top:0}
.meta{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:11px}
.m{font-size:11.5px;font-weight:600;color:var(--muted);background:var(--paper-2);
border:1px solid var(--line);border-radius:5px;padding:3px 8px;font-variant-numeric:tabular-nums}
.m.n{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.m.clip{color:var(--teal-deep);border-color:var(--teal);background:transparent}
.m.bad{color:#fff;background:var(--coral-deep);border-color:var(--coral-deep)}
.hd .eyebrow{font-size:11.5px;letter-spacing:.1em;color:var(--coral-deep);font-weight:700;margin-bottom:5px}
.hd h3{margin:0;font-size:20.5px;line-height:1.36;letter-spacing:-.025em;font-weight:800}
.hd .lead{margin:.45em 0 0;color:var(--muted);font-size:14px;line-height:1.55}
details.screen{margin:13px 0 0;font-size:13.5px}
details.screen summary{cursor:pointer;color:var(--teal-deep);font-weight:600;list-style:none}
details.screen summary::-webkit-details-marker{display:none}
details.screen summary::before{content:"▸ ";}
details.screen[open] summary::before{content:"▾ "}
details.screen ul{margin:9px 0 0;padding-left:17px;color:var(--muted);line-height:1.62}
details.screen li{margin-bottom:5px}
details.screen b{color:var(--ink)}
.script{margin-top:16px;padding-left:15px;border-left:3px solid var(--mustard-deep)}
.say{display:block;margin:0 0 .42em;font-size:17.5px;line-height:1.78}
.cue{display:block;margin:.7em 0 .55em;padding:7px 11px;border-radius:8px;
background:rgba(214,111,83,.12);border:1px dashed var(--coral);
color:var(--coral-deep);font-size:13.5px;font-weight:700;line-height:1.5}
.none{color:var(--muted);font-style:italic}
footer{margin-top:44px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:12.5px;line-height:1.7}
footer a{color:var(--coral-deep)}
.back{position:fixed;right:16px;bottom:calc(16px + env(safe-area-inset-bottom));z-index:20;
width:46px;height:46px;border-radius:50%;border:1px solid var(--line);background:var(--paper);
color:var(--ink);font-size:17px;box-shadow:0 3px 14px rgba(0,0,0,.14);cursor:pointer;
opacity:0;pointer-events:none;transition:opacity .2s}
.back.on{opacity:1;pointer-events:auto}
@media(min-width:760px){body{font-size:18px}.hd h3{font-size:23px}.say{font-size:18.5px}}
</style>
</head>
<body>
<div class="wrap">
<header class="top">
  <div class="kick">발표자 낭독본 · v4</div>
  <h1>클로드 시작하기</h1>
  <p>슬라이드 __N__장의 낭독 대사와 무대 지시입니다.
  <b style="color:var(--coral-deep)">붉은 점선 칸</b>은 말하지 않고 조작하는 지시,
  그 아래 본문이 실제로 읽는 대사입니다.</p>
  <div class="stats">
    <span>낭독 <b>__CHARS__자</b></span>
    <span>읽는 시간 <b>약 __READ__분</b></span>
    <span>영상 <b>__VID__분</b></span>
    <span>합계 <b>약 __TOT__분</b></span>
  </div>
</header>

<details class="toc"><summary>슬라이드 목차</summary><div class="toclist">__TOC__</div></details>

__CARDS__

<footer>
낭독 시간은 분당 315자 기준 추정입니다. 합계는 낭독과 영상이 절반쯤 겹친다고 본 값입니다.<br>
발표 덱 → <a href="클로드_시작하기_발표_v4.html">클로드_시작하기_발표_v4.html</a><br>
이 페이지는 <code>_build_낭독본.py</code>가 덱의 <code>data-speaker-notes</code>에서 생성합니다. 덱을 고치면 다시 돌려 주세요.
</footer>
</div>
<button class="back" id="back" aria-label="맨 위로">↑</button>
<script>
var b=document.getElementById('back');
addEventListener('scroll',function(){b.classList.toggle('on',scrollY>700)},{passive:true});
b.onclick=function(){scrollTo({top:0,behavior:'smooth'})};
</script>
</body>
</html>
"""

out = (PAGE
       .replace('__N__', str(len(slides)))
       .replace('__CHARS__', '{:,}'.format(tot_chars))
       .replace('__READ__', '%.1f' % tot_read)
       .replace('__VID__', '%.1f' % (tot_vid / 60))
       .replace('__TOT__', '%.0f' % (tot_read + tot_vid / 60 * 0.5))
       .replace('__TOC__', toc)
       .replace('__CARDS__', '\n\n'.join(cards)))

open(OUT, 'w', encoding='utf-8').write(out)
print('생성: %s' % os.path.basename(OUT))
print('슬라이드 %d장 · 낭독 %d자(약 %.1f분) · 영상 %.1f분' % (len(slides), tot_chars, tot_read, tot_vid / 60))
