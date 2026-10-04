"""Facebook and Instagram numbers for the private dashboard, read from Meta's Graph API with a permanent Page token.

Configured by META_PAGE_TOKEN, META_PAGE_ID and META_IG_ID in .env.local (scripts/meta/connect.py sets them up). Read-only:
the token only has insight and profile permissions. Results are cached for five minutes so refreshing the dashboard doesn't
hammer the API. Facebook reel and page insights need Meta's `read_insights` permission; without it Facebook shows the reels only.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

GRAPH = 'https://graph.facebook.com/v26.0'
CACHE_SECONDS = 300
_cache = {}
POST_METRICS = 'reach,views,likes,comments,shares,saved,total_interactions'
REEL_METRICS = POST_METRICS + ',ig_reels_avg_watch_time'


def configured():
    return all(os.environ.get(k) for k in ('META_PAGE_TOKEN', 'META_PAGE_ID', 'META_IG_ID'))


def _get(path, **params):
    params['access_token'] = os.environ['META_PAGE_TOKEN']
    url = f'{GRAPH}/{path}?' + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        try:
            message = json.loads(error.read())['error']['message']
        except Exception:  # noqa: BLE001
            message = str(error)
        raise RuntimeError(message[:200])


def _values(insights):
    out = {}
    for item in insights.get('data', []):
        value = item.get('total_value', {}).get('value')
        if value is None and item.get('values'):
            value = item['values'][0].get('value')
        out[item['name']] = value
    return out


def _post_metrics(media):
    metrics = REEL_METRICS if media.get('media_product_type') == 'REELS' else POST_METRICS
    for attempt in (metrics, 'reach,likes,comments,saved,shares'):
        try:
            return _values(_get(f"{media['id']}/insights", metric=attempt))
        except RuntimeError:
            continue
    return {}


def _instagram(days):
    ig = os.environ['META_IG_ID']
    profile = _get(ig, fields='username,followers_count,follows_count,media_count')
    until = int(time.time())
    try:
        account = _values(_get(f'{ig}/insights', metric='reach,views,profile_views,website_clicks,accounts_engaged',
                               period='day', metric_type='total_value', since=until - days * 86400, until=until))
    except RuntimeError as error:
        account = {'error': str(error)}
    media = _get(f'{ig}/media', fields='id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count',
                 limit=25).get('data', [])
    with ThreadPoolExecutor(max_workers=6) as pool:
        metrics = list(pool.map(_post_metrics, media))
    posts = []
    for item, numbers in zip(media, metrics):
        kind = {'REELS': 'Reel', 'CAROUSEL_ALBUM': 'Carousel'}.get(item.get('media_product_type') or item.get('media_type'), 'Post')
        if item.get('media_type') == 'CAROUSEL_ALBUM':
            kind = 'Carousel'
        avg = numbers.get('ig_reels_avg_watch_time')
        posts.append({'id': item['id'], 'caption': (item.get('caption') or '').split('\n')[0][:90], 'type': kind,
                      'date': item['timestamp'], 'url': item.get('permalink'),
                      'reach': numbers.get('reach'), 'views': numbers.get('views'),
                      'likes': numbers.get('likes', item.get('like_count')), 'comments': numbers.get('comments', item.get('comments_count')),
                      'shares': numbers.get('shares'), 'saves': numbers.get('saved'),
                      'avg_watch': round(avg / 1000, 1) if avg else None})
    return {'profile': profile, 'account': account, 'posts': posts}


def _reel_numbers(reel):
    """Per-reel numbers from Facebook's video insights (needs read_insights)."""
    try:
        data = {i['name']: i['values'][0]['value'] for i in _get(f"{reel['id']}/video_insights").get('data', [])}
    except RuntimeError:
        return None
    actions = data.get('post_video_social_actions') or {}
    graph = data.get('post_video_retention_graph') or {}
    avg = data.get('post_video_avg_time_watched')
    return {'reach': data.get('post_impressions_unique'), 'plays': data.get('fb_reels_total_plays'),
            'reactions': sum((data.get('post_video_likes_by_reaction_type') or {}).values()),
            'comments': actions.get('COMMENT', 0), 'shares': actions.get('SHARE', 0),
            'avg_watch': round(avg / 1000, 1) if avg else None,
            'held_3s': graph.get('3'), 'follows': data.get('post_video_followers')}


def _facebook(days):
    page = os.environ['META_PAGE_ID']
    profile = _get(page, fields='name,followers_count,fan_count')
    reels = _get(f'{page}/video_reels', fields='id,description,created_time,permalink_url,length', limit=15).get('data', [])
    with ThreadPoolExecutor(max_workers=6) as pool:
        numbers = list(pool.map(_reel_numbers, reels))
    insights = any(n is not None for n in numbers) or not reels
    totals = {}
    if insights:
        until = int(time.time())
        try:
            for item in _get(f'{page}/insights', metric='page_media_view,page_total_media_view_unique,page_post_engagements,page_follows',
                             period='day', since=until - days * 86400, until=until).get('data', []):
                values = [v['value'] for v in item.get('values', []) if isinstance(v.get('value'), (int, float))]
                totals[item['name']] = sum(values)
        except RuntimeError:
            pass
    posts = []
    for reel, n in zip(reels, numbers):
        n = n or {}
        link = reel.get('permalink_url', '')
        posts.append({'id': reel['id'], 'caption': (reel.get('description') or '').split('\n')[0][:90], 'date': reel['created_time'],
                      'url': 'https://www.facebook.com' + link if link.startswith('/') else link, 'seconds': round(reel.get('length') or 0),
                      **{k: n.get(k) for k in ('reach', 'plays', 'reactions', 'comments', 'shares', 'avg_watch', 'held_3s', 'follows')}})
    return {'profile': profile, 'posts': posts, 'insights': insights, 'totals': totals}


def social(days=7):
    days = max(1, min(int(days), 30))
    cached = _cache.get(days)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1]
    result = {'generated': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'days': days}
    for name, fetch in (('instagram', lambda: _instagram(days)), ('facebook', lambda: _facebook(days))):
        try:
            result[name] = fetch()
        except RuntimeError as error:
            result[name] = {'error': str(error)}
    _cache[days] = (time.time(), result)
    return result
