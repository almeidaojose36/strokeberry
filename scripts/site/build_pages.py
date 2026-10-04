"""Write the public gallery page and the blog (static HTML, built by Vite like the rest of the site).

    .venv/bin/python scripts/site/build_pages.py

Pages: frontend/examples/index.html (every example in the library, filterable, each with "Use this"), frontend/blog/index.html,
one folder per post in POSTS, and the comparison and use-case guides in GUIDES (compare/… and for/…).
Re-run after editing a post below or adding examples; vite.config.js builds every index.html it finds.
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONT = ROOT / 'frontend'
GALLERY_VERSION = 'sports3'  # bump when the gallery clips are re-rendered, so Cloudflare's cache serves the new files

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
<p>Your images. Drawn to life.</p><nav class="footer-guides" aria-label="Guides"><a href="/for/teachers/">For teachers</a><a href="/for/ecommerce/">For online shops</a><a href="/for/real-estate/">For real estate</a><a href="/for/interiors/">For interior designers</a><a href="/for/creators/">For creators</a><a href="/compare/videoscribe-alternative/">VideoScribe alternative</a><a href="/compare/doodly-alternative/">Doodly alternative</a><a href="/compare/speedpainter-alternative/">SpeedPainter alternative</a></nav>
<nav class="footer-links" aria-label="More"><a href="/examples/">Gallery</a><a href="/blog/">Blog</a><a href="/terms/">Terms</a><a href="/privacy/">Privacy</a><a href="/refunds/">Refunds</a><a class="footer-mail" href="mailto:hi@strokeberry.com">hi@strokeberry.com</a></nav>
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
    return (f'<figure class="post-clip"><video muted loop playsinline preload="none" poster="/gallery/{key}.jpg?v={GALLERY_VERSION}" '
            f'data-src="/gallery/{key}.mp4?v={GALLERY_VERSION}" aria-label="{html.escape(caption)}"></video><figcaption>{caption}</figcaption></figure>')


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


def table(head, rows):
    """A comparison table; the Strokeberry column (the first after the label) is highlighted."""
    pro = ' class="c-pro"'
    th = ''.join(f'<th scope="col"{pro if i == 1 else ""}>{h}</th>' for i, h in enumerate(head))
    body = ''.join('<tr><th scope="row">' + r[0] + '</th>' + ''.join(
        f'<td{pro if i == 0 else ""}>{c}</td>' for i, c in enumerate(r[1:])) + '</tr>' for r in rows)
    return f'<div class="compare guide-table"><div class="compare-scroll"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div></div>'


CHECKED = '3 October 2026'
OUR_PRICE = ('Free: 3 videos a month<br/>Pro: $10 a month (or $84 a year), 200 videos<br/>'
             'Packs: 5 videos $5, 15 for $12, 40 for $25, paid once')
GUIDE_CTA = ('<aside class="post-cta"><p><strong>See your own picture drawn.</strong> Drop an image in the studio and it starts drawing '
             'straight away. No sign-up to preview, 3 free videos every month.</p><a class="btn btn-primary" href="/studio/">Try it free '
             '<svg width="18" height="18"><use href="#arrow"/></svg></a></aside>')
FAIR = (f'<p class="guide-note">Competitor details are taken from their own websites on {CHECKED} and may have changed since. '
        'Spotted something out of date? Email <a href="mailto:hi@strokeberry.com">hi@strokeberry.com</a> and we’ll fix it.</p>')

# Each guide: path, kind ('compare' or 'for'), card title, page title, description, body (HTML).
GUIDES = [
    ('compare/videoscribe-alternative', 'compare', 'Strokeberry vs VideoScribe',
     'A simpler VideoScribe alternative for drawing videos',
     'VideoScribe builds whiteboard explainers scene by scene. Strokeberry draws your own image in a minute. Here is how they compare, and when each one is the better pick.',
     f'''
<p>VideoScribe is a well-known whiteboard animation tool: you build an explainer scene by scene from its image library, add text, a voiceover and music, and it draws each element in turn. Strokeberry does one thing instead: you give it <em>your</em> picture, and it draws that picture the way a person would, lines first, then the colour painted in.</p>
<p>If you are making a 5-minute narrated explainer, VideoScribe is built for that. If you want a logo, a product, a lesson sheet or an illustration drawn for Reels, TikTok, Shorts or a website, Strokeberry gets you there much faster.</p>
{clip('balloon', 'Made in Strokeberry: a hot-air balloon drawn in ink, then painted in')}
<h2>At a glance</h2>
{table(['', 'Strokeberry', 'VideoScribe'], [
    ['What you start from', 'Your own image (logo, product, drawing, lesson sheet)', 'A blank canvas and its image library, scene by scene'],
    ['Time to a first video', 'About a minute: upload, pick a style, export', 'Longer: you place, time and arrange each element'],
    ['How it draws', 'Finds the real lines in your picture, draws them in order, then paints the colour in', 'Draws each placed image along its outline, with a choice of hands'],
    ['Runs in', 'Your browser', 'Browser or desktop app'],
    ['Voiceover and music', 'No: videos export silent, so you add a sound where you post', 'Yes: voiceover recording, AI voices and a music library'],
    ['Formats', '16:9, 9:16, 1:1, 4:5 or fit to the image', 'Landscape, portrait or square'],
    ['Longest video', '1 minute free, 5 minutes with Pro or a pack', '5 to 20 minutes depending on plan'],
    ['Free option', '3 videos every month, no card, no time limit', '7-day trial, 3 downloads, watermarked'],
    ['Price', OUR_PRICE, 'Lite $104.65 a year (5 downloads a month), Core $178.25 a year (30 a month, no watermark), Max $224.25 a year (unlimited)'],
])}
<h2>Where Strokeberry is the better fit</h2>
<ul><li><strong>You already have the picture.</strong> A logo, a product illustration, a drawing your students know, a floor plan. Strokeberry animates that exact image instead of asking you to rebuild it from library pieces.</li>
<li><strong>Short social videos.</strong> 8 to 20 seconds in 9:16 or 4:5 is where drawing videos stop the scroll, and that’s what Strokeberry is designed around.</li>
<li><strong>Volume on a small budget.</strong> Pro is $10 a month for 200 videos without a watermark. For a single campaign, a pack of 5 videos is $5, paid once.</li>
<li><strong>Step-by-step lessons.</strong> Upload a how-to-draw sheet and tutorial mode turns its panels into one lesson video that builds stage by stage.</li></ul>
<h2>Where VideoScribe is the better fit</h2>
<ul><li><strong>Narrated explainers.</strong> If the video is a story told over several scenes with a voiceover and music, VideoScribe’s scene editor is made for that.</li>
<li><strong>No image to start from.</strong> Its library has millions of images and icons to build with.</li>
<li><strong>Long videos.</strong> Its higher plans allow 10 to 20 minutes.</li></ul>
<h2>Can I use both?</h2>
<p>Yes, and many people do: draw a logo or a product in Strokeberry and use the MP4 as the intro or a scene inside a longer edit.</p>
{FAIR}{GUIDE_CTA}'''),

    ('compare/doodly-alternative', 'compare', 'Strokeberry vs Doodly',
     'A browser-based Doodly alternative for your own images',
     'Doodly is a desktop doodle-video app built around its own drawings. Strokeberry runs in your browser and draws any image you upload. A fair comparison.',
     f'''
<p>Doodly is a desktop app for Mac and PC for making doodle videos: you drag its hand-drawn characters and scenes onto a whiteboard, blackboard or glassboard and it draws them in. You can import your own images too, and set their draw paths by pointing and clicking.</p>
<p>Strokeberry starts from your own image every time and works out the drawing for you: it finds the lines, draws them in a natural order with a realistic hand, then paints the colour in. Nothing to install, nothing to trace by hand.</p>
{clip('fox', 'Made in Strokeberry: a fox drawn in chalk on the greenboard canvas')}
<h2>At a glance</h2>
{table(['', 'Strokeberry', 'Doodly'], [
    ['What you start from', 'Your own image', 'Its library of doodle characters and scenes, or your imported images'],
    ['Drawing your own image', 'Automatic: the lines and the order are worked out for you', 'Smart Draw: you set the draw path by pointing and clicking'],
    ['Runs in', 'Your browser, on any computer', 'Desktop app for Mac and PC'],
    ['Boards', 'Paper, blackboard and greenboard (chalk)', 'Whiteboard, blackboard, glassboard and green screen'],
    ['Hands', 'Realistic hands in three skin tones, with an ink pen or a pencil for the lines and a brush for the colour, or no hand', 'Many male and female hands in different skin tones'],
    ['Voiceover', 'No: export silent and add sound where you post', 'Yes: record or import a voiceover'],
    ['Formats', '16:9, 9:16, 1:1, 4:5 or fit to the image', 'See Doodly’s site'],
    ['Free option', '3 videos every month, no card, no time limit', '14-day free trial'],
    ['Price', OUR_PRICE, 'Included in Voomly Cloud; see their site for current pricing'],
])}
<h2>Where Strokeberry is the better fit</h2>
<ul><li><strong>You want your own artwork drawn, not stock doodles.</strong> Your logo, your product, your illustration, your lesson sheet.</li>
<li><strong>You don’t want to trace draw paths.</strong> Strokeberry decides the order: big shapes first, then details, then the colour.</li>
<li><strong>You work on more than one computer</strong>, or on one where you can’t install software, like a school laptop.</li>
<li><strong>Vertical social video.</strong> 9:16 and 4:5 are one click away.</li></ul>
<h2>Where Doodly is the better fit</h2>
<ul><li><strong>Character-led explainers</strong> built from a ready-made cast of doodle people and scenes.</li>
<li><strong>Voiceover inside the app.</strong></li>
<li><strong>Glassboard and green-screen styles.</strong></li></ul>
{FAIR}{GUIDE_CTA}'''),

    ('compare/speedpainter-alternative', 'compare', 'Strokeberry vs SpeedPainter',
     'SpeedPainter alternative: drawing videos without credits',
     'SpeedPainter and Strokeberry both turn an image into a hand-drawn video. The big difference is how you pay: credits per second, or a simple number of videos.',
     f'''
<p>SpeedPainter and Strokeberry do a similar job: upload an image and get a video of it being drawn by hand. Both have realistic hands, several canvases and the usual social formats. The clearest difference is pricing.</p>
<p>SpeedPainter sells <strong>credits</strong>, spent per second of video: their own pricing page says 700 credits make about 116 six-second videos. Longer videos use more credits, so the number of videos you get depends on how long they are. Strokeberry counts <strong>videos</strong>: a 10-second clip and a 5-minute lesson each use one.</p>
{clip('strawberry', 'Made in Strokeberry: a four-step strawberry lesson, built stage by stage')}
<h2>At a glance</h2>
{table(['', 'Strokeberry', 'SpeedPainter'], [
    ['How you pay', 'Per video, whatever its length', 'Credits, spent per second of video'],
    ['Entry plan', '$10 a month: 200 videos up to 5 minutes each, no watermark', 'Starter $19.90 a month: 700 credits (about 116 six-second videos)'],
    ['Yearly', '$84 a year ($7 a month)', 'Starter $199, Plus $399, Ultra $599 a year'],
    ['Pay once', 'Video packs: 5 for $5, 15 for $12, 40 for $25. Never expire', 'Credit top-ups from $29.90 for 1000 credits'],
    ['Free option', '3 videos every month, no card', 'See their site'],
    ['Highest quality', '4K with Pro, 1080p on Free and packs', '4K on paid plans'],
    ['Step-by-step lessons', 'Tutorial mode turns a how-to-draw sheet into one lesson video', 'See their site'],
    ['Formats', '16:9, 9:16, 1:1, 4:5 or fit to the image', 'Several sizes'],
])}
<h2>What a minute of video costs</h2>
<p>Using SpeedPainter’s own figure (700 credits for about 116 six-second videos, so roughly one credit per second), the Starter plan covers about 11 minutes of video a month. Strokeberry Pro at $10 covers 200 videos of up to 5 minutes each. If you make longer videos, like drawing lessons, relaxing full pieces or YouTube intros, counting videos instead of seconds makes a big difference.</p>
<h2>Where Strokeberry is the better fit</h2>
<ul><li><strong>Longer videos</strong>: lessons and full speed paints cost the same as a 6-second clip.</li>
<li><strong>Teachers</strong>: tutorial mode for step-by-step sheets, and chalkboard canvases.</li>
<li><strong>Predictable spending</strong>: you always know how many videos you have left.</li></ul>
<h2>Where SpeedPainter may suit you better</h2>
<ul><li><strong>Lots of very short clips in 4K</strong> on a paid plan.</li>
<li><strong>Effects we don’t offer.</strong> Have a look at both and pick the look you like.</li></ul>
{FAIR}{GUIDE_CTA}'''),

    ('for/teachers', 'for', 'For teachers',
     'Drawing videos for teachers and classrooms',
     'Turn a how-to-draw sheet, a diagram or a story illustration into a video your class can follow, step by step. Chalkboard canvases included.',
     f'''
<p>Children (and adults) learn a drawing faster when they watch it being built: first the guide shapes, then the details, then the colour. Strokeberry turns the pictures you already use in class into videos that do exactly that.</p>
{clip('lesson', 'A reading-corner illustration drawn and painted in')}
<h2>Three ways teachers use it</h2>
<ul><li><strong>How-to-draw lessons.</strong> Upload a step-by-step sheet. Tutorial mode finds the panels and turns them into one video that adds each step in turn, holding each stage so the class can catch up.</li>
<li><strong>Explaining a diagram.</strong> A water cycle, a plant cell or a map is easier to follow when it appears piece by piece.</li>
<li><strong>Story time.</strong> Draw the illustration for today’s story as the class settles down.</li></ul>
{clip('owl', 'Tutorial mode: a four-step owl lesson')}
<h2>Made for the classroom</h2>
<ul><li><strong>Chalkboard canvases.</strong> Blackboard and greenboard draw in chalk.</li>
<li><strong>Works on a school laptop.</strong> It runs in the browser: nothing to install.</li>
<li><strong>Classroom screen or phone.</strong> 16:9 for the projector or YouTube, 9:16 for Shorts and Reels.</li>
<li><strong>Lessons up to 5 minutes</strong> with Pro or a video pack. Pro’s 200 videos a month covers a whole term.</li></ul>
<h2>What it costs</h2>
<p>3 videos a month are free. Pro is $10 a month for 200 videos without a watermark. Or buy a pack once, from 5 videos for $5, and use them whenever you like.</p>
{GUIDE_CTA}'''),

    ('for/ecommerce', 'for', 'For online shops',
     'Product drawing videos for online shops and e-commerce',
     'Turn a product illustration into a short hand-drawn video for ads, product pages, Reels and TikTok. A scroll-stopper that looks crafted, not templated.',
     f'''
<p>Most product videos look the same: a spinning packshot and a sliding caption. A product being sketched and painted in by hand looks different, and different is what stops the scroll. It says “designed with care”, which is exactly what a small brand wants to say.</p>
{clip('skincare', 'A skincare set drawn and painted in')}
<h2>Ideas that work</h2>
<ul><li><strong>Launch teasers.</strong> Draw the new product before you show the photo.</li>
<li><strong>Product page hero.</strong> A 6 to 10 second loop above the fold.</li>
<li><strong>Ads.</strong> Hand-drawn openers make a fresh first second for Meta and TikTok ads.</li>
<li><strong>Bundles and gift sets.</strong> Draw the set coming together.</li></ul>
{clip('fashion', 'A handbag and heels, sketched then coloured')}
<h2>How to make one</h2>
<ol><li><strong>Start from an illustration of the product</strong>, ideally with clear outlines. A flat-colour image works too: “Improve my lines” suggests outlines you can accept or skip.</li>
<li><strong>Pick ink</strong> for a bold, modern look, or pencil for a handmade feel.</li>
<li><strong>Export 9:16</strong> for Reels, TikTok and Stories, 4:5 for the feed, 1:1 for marketplaces.</li>
<li><strong>Add your brand kit</strong> (Pro) so the pen draws in your colour and your logo sits in a corner.</li></ol>
<h2>Commercial use</h2>
<p>Videos made with Pro or a video pack have no watermark and can be used in ads and on your store. Free videos are for personal use.</p>
{GUIDE_CTA}'''),

    ('for/real-estate', 'for', 'For real estate',
     'Hand-drawn property videos for real estate agents',
     'Turn a property sketch, a floor plan or a listing illustration into a hand-drawn video for listings, Reels and “Just listed” posts.',
     f'''
<p>Every listing has the same photos and the same slideshow. A home being sketched and painted in by hand is a small surprise in the feed, and it makes a “Just listed” or “Sold” post feel personal.</p>
{clip('house', 'A family home sketched and painted in')}
<h2>Ideas that work</h2>
<ul><li><strong>Just listed.</strong> Draw the house, then cut to the real photo.</li>
<li><strong>Floor plans.</strong> The walls go up first, room by room, then the furniture and colours appear. Easier to read than a static plan.</li>
<li><strong>Sold and thank-you posts</strong> for the buyers, with their new home drawn.</li>
<li><strong>Your agency logo</strong> as a short intro for every video.</li></ul>
{clip('floorplan', 'A two-bedroom floor plan: walls first, then the rooms come to life')}
<h2>How to make one</h2>
<ol><li><strong>Start from a sketch or illustration of the property.</strong> Line drawings and architectural sketches draw beautifully. A photo doesn’t draw well: turn it into an illustration first.</li>
<li><strong>Pick pencil</strong> for an architect’s-sketch feel, or ink for a bolder look.</li>
<li><strong>Export 9:16</strong> for Reels and Stories, 4:5 for the feed, 16:9 for YouTube and your website.</li></ol>
<h2>What it costs</h2>
<p>Try 3 videos a month free. For one listing campaign, a pack of 5 videos is $5, paid once, with no watermark. If you post every week, Pro is $10 a month for 200 videos.</p>
{GUIDE_CTA}'''),

    ('for/interiors', 'for', 'For interiors & furniture',
     'Drawing videos for interior designers and furniture brands',
     'Turn a room sketch, a furniture illustration or a floor plan into a hand-drawn video for Instagram, Pinterest, TikTok and your website.',
     f'''
<p>Interior design sells a feeling before it sells a product, and watching a room come together line by line is a feeling people stop for. Strokeberry draws your room or furniture illustration the way a designer would sketch it, then paints the colours and materials in.</p>
{clip('livingroom', 'A Scandinavian living room, sketched and painted in')}
<h2>Ideas that work</h2>
<ul><li><strong>Mood boards that move.</strong> Show a client’s room concept being sketched before the reveal.</li>
<li><strong>Furniture launches.</strong> A new chair or sofa drawn in a few seconds makes a striking product post or ad.</li>
<li><strong>Before and after.</strong> Draw the plan for a room, then cut to the photo of the finished space.</li>
<li><strong>Floor plans.</strong> The walls go up room by room, then the home appears in colour.</li></ul>
{clip('armchair', 'A lounge armchair, drawn then painted in mustard')}
<h2>How to make one</h2>
<ol><li><strong>Start from an illustration or sketch</strong> of the room or the piece, with clear outlines. Photos of real rooms don’t draw well: turn them into an illustration first.</li>
<li><strong>Pick ink</strong> for crisp, architectural lines, or pencil for a softer concept-sketch feel.</li>
<li><strong>Choose the format:</strong> 9:16 for Reels, TikTok and Pinterest, 4:5 for the Instagram feed, 16:9 for your website or YouTube.</li>
<li><strong>Add your brand kit</strong> (Pro) so the pen draws in your colour and your logo sits in a corner.</li></ol>
{clip('kitchen', 'A sage-green kitchen drawn line by line')}
<h2>What it costs</h2>
<p>3 videos a month are free. For a single launch, a pack of 5 videos is $5, paid once, with no watermark and commercial use included. If you post every week, Pro is $10 a month for 200 videos.</p>
{GUIDE_CTA}'''),

    ('for/creators', 'for', 'For YouTubers and creators',
     'Speed-drawing videos for YouTubers and content creators',
     'Intros, channel art reveals, thumbnails that draw themselves and relaxing speed paints: hand-drawn videos for YouTube, TikTok and Reels.',
     f'''
<p>Drawing videos are some of the most-watched art content online: from the first line, people want to see what it becomes. You don’t need to be an artist to use that hook. Give Strokeberry an illustration and it draws it the way a person would.</p>
{clip('creator', 'A creator’s desk setup sketched and painted in')}
<h2>Ideas that work</h2>
<ul><li><strong>Channel intro.</strong> Your logo or mascot drawn in 6 seconds.</li>
<li><strong>Reveal your new channel art</strong> or merch design.</li>
<li><strong>Faceless channels.</strong> Facts, stories and history explained over illustrations that draw themselves.</li>
<li><strong>Relaxing speed paints.</strong> Full pieces up to 5 minutes long.</li></ul>
<h2>How to make one</h2>
<ol><li><strong>Start from an illustration</strong> with clear outlines.</li>
<li><strong>Pick the hand:</strong> a realistic hand with an ink pen and a brush, or no hand for a clean look.</li>
<li><strong>Export 9:16</strong> for Shorts, TikTok and Reels, or 16:9 for YouTube. 4K with Pro.</li>
<li><strong>Add music where you post.</strong> Videos export silent so you can use a trending sound.</li></ol>
<h2>What it costs</h2>
<p>3 videos a month are free. Pro is $10 a month for 200 videos up to 5 minutes long, in up to 4K, with no watermark, and you can use them commercially.</p>
{GUIDE_CTA}'''),
]


def build_guides():
    written = []
    for path, kind, card, title, description, content in GUIDES:
        crumb = '<a href="/blog/">Guides</a> · ' + ('Comparison' if kind == 'compare' else 'Use case')
        body = (f'<main class="doc post guide"><p class="doc-meta">{crumb}</p>'
                f'<h1>{html.escape(title)}</h1><p class="post-lede">{html.escape(description)}</p>{content}</main>')
        ld = json.dumps({'@context': 'https://schema.org', '@type': 'Article', 'headline': title, 'description': description,
                         'dateModified': '2026-10-03', 'author': {'@type': 'Organization', 'name': 'Strokeberry'}})
        written.append(page(path, f'{title} · Strokeberry', description, body,
                            extra_head=f'<script type="application/ld+json">{ld}</script>'))
    return written


def lead_clip(content):
    """The gallery clip a page opens with, used as its card's moving thumbnail."""
    return re.search(r'/gallery/([a-z0-9-]+)\.jpg', content).group(1)


