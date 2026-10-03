"""Plain, occasional emails: a welcome message, free-allowance notices and founding-member reservations.

Sending is off until SMTP is configured (for Zoho: SMTP_HOST=smtp.zoho.com, SMTP_PORT=465, SMTP_USER=hi@strokeberry.com,
SMTP_PASSWORD=<an app-specific password from Zoho>, optional SMTP_FROM="Strokeberry <hi@strokeberry.com>"). Emails are sent on a
background thread so a slow mail server never slows a request, and any failure is logged and ignored.
"""
import logging
import os
import smtplib
import threading
from email.message import EmailMessage


def configured():
    return all(os.environ.get(k) for k in ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD'))


def _app_url():
    return os.environ.get('STROKEBERRY_APP_URL', 'http://127.0.0.1:8001').rstrip('/')


def _send(to, subject, text, html):
    try:
        message = EmailMessage()
        message['Subject'] = subject
        message['From'] = os.environ.get('SMTP_FROM') or f"Strokeberry <{os.environ['SMTP_USER']}>"
        message['To'] = to
        message['Reply-To'] = os.environ['SMTP_USER']
        message.set_content(text)
        message.add_alternative(html, subtype='html')
        host, port = os.environ['SMTP_HOST'], int(os.environ.get('SMTP_PORT', '465'))
        smtp = smtplib.SMTP_SSL(host, port, timeout=20) if port == 465 else smtplib.SMTP(host, port, timeout=20)
        with smtp:
            if port != 465:
                smtp.starttls()
            smtp.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
            smtp.send_message(message)
    except Exception:
        logging.exception('Could not send email to %s', to)


def send(to, subject, paragraphs, button=None, picture=None):
    """paragraphs: list of strings; button: (label, path) linking into the app; picture: (path, alt) of an image on the
    site shown above the button. Images are linked from strokeberry.com (never attached or SVG), so every mail app shows them."""
    if not to or not configured():
        return False
    url = f'{_app_url()}{button[1]}' if button else None
    text = '\n\n'.join(paragraphs) + (f'\n\n{button[0]}: {url}' if url else '') + \
        '\n\nThe Strokeberry team\nQuestions? Just reply to this email.'
    body = ''.join(f'<p style="margin:0 0 16px;font-size:16px;line-height:1.6;color:#3a352f">{p}</p>' for p in paragraphs)
    base = _app_url()
    image = ''
    if picture:
        image = (f'<a href="{url or base}" style="display:block;margin:8px 0 20px"><img src="{base}{picture[0]}" alt="{picture[1]}" width="280" '
                 'style="display:block;width:100%;max-width:280px;height:auto;border-radius:14px;border:1px solid #efe2ca"></a>')
    cta = f'<p style="margin:24px 0"><a href="{url}" style="background:#1b1b1b;color:#fff;text-decoration:none;padding:14px 26px;border-radius:999px;font-weight:600;display:inline-block">{button[0]}</a></p>' if url else ''
    html = ('<div style="background:#fff8ec;padding:32px 16px;font-family:Figtree,Helvetica,Arial,sans-serif"><div style="max-width:520px;margin:0 auto;'
            'background:#fffdf8;border-radius:20px;padding:32px;border:1px solid #efe2ca"><p style="margin:0 0 20px;font-size:22px;font-weight:800;'
            f'letter-spacing:-.02em;color:#1b1b1b"><img src="{base}/email/mascot.png" alt="" width="34" height="34" '
            f'style="vertical-align:middle;margin-right:8px;border:0">strokeberry</p>{body}{image}{cta}<p style="margin:24px 0 0;font-size:13px;color:#8a8174">Questions? Just reply to this email.</p></div></div>')
    threading.Thread(target=_send, args=(to, subject, text, html), daemon=True).start()
    return True


def welcome(to, name=None):
    first = (name or '').split(' ')[0]
    return send(to, 'Welcome to Strokeberry', [
        f'Hi {first},' if first else 'Hi there,',
        'Thanks for joining Strokeberry. You get 3 free videos every month, and there’s a quick way to get a great first result: '
        'pick one of the examples, choose Ink, and export it as a 9:16 video for Reels or TikTok.',
        'Your projects are saved, so you can come back and make more any time.'], ('Open the studio', '/studio/'),
        ('/email/drawing.gif', 'A puppy being drawn by hand, then painted in'))


def allowance(to, remaining, resets=None):
    if remaining > 0:
        return send(to, 'You have 1 free video left', [
            'You’ve used 2 of your 3 free videos this month, so there’s 1 left. Make it a good one!',
            'You get 3 new free videos every month. If you’d like more sooner, Strokeberry Pro gives you 200 videos a month in Full HD with no watermark.'],
            ('Open the studio', '/studio/'))
    return send(to, 'You’ve used your 3 free videos this month', [
        'That’s all 3 free videos used for now' + (f'. They come back on {resets}.' if resets else '.') + ' Your projects are still here and you can keep previewing as much as you like.',
        'To export more, Strokeberry Pro gives you 200 videos a month in Full HD with no watermark. Cancel any time.'],
        ('See Pro', '/studio/?upgrade=1'))


def reserved(to, position, limit, price, gift, name=None):
    first = (name or '').split(' ')[0]
    return send(to, f'You’re founding member #{position}', [
        f'Hi {first},' if first else 'Hi there,',
        f'Your founding place is reserved: you’re number {position} of {limit}. When payments open you can go Pro for {price} a month '
        'instead of $10, for as long as you stay subscribed. There’s nothing to pay now.',
        f'As a thank-you, we’ve added {gift} videos without a watermark or end card to your account. Use them on anything you like.',
        'We’ll email you as soon as your price is ready to claim.'], ('Make a video', '/studio/'),
        ('/email/drawing.gif', 'A puppy being drawn by hand, then painted in'))


def founding_open(to, price):
    return send(to, 'Your founding price is ready', [
        'Hi there,',
        f'Payments are now open, and the founding price you reserved is waiting for you: Strokeberry Pro for {price} a month, '
        'for as long as you stay subscribed.',
        'Pro gives you 200 videos a month, up to 5 minutes each, in up to 4K, with no watermark. Cancel anytime.'],
        ('Claim my founding price', '/studio/?upgrade=1'))
