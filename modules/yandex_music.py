"""
Поддержка Яндекс Музыки для музыкального плеера.

Работает через API api.music.yandex.net:
  - Без токена: возвращаются 30-секундные превью треков.
  - С токеном (YANDEX_MUSIC_TOKEN, нужна подписка Плюс):
    возвращаются полные треки.

Поддерживаемые ссылки:
  - Плейлист: music.yandex.ru/users/{login}/playlists/{kind}
  - Альбом:   music.yandex.ru/album/{album_id}
  - Трек:     music.yandex.ru/album/{album_id}/track/{track_id}
"""

import hashlib
import logging
import os
import re
import xml.etree.ElementTree as ET

import aiohttp

logger = logging.getLogger('discord_bot.yandex')

BASE_URL = 'https://api.music.yandex.net'
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36')

# Ссылки на Яндекс Музыку
_PLAYLIST_RE = re.compile(r'music\.yandex\.\w+/users/(?P<login>[^/]+)/playlists/(?P<kind>\d+)')
_ALBUM_RE = re.compile(r'music\.yandex\.\w+/album/(?P<album>\d+)')
_TRACK_RE = re.compile(r'music\.yandex\.\w+/album/(?P<album>\d+)/track/(?P<track>\d+)')


def get_token():
    """Токен Яндекс Музыки из окружения (YANDEX_MUSIC_TOKEN), или None"""
    return os.getenv('YANDEX_MUSIC_TOKEN') or None


def is_yandex_url(url: str) -> bool:
    """Является ли ссылка ссылкой на Яндекс Музыку"""
    if not url or not re.match(r'https?://', url):
        return False
    return bool(re.search(r'music\.yandex\.\w+', url))


def _headers(token=None):
    headers = {
        'User-Agent': USER_AGENT,
        'X-Requested-With': 'XMLHttpRequest',
    }
    if token:
        headers['Authorization'] = f'OAuth {token}'
    return headers


async def _get_json(session, url, params=None, token=None):
    """GET с обработкой ошибок"""
    async with session.get(url, params=params, headers=_headers(token), timeout=aiohttp.ClientTimeout(total=20)) as resp:
        if resp.status == 401:
            raise YandexAuthError('Токен Яндекс Музыки недействителен или истёк')
        if resp.status == 403:
            raise YandexError('Яндекс Музыка заблокировала доступ (403). Возможно, недоступно из вашего региона')
        if resp.status != 200:
            raise YandexError(f'Яндекс Музыка вернула ошибку {resp.status}')
        data = await resp.json(content_type=None)
    return data.get('result')


class YandexError(Exception):
    pass


class YandexAuthError(YandexError):
    pass


def _parse_track_url(url: str):
    """Разбор ссылки: (тип, параметры) — track/album/playlist"""
    m = _TRACK_RE.search(url)
    if m:
        return 'track', {'album': int(m.group('album')), 'track': int(m.group('track'))}
    m = _ALBUM_RE.search(url)
    if m:
        return 'album', {'album': int(m.group('album'))}
    m = _PLAYLIST_RE.search(url)
    if m:
        return 'playlist', {'login': m.group('login'), 'kind': int(m.group('kind'))}
    return None, None


async def _fetch_track_info(session, track_id, album_id, token):
    """Полная информация о треке (название, артист, длительность, обложка)"""
    url = f'{BASE_URL}/tracks/{track_id}:{album_id}'
    data = await _get_json(session, url, token=token)
    if not data or not data:
        return None
    info = data[0]
    albums = info.get('albums') or []
    album = albums[0] if albums else {}
    cover = album.get('coverUri') or ''
    if cover:
        cover = 'https://' + cover.replace('%%', '400x400')
    artists = [a.get('name') for a in (info.get('artists') or []) if a.get('name')]
    return {
        'title': info.get('title') or 'Неизвестно',
        'duration': (info.get('durationMs') or 0) / 1000,
        'thumbnail': cover or None,
        'channel': ', '.join(artists) or 'Яндекс Музыка',
    }


async def _build_direct_url(session, track_id, album_id, token):
    """Прямая ссылка на mp3 трека (превью или полный, зависит от токена)"""
    url = f'{BASE_URL}/tracks/{track_id}:{album_id}/download-info'
    data = await _get_json(session, url, token=token)
    if not data:
        return None
    info = data[0]
    download_info_url = info.get('downloadInfoUrl')
    if not download_info_url:
        return None
    async with session.get(download_info_url, headers=_headers(token), timeout=aiohttp.ClientTimeout(total=20)) as resp:
        if resp.status != 200:
            return None
        text = await resp.text()
    try:
        root = ET.fromstring(text)
        host = root.findtext('host') or ''
        path = root.findtext('path') or ''
        ts = root.findtext('ts') or ''
        s = root.findtext('s') or ''
        if not (host and path and s):
            return None
        key = hashlib.md5(('XGRlBW9FXlekgbPrRHuSiA' + path[1:] + s).encode()).hexdigest()
        return f'https://{host}/get-mp3/{key}/{ts}{path}?track-id={track_id}'
    except ET.ParseError as e:
        logger.error(f'Ошибка разбора XML download-info: {e}')
        return None