def card(href, key, tag, title, description, badge='', featured=False):
    """A blog-page card. The featured card plays its drawing while on screen (see FOOT); the others show the finished
    picture and play the drawing only on hover (BLOG_HOVER), so the page isn't a wall of moving video."""
    media = (f'<video muted loop playsinline preload="none" poster="/gallery/{key}.jpg?v={GALLERY_VERSION}" data-src="/gallery/{key}.mp4?v={GALLERY_VERSION}" aria-hidden="true"></video>'
             if featured else
             f'<img src="/gallery/{key}.jpg?v={GALLERY_VERSION}" alt="" loading="lazy" width="720" height="720"/>'
             f'<video muted loop playsinline preload="none" data-hover="/gallery/{key}.mp4?v={GALLERY_VERSION}" aria-hidden="true"></video>'
             '<span class="bcard-play"><svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 1l7 4-7 4z" fill="currentColor"/></svg>Watch it draw</span>')
    return (f'<a class="bcard{" bcard-featured" if featured else ""}" href="{href}"><span class="bcard-media">{media}'
            f'{f"<span class=bcard-badge>{badge}</span>" if badge else ""}</span>'
            f'<span class="bcard-body"><span class="bcard-tag">{tag}</span><strong>{html.escape(title)}</strong>'
            f'<span class="bcard-text">{html.escape(description)}</span><em>{"Read the guide" if featured else "Read"} '
            f'<svg width="16" height="16"><use href="#arrow"/></svg></em></span></a>')


