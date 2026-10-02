"""Write the public gallery page and the blog (static HTML, built by Vite like the rest of the site).

    .venv/bin/python scripts/site/build_pages.py

Pages: frontend/examples/index.html (every example in the library, filterable, each with "Use this"), frontend/blog/index.html
and one folder per post in POSTS. Re-run after editing a post below or adding examples; vite.config.js lists every page.
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONT = ROOT / 'frontend'

HEAD = '''<!doctype html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/><meta name="theme-color" content="#FFF8EC"/>
<title>{title}</title><meta name="description" content="{description}"/>
<meta property="og:title" content="{title}"/><meta property="og:description" content="{description}"/><meta property="og:image" content="https://strokeberry.com/brand/og-image.png"/>
<link rel="canonical" href="https://strokeberry.com/{path}/"/><meta property="og:url" content="https://strokeberry.com/{path}/"/>
<link rel="icon" type="image/png" sizes="32x32" href="/brand/favicon-32.png"/><link rel="icon" type="image/png" sizes="192x192" href="/brand/strokeberry-192.png"/>
<link rel="stylesheet" href="/src/landing.css"/>{extra_head}</head><body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs><symbol id="arrow" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></symbol></defs></svg>
<header class="nav scrolled"><div class="wrap nav-inner"><a class="logo" href="/" aria-label="Strokeberry home"><img src="/brand/strokeberry-mascot.png" srcset="/brand/strokeberry-mascot@2x.png 2x" width="43" height="44" alt=""/>Strokeberry</a>
<nav class="nav-links" aria-label="Primary"><a href="/#gallery">Examples</a><a href="/#pricing">Pricing</a><a href="/examples/">Gallery</a><a href="/blog/">Blog</a></nav>
<a class="btn btn-primary btn-sm" href="/studio/">Try free</a></div></header>
'''
FOOT = '''<footer class="footer"><div class="wrap footer-inner"><a class="logo" href="/"><img src="/brand/strokeberry-mascot.png" srcset="/brand/strokeberry-mascot@2x.png 2x" width="35" height="36" alt=""/>Strokeberry</a>
<p>Your images. Drawn to life.</p><nav class="footer-links" aria-label="More"><a href="/examples/">Gallery</a><a href="/blog/">Blog</a><a href="/terms/">Terms</a><a href="/privacy/">Privacy</a><a href="/refunds/">Refunds</a><a class="footer-mail" href="mailto:hi@strokeberry.com">hi@strokeberry.com</a></nav>
<p class="copy">© 2026 Strokeberry</p></div></footer>
<script>
  // Clips load and play only while they are on screen; posters show straight away so nothing is ever blank.
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clips = document.querySelectorAll('video[data-src]');
  if ('IntersectionObserver' in window) {{
    const io = new IntersectionObserver(entries => entries.forEach(({{target: v, isIntersecting}}) => {{
      if (isIntersecting) {{ if (!v.src) v.src = v.dataset.src; if (!reduced) v.play().catch(() => {{}}); }} else v.pause();
    }}), {{threshold: .35}});
    clips.forEach(v => io.observe(v));
  }}
</script>{extra_body}
</body></html>
'''


def page(path, title, description, body, extra_head='', extra_body=''):
    out = FRONT / path / 'index.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(HEAD.format(title=html.escape(title), description=html.escape(description), extra_head=extra_head, path=path)
                   + body + FOOT.format(extra_body=extra_body))
    return f'{path}/index.html'


def clip(key, caption):
    return (f'<figure class="post-clip"><video muted loop playsinline preload="none" poster="/gallery/{key}.jpg" '
            f'data-src="/gallery/{key}.mp4" aria-label="{html.escape(caption)}"></video><figcaption>{caption}</figcaption></figure>')


CTA = ('<aside class="post-cta"><p><strong>Try it with your own picture.</strong> Upload an image and watch it being drawn: '
       'no sign-up to preview, 3 free videos every month.</p><a class="btn btn-primary" href="/studio/">Open the studio '
       '<svg width="18" height="18"><use href="#arrow"/></svg></a></aside>')

# Each post: slug, title, description, date, read time, body (HTML). Written for people about to make a video, not for
# search-engine filler: every one ends in the studio.
POSTS = [
    ('logo-reveal-video', 'How to make a logo reveal video for your business',
     'Turn your logo into a short hand-drawn reveal for Reels, TikTok, YouTube intros and launch posts, in about a minute.',
     '1 October 2026', 5, f'''
<p>A logo that draws itself is one of the simplest ways to make a brand post stop the scroll. Movement catches the eye, and watching the shapes come together keeps people looking until the name appears. You don’t need an animator or editing software: if you have your logo as an image, you can make the video in about a minute.</p>
<h2>What you need</h2>
<ul><li><strong>Your logo as a PNG or JPG.</strong> A version on a white or transparent background works best. The cleaner the outlines, the cleaner the drawing.</li>
<li><strong>An idea of where it will go.</strong> Square or 4:5 for an Instagram post, 9:16 for Reels, TikTok and Stories, 16:9 for a YouTube intro or a website header.</li></ul>
<h2>Step by step</h2>
<ol><li><strong>Upload the logo.</strong> Open the studio and drop the image in. It starts drawing straight away so you can see how it will look.</li>
<li><strong>Choose ink.</strong> Ink gives bold, confident lines that suit logos. Pencil feels softer and works for handmade or bakery-style brands.</li>
<li><strong>Pick the hand.</strong> A realistic hand drawing the lines and then painting the colour in feels personal. For a cleaner, more corporate look, choose no hand.</li>
<li><strong>Keep it short.</strong> Logo reveals work best at 6 to 12 seconds. Long enough to enjoy, short enough to loop.</li>
<li><strong>Choose the format and export.</strong> Download the MP4 and post it, or drop it into your editor as an intro.</li></ol>
{clip('sneaker', 'A product illustration drawn in ink, then painted in')}
<h2>Tips for a better logo reveal</h2>
<ul><li><strong>Outlines matter.</strong> Logos with clear dark outlines draw beautifully. If your logo is flat colour with no outlines, try “Improve my lines”: Strokeberry suggests the missing outlines and you choose whether to add them.</li>
<li><strong>Use your brand colours on the lines.</strong> With a brand kit (Pro) the pen draws in your own colour and your logo can sit in a corner of every export.</li>
<li><strong>Add sound where you post.</strong> Videos export silent so you can add a trending sound or your brand jingle in Instagram, TikTok or your editor.</li></ul>
<h2>Can I use it in ads?</h2>
<p>Yes, with Pro or a video pack: those exports have no watermark and can be used commercially. Free exports are for personal use and carry a small watermark and a short end card.</p>
{CTA}'''),
    ('drawing-tutorial-video', 'Turn a how-to-draw sheet into a video lesson',
     'Teachers and tutorial creators: turn a step-by-step drawing sheet into one video that builds the picture stage by stage.',
     '1 October 2026', 6, f'''
<p>Step-by-step drawing sheets are brilliant on paper: four or six small panels, each adding a little more. On video they are even better, because students can watch each stage appear and follow along at their own pace. Strokeberry’s tutorial mode turns a sheet like that into one continuous lesson video.</p>
{clip('owl', 'A four-step owl tutorial, from guide shapes to final colour')}
<h2>How tutorial mode works</h2>
<p>When you upload a sheet with several panels, Strokeberry finds the panels and offers to use them as steps. Each panel becomes a stage: the video draws the first stage, then adds only what is new in the next one, and so on until the final, coloured picture. The marks, shading and colours of each panel are kept, so the video looks like the sheet you started from.</p>
<h2>Step by step</h2>
<ol><li><strong>Upload the sheet.</strong> A clean scan or a digital sheet works best. If it’s a photo of paper, use the built-in cleanup to brighten the page.</li>
<li><strong>Check the steps.</strong> The step editor shows the panels it found, in reading order. Adjust a crop, change the order, or rename a step (“Body shape”, “Face”, “Colour”).</li>
<li><strong>Set the timing.</strong> Give harder steps more time. A four-step lesson usually works well at 30 to 60 seconds; longer lessons can run up to 5 minutes with Pro or a video pack.</li>
<li><strong>Export in the right shape.</strong> 16:9 for a classroom screen or YouTube, 9:16 for Shorts and Reels.</li></ol>
<h2>Classroom tips</h2>
<ul><li><strong>Pause between steps.</strong> The video holds each finished stage for a moment, so it’s easy to pause and let everyone catch up.</li>
<li><strong>Use a chalkboard canvas.</strong> The blackboard and greenboard canvases draw in chalk, which feels at home in a classroom.</li>
<li><strong>Make a series.</strong> One sheet per lesson adds up quickly. Pro’s 200 videos a month covers a full term of lessons.</li></ul>
{CTA}'''),
    ('cafe-instagram-drawing-videos', 'Drawing videos for your café’s Instagram',
     'Show your coffee, cakes and menu being drawn by hand: easy, scroll-stopping posts for cafés, bakeries and food brands.',
     '1 October 2026', 5, f'''
<p>Food posts are everywhere, and most of them look the same. A drawing of your signature drink or pastry being sketched and painted in by hand looks different: warm, crafted, and very “made here”. It’s an easy way to announce a new item, a seasonal menu or an opening-hours change.</p>
{clip('coffee', 'Café menu art: a coffee and croissant drawn and painted in')}
<h2>Ideas that work</h2>
<ul><li><strong>New on the menu.</strong> Draw the new item, then post the photo of the real thing next to it.</li>
<li><strong>Seasonal specials.</strong> A pumpkin latte in autumn, a berry tart in summer.</li>
<li><strong>Your logo or shop front.</strong> A short reveal for your profile highlights or the start of your Stories.</li>
<li><strong>Behind the counter.</strong> Draw your barista’s favourite drink and tag them.</li></ul>
<h2>How to make one</h2>
<ol><li><strong>Start from an illustration.</strong> A simple drawing of the item with clear outlines works far better than a photo. Commission one, draw it yourself, or start from one of the food examples in the gallery.</li>
<li><strong>Choose pencil or ink.</strong> Pencil feels cosy and hand-made; ink looks bold and modern.</li>
<li><strong>Use the 4:5 format for your feed</strong> and 9:16 for Reels and Stories.</li>
<li><strong>Keep it under 15 seconds</strong> and let the finished picture stay on screen for a beat before it loops.</li></ol>
<h2>What it costs</h2>
<p>You can make 3 videos a month for free. For a single campaign, a video pack (from $5, paid once) gives you watermark-free videos you can use commercially. If you post every week, Pro is the better deal at $10 a month for 200 videos.</p>
{CTA}'''),
    ('what-is-a-speed-drawing-video', 'What is a speed-drawing video?',
     'Speed-drawing (or speed paint) videos explained: what they are, why people love watching them, and how to make one from any image.',
     '1 October 2026', 4, f'''
<p>A speed-drawing video shows a picture being drawn from the first line to the last splash of colour, sped up so the whole thing takes seconds or minutes instead of hours. Artists have shared them for years as “speed paints” and time-lapses, and they remain some of the most-watched art content on YouTube, TikTok and Instagram.</p>
<h2>Why they work</h2>
<ul><li><strong>Curiosity.</strong> From the first line, viewers want to know what it will become, so they keep watching.</li>
<li><strong>Satisfaction.</strong> Watching order emerge from a blank page is calming. Many people watch drawing videos to relax.</li>
<li><strong>They show skill and care.</strong> For a brand or a teacher, a drawing says “this was made by people”.</li></ul>
{clip('cat', 'A cat drawn in pencil, then painted in')}
<h2>Three ways to make one</h2>
<ol><li><strong>Record yourself drawing.</strong> The traditional way: set up a camera or screen recorder, draw, then speed up the footage. Beautiful, but it takes hours and needs drawing skill.</li>
<li><strong>Use a generic “sketch effect”.</strong> Many apps turn a picture into a pencil-sketch filter and wipe it on. Quick, but it rarely looks like real drawing.</li>
<li><strong>Use a drawing engine like Strokeberry.</strong> It finds the actual lines in your image and draws them the way a person would: big shapes first, then details, then the dark areas, then the colour painted in. You choose the style, the hand and the length.</li></ol>
<h2>What makes a good one</h2>
<ul><li><strong>Clear outlines.</strong> Illustrations, logos and drawing tutorials draw best.</li>
<li><strong>The right length.</strong> 8 to 20 seconds for social media; up to a few minutes for a relaxing full piece or a lesson.</li>
<li><strong>A moment at the end.</strong> Let the finished picture breathe before the video loops.</li></ul>
{CTA}'''),
]


def build_examples():
    library = json.loads((FRONT / 'public' / 'library' / 'library.json').read_text())
    made = [('skincare', 'Skincare set', 'For e-commerce'), ('fashion', 'Handbag & heels', 'For fashion brands'),
            ('creator', 'Creator setup', 'For YouTubers & creators'), ('cafe', 'Café badge', 'For cafés & food brands'),
            ('lesson', 'Reading rocket', 'For teachers'), ('house', 'Family home', 'For real estate'),
            ('strawberry', 'How to draw a strawberry', 'Tutorial · 4 steps'), ('owl', 'How to draw an owl', 'Tutorial · 4 steps'),
            ('cat', 'Curled-up cat', 'Pencil · hand'), ('sneaker', 'Product sketch', 'Ink · hand'), ('coffee', 'Coffee & croissant', 'Ink'),
            ('wreath', 'Floral wreath', 'Pencil'), ('balloon', 'Hot-air balloon', 'Ink · hand'),
            ('puppy', 'Happy puppy', 'Ink · hand'), ('fox', 'Chalkboard fox', 'Greenboard')]
    clips = ''.join(f'<figure class="ex-clip"><video muted loop playsinline preload="none" poster="/gallery/{k}.jpg" data-src="/gallery/{k}.mp4" '
                    f'aria-label="{html.escape(t)}"></video><figcaption><strong>{html.escape(t)}</strong><span>{s}</span></figcaption></figure>'
                    for k, t, s in made)
    chips = '<button class="chip on" data-cat="all">All</button>' + ''.join(
        f'<button class="chip" data-cat="{c["id"]}">{html.escape(c["name"])}</button>' for c in library['categories'])
    cards = ''.join(
        f'<a class="ex-card" data-cat="{i["category"]}" href="/studio/?example={i["id"]}"><img src="/library/{i["thumb"]}" alt="" loading="lazy" width="360" height="360"/>'
        f'<span><strong>{html.escape(i["title"])}</strong><em>{"Tutorial" if i["tutorial"] else "Use this"} →</em></span></a>'
        for i in library['items'])
    body = f'''<main class="wrap ex-page">
<header class="ex-head"><p class="eyebrow">Gallery</p><h1>Watch it draw. Then make your own.</h1>
<p class="section-sub">Real exports from Strokeberry, and {len(library['items'])} ready-to-use pictures. Pick one and it opens in the studio, already drawing: no sign-up to preview.</p></header>
<section><h2 class="ex-title">Made in Strokeberry</h2><div class="ex-clips">{clips}</div></section>
<section><h2 class="ex-title">Start from an example</h2><div class="chips" role="tablist" aria-label="Categories">{chips}</div><div class="ex-grid">{cards}</div></section>
</main>'''
    script = '''<script>
  document.querySelector('.chips').addEventListener('click', e => {
    const chip = e.target.closest('.chip'); if (!chip) return;
    document.querySelectorAll('.chip').forEach(c => c.classList.toggle('on', c === chip));
    document.querySelectorAll('.ex-card').forEach(card => card.hidden = chip.dataset.cat !== 'all' && card.dataset.cat !== chip.dataset.cat);
  });
</script>'''
    return page('examples', 'Gallery · Strokeberry', 'Hand-drawn videos made with Strokeberry, and ready-to-use pictures for animals, food, occasions, logos and drawing tutorials.', body, extra_body=script)


def build_blog():
    written = []
    for slug, title, description, date, minutes, content in POSTS:
        body = (f'<main class="doc post"><p class="doc-meta"><a href="/blog/">Blog</a> · {date} · {minutes} min read</p>'
                f'<h1>{html.escape(title)}</h1><p class="post-lede">{html.escape(description)}</p>{content}</main>')
        ld = json.dumps({'@context': 'https://schema.org', '@type': 'BlogPosting', 'headline': title, 'description': description,
                         'datePublished': '2026-10-01', 'author': {'@type': 'Organization', 'name': 'Strokeberry'}})
        written.append(page(f'blog/{slug}', f'{title} · Strokeberry', description, body,
                            extra_head=f'<script type="application/ld+json">{ld}</script>'))
    cards = ''.join(f'<a class="blog-card" href="/blog/{slug}/"><span class="doc-meta">{date} · {minutes} min read</span>'
                    f'<strong>{html.escape(title)}</strong><p>{html.escape(description)}</p><em>Read →</em></a>'
                    for slug, title, description, date, minutes, _ in POSTS)
    body = f'''<main class="wrap ex-page"><header class="ex-head"><p class="eyebrow">Blog</p><h1>Ideas for hand-drawn videos</h1>
<p class="section-sub">Practical guides for small businesses, teachers and creators.</p></header><div class="blog-grid">{cards}</div></main>'''
    written.append(page('blog', 'Blog · Strokeberry', 'Guides to making hand-drawn videos for your business, your classroom and your social media.', body))
    return written


def build_sitemap(pages):
    """public/sitemap.xml and robots.txt: every public page (the studio included; the API and private media excluded)."""
    urls = ['/', '/studio/', '/terms/', '/privacy/', '/refunds/'] + ['/' + p.rsplit('/index.html', 1)[0] + '/' for p in pages]
    entries = ''.join(f'<url><loc>https://strokeberry.com{u}</loc></url>' for u in dict.fromkeys(urls))
    (FRONT / 'public' / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                                  f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</urlset>\n')
    (FRONT / 'public' / 'robots.txt').write_text('User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /media/\n\n'
                                                 'Sitemap: https://strokeberry.com/sitemap.xml\n')


if __name__ == '__main__':
    pages = [build_examples()] + build_blog()
    build_sitemap(pages)
    print('\n'.join(pages + ['public/sitemap.xml', 'public/robots.txt']))