async def _search_playlist_by_login(session, login, kind, token):
    """Поиск плейлиста по логину: получаем uid пользователя через поиск, затем плейлист"""
    # Ищем пользователя по логину
    search_url = f'{BASE_URL}/search'
    params = {'text': login, 'type': 'user', 'page': '0'}
    data = await _get_json(session, search_url, params=params, token=token)
    uid = None
    try:
        users = data.get('users', {}).get('results', [])
        if users:
            uid = users[0].get('uid')
    except AttributeError:
        pass

    if not uid:
        # Возможно uid в поле 'id' или плейлист доступен по логину напрямую
        uid = login

    pl_url = f'{BASE_URL}/users/{uid}/playlists/{kind}'
    return await _get_json(session, pl_url, token=token)


async def _playlist_tracks(session, url, token):
    """Получение списка треков плейлиста"""
    kind_type, params = _parse_track_url(url)
    if kind_type == 'playlist':
        data = await _search_playlist_by_login(session, params['login'], params['kind'], token)
        if not data:
            return None, None
        title = data.get('title') or 'Плейлист'
        tracks = data.get('tracks') or []
    elif kind_type == 'album':
        album_url = f"{BASE_URL}/albums/{params['album']}/with-tracks"
        data = await _get_json(session, album_url, token=token)
        if not data:
            return None, None
        title = data.get('title') or 'Альбом'
        # Объединяем все диски альбома
        volumes = data.get('volumes') or []
        tracks = [t for vol in volumes for t in vol if isinstance(t, dict)]
    else:
        return None, None

    return title, tracks


async def _tracks_to_bot_format(session, tracks, token):
    """Преобразование треков Яндекса в формат бота (title/url/webpage_url/duration/thumbnail/channel)"""
    result = []
    for t in tracks:
        if not isinstance(t, dict):
            continue
        track = t.get('track') or t
        track_id = track.get('id') or track.get('realId')
        albums = track.get('albums') or []
        album_id = albums[0].get('id') if albums and isinstance(albums[0], dict) else None
        if not track_id or not album_id:
            continue

        info = await _fetch_track_info(session, track_id, album_id, token)
        direct = await _build_direct_url(session, track_id, album_id, token)
        if not info or not direct:
            continue

        result.append({
            'title': info['title'],
            'url': direct,
            'webpage_url': f'https://music.yandex.ru/album/{album_id}/track/{track_id}',
            'duration': info['duration'],
            'thumbnail': info['thumbnail'],
            'channel': info['channel'],
        })
    return result


async def fetch_yandex_playlist(session, url, token=None, limit=50):
    """Основная функция: по ссылке возвращает (название, [треки в формате бота])"""
    try:
        title, tracks = await _playlist_tracks(session, url, token)
        if not tracks:
            return None, []
        bot_tracks = await _tracks_to_bot_format(session, tracks[:limit], token)
        return title, bot_tracks
    except YandexError as e:
        logger.warning(f'Яндекс Музыка: {e}')
        return None, []
    except Exception as e:
        logger.error(f'Ошибка Яндекс Музыки: {e}')
        return None, []


async def fetch_yandex_single_track(session, url, token=None):
    """По ссылке на трек возвращает трек в формате бота или None"""
    try:
        kind_type, params = _parse_track_url(url)
        if kind_type != 'track':
            return None
        track_id, album_id = params['track'], params['album']
        info = await _fetch_track_info(session, track_id, album_id, token)
        direct = await _build_direct_url(session, track_id, album_id, token)
        if not info or not direct:
            return None
        return {
            'title': info['title'],
            'url': direct,
            'webpage_url': url,
            'duration': info['duration'],
            'thumbnail': info['thumbnail'],
            'channel': info['channel'],
        }
    except Exception as e:
        logger.error(f'Ошибка получения трека Яндекса: {e}')
        return None


async def make_session():
    """Создание HTTP-сессии для Яндекс Музыки (освобождать после использования)"""
    return aiohttp.ClientSession(headers={'User-Agent': USER_AGENT})