def guide_cards(kind):
    return ''.join(card(f'/{path}/', lead_clip(content), 'Comparison' if k == 'compare' else 'Use case', name, description,
                        badge=('vs ' + name.split(' vs ')[1]) if k == 'compare' else '')
                   for path, k, name, _, description, content in GUIDES if k == kind)


# The gallery's videos, grouped by who they are for: (id, chip name, [(clip key, title, how it was made, library example)]).
MADE = [
    ('shops', 'Shops & products', [('skincare', 'Skincare set', 'Ink · pen & brush', None), ('fashion', 'Handbag & heels', 'Ink · pen & brush', None),
                                   ('sneaker', 'Product sketch', 'Ink · pen & brush', 'objects-00-sneaker')]),
    ('home', 'Home & interiors', [('livingroom', 'Living room', 'Ink · pen & brush', 'home-01-living-room'),
                                  ('armchair', 'Lounge armchair', 'Ink · pen & brush', 'home-02-armchair'),
                                  ('kitchen', 'Kitchen', 'Ink · pen & brush', 'home-03-kitchen'),
                                  ('house', 'Family home', 'Ink · pen & brush', None),
                                  ('floorplan', 'Floor plan', 'Ink · walls first', 'home-04-floor-plan')]),
    ('sports', 'Sports & clubs', [('striker', 'Striker', 'Ink · pen & brush', 'sports-01-striker'),
                                  ('keeper', 'Goalkeeper', 'Ink · pen & brush', 'sports-02-goalkeeper'),
                                  ('sprinter', 'Sprinter', 'Ink · pen & brush', 'sports-03-sprinter'),
                                  ('dunk', 'Basketball dunk', 'Ink · pen & brush', 'sports-05-dunk'),
                                  ('fan', 'Fan with flag', 'Ink · pen & brush', 'sports-08-fan')]),
    ('food', 'Cafés & food', [('cafe', 'Café badge', 'Ink · pen & brush', None), ('coffee', 'Coffee & croissant', 'Ink', 'food-00-coffee')]),
    ('learning', 'Teachers & lessons', [('strawberry', 'How to draw a strawberry', 'Tutorial · 4 steps', None),
                                        ('owl', 'How to draw an owl', 'Tutorial · 4 steps', 'tutorial-00-owl'),
                                        ('lesson', 'Reading rocket', 'Ink · pen & brush', None),
                                        ('fox', 'Chalkboard fox', 'Greenboard · chalk', 'animals-01-fox')]),
    ('creators', 'Creators', [('creator', 'Creator setup', 'Ink · pen & brush', None), ('balloon', 'Hot-air balloon', 'Ink · pen & brush', 'travel-02-hot-air-balloon')]),
    ('fun', 'Pets & occasions', [('puppy', 'Happy puppy', 'Ink · pen & brush', 'animals-04-puppy'), ('cat', 'Curled-up cat', 'Pencil · hand', 'animals-00-cat'),
                                 ('wreath', 'Floral wreath', 'Pencil', 'occasion-00-wreath')]),
]


def chips(groups, label):
    return (f'<div class="chips" role="tablist" aria-label="{label}"><button class="chip on" data-cat="all">All</button>'
            + ''.join(f'<button class="chip" data-cat="{cat}">{html.escape(name)}</button>' for cat, name in groups) + '</div>')


EXAMPLES_SHOWN = 18  # three rows of six before "See all"
# The order categories take turns in, so the first rows mix businesses, food and fun instead of a block of animals.
MIX = ['home', 'sports', 'food', 'logo', 'animals', 'objects', 'occasion', 'tutorial', 'nature', 'travel']


def mixed(items):
    """Interleave the library by category (one from each in turn), keeping each category's own order."""
    queues = {}
    for item in items:
        queues.setdefault(item['category'], []).append(item)
    order = [c for c in MIX if c in queues] + [c for c in queues if c not in MIX]
    out = []
    while any(queues.values()):
        out += [queues[c].pop(0) for c in order if queues[c]]
    return out


def build_examples():
    library = json.loads((FRONT / 'public' / 'library' / 'library.json').read_text())
    clips = ''.join(
        f'<figure class="ex-clip" data-cat="{cat}"><video muted loop playsinline preload="none" poster="/gallery/{k}.jpg?v={GALLERY_VERSION}" '
        f'data-src="/gallery/{k}.mp4?v={GALLERY_VERSION}" aria-label="{html.escape(t)}"></video><figcaption><strong>{html.escape(t)}</strong>'
        + (f'<a href="/studio/?example={example}">Use this →</a>' if example else f'<span>{how}</span>') + '</figcaption></figure>'
        for cat, _, items in MADE for k, t, how, example in items)
    cards = ''.join(
        f'<a class="ex-card{" ex-extra" if n >= EXAMPLES_SHOWN else ""}" data-cat="{i["category"]}" href="/studio/?example={i["id"]}"{" hidden" if n >= EXAMPLES_SHOWN else ""}>'
        f'<img src="/library/{i["thumb"]}" alt="" loading="lazy" width="360" height="360"/>'
        f'<span><strong>{html.escape(i["title"])}</strong><em>{"Tutorial" if i["tutorial"] else "Use this"} →</em></span></a>'
        for n, i in enumerate(mixed(library['items'])))
    more = (f'<button class="btn btn-quiet ex-more" type="button">See all {len(library["items"])} pictures</button>'
            if len(library['items']) > EXAMPLES_SHOWN else '')
    videos = sum(len(items) for _, _, items in MADE)
    body = f'''<main class="wrap ex-page">
<header class="ex-head"><p class="eyebrow">Gallery</p><h1>Watch it draw. Then make your own.</h1>
<p class="section-sub">{videos} real exports from Strokeberry, and {len(library['items'])} ready-to-use pictures. Pick one and it opens in the studio, already drawing: no sign-up to preview.</p></header>
<section class="ex-filter"><h2 class="ex-title">Made in Strokeberry</h2>{chips([(c, n) for c, n, _ in MADE], 'Video categories')}<div class="ex-clips">{clips}</div></section>
<section class="ex-filter"><h2 class="ex-title">Start from an example</h2>{chips([(c['id'], c['name']) for c in library['categories']], 'Example categories')}<div class="ex-grid">{cards}</div>{more}</section>
</main>'''
    script = '''<script>
  // Each section filters its own videos or pictures by category.
  document.querySelectorAll('.ex-filter').forEach(section => section.querySelector('.chips').addEventListener('click', e => {
    const chip = e.target.closest('.chip'); if (!chip) return;
    section.querySelectorAll('.chip').forEach(c => { c.classList.toggle('on', c === chip); c.setAttribute('aria-selected', c === chip); });
    const all = chip.dataset.cat === 'all', more = section.querySelector('.ex-more');
    // "All" shows a balanced first selection with "See all" for the rest; a category shows everything in it.
    section.querySelectorAll('[data-cat]:not(.chip)').forEach(item => item.hidden =
      all ? item.classList.contains('ex-extra') && !section.classList.contains('expanded') : item.dataset.cat !== chip.dataset.cat);
    if (more) more.hidden = !all || section.classList.contains('expanded');
  }));
  document.querySelectorAll('.ex-more').forEach(button => button.addEventListener('click', () => {
    const section = button.closest('.ex-filter');
    section.classList.add('expanded');
    section.querySelectorAll('.ex-extra').forEach(item => item.hidden = false);
    button.hidden = true;
  }));
</script>'''
    return page('examples', 'Gallery · Strokeberry', 'Hand-drawn videos made with Strokeberry for shops, interiors, cafés, teachers and creators, and ready-to-use pictures to start from.', body, extra_body=script)


FEATURED = 'what-is-a-speed-drawing-video'  # the big card at the top of the blog page
# Cards play their drawing on hover with a mouse; on touch screens they stay as pictures.
BLOG_HOVER = '''<script>
  if (matchMedia('(hover: hover)').matches && !matchMedia('(prefers-reduced-motion: reduce)').matches)
    document.querySelectorAll('.bcard video[data-hover]').forEach(video => {
      const card = video.closest('.bcard');
      card.addEventListener('mouseenter', () => {
        if (!video.src) video.src = video.dataset.hover;
        video.currentTime = 0; video.play().then(() => card.classList.add('playing')).catch(() => {});
      });
      card.addEventListener('mouseleave', () => { card.classList.remove('playing'); video.pause(); });
    });
</script>'''


def build_blog():
    written = []
    for slug, title, description, date, minutes, content in POSTS:
        body = (f'<main class="doc post"><p class="doc-meta"><a href="/blog/">Blog</a> · {date} · {minutes} min read</p>'
                f'<h1>{html.escape(title)}</h1><p class="post-lede">{html.escape(description)}</p>{content}</main>')
        ld = json.dumps({'@context': 'https://schema.org', '@type': 'BlogPosting', 'headline': title, 'description': description,
                         'datePublished': '2026-10-01', 'author': {'@type': 'Organization', 'name': 'Strokeberry'}})
        written.append(page(f'blog/{slug}', f'{title} · Strokeberry', description, body,
                            extra_head=f'<script type="application/ld+json">{ld}</script>'))
    featured, *rest = sorted(POSTS, key=lambda post: post[0] != FEATURED)
    post_card = lambda post, **extra: card(f'/blog/{post[0]}/', lead_clip(post[5]), f'Guide · {post[4]} min read', post[1], post[2], **extra)
    cards = ''.join(post_card(post) for post in rest)
    body = f'''<main class="wrap ex-page blog-page"><header class="ex-head"><p class="eyebrow">Blog</p><h1>Ideas for hand-drawn videos</h1>
<p class="section-sub">Practical guides for small businesses, teachers and creators, with real videos made in Strokeberry.</p></header>
{post_card(featured, featured=True)}
<section class="blog-block"><div class="blog-block-head"><p class="eyebrow">How-to guides</p><h2>Make your first drawing video</h2></div><div class="bcard-grid">{cards}</div></section>
<section class="blog-block"><div class="blog-block-head"><p class="eyebrow">Use cases</p><h2>Strokeberry for…</h2></div><div class="bcard-grid bcard-grid-5">{guide_cards('for')}</div></section>
<section class="blog-block"><div class="blog-block-head"><p class="eyebrow">Comparisons</p><h2>How Strokeberry compares</h2></div><div class="bcard-grid">{guide_cards('compare')}</div></section>
<aside class="blog-band"><img src="/brand/strokeberry-mascot@2x.png" width="86" height="88" alt=""/><div><h2>Your picture, drawn in a minute</h2><p>Drop in a logo, a product or a drawing and watch it come to life. No sign-up to preview.</p></div>
<a class="btn btn-primary" href="/studio/">Try it free <svg width="18" height="18"><use href="#arrow"/></svg></a></aside></main>'''
    written.append(page('blog', 'Blog · Strokeberry', 'Guides to making hand-drawn videos for your business, your classroom and your social media.', body,
                        extra_body=BLOG_HOVER))
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
    pages = [build_examples()] + build_blog() + build_guides()
    build_sitemap(pages)
    print('\n'.join(pages + ['public/sitemap.xml', 'public/robots.txt']))
