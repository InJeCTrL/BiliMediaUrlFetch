import json
import requests
from typing import Dict

REQ_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0',
}
URL_FORMAT = "https://www.bilibili.com/video/{0}"
PATTERN_PLAYINFO = 'window.__playinfo__='
PATTERN_INITIAL_STATE = 'window.__INITIAL_STATE__='

ERR_INVALID_BVID = 'No invalid bvid provided'

def success(data: Dict[str, object]) -> Dict[str, object]:
    return {
        'statusCode': 200,
        'body': json.dumps(
            {
                'data': data,
                'msg': '',
            }
        )
    }

def error(code: int, tip: str) -> Dict[str, object]:
    return {
        'statusCode': code,
        'body': json.dumps(
            {
                'data': None,
                'msg': tip,
            }
        )
    }
    
def extract_media_url(html_content: str) -> Dict[str, object]:
    media_info = {}
    
    play_info = html_content[html_content.index(PATTERN_PLAYINFO) + len(PATTERN_PLAYINFO):]
    play_info = play_info[:play_info.index('</script>')]
    play_info_data = json.loads(play_info)
    data = play_info_data.get('data')
    if not data:
        return media_info
    
    dash = data.get('dash')
    if not dash:
        return media_info
    
    video = dash.get('video')
    if video and video[0]:
        media_info['video'] = {
            'url': video[0].get('baseUrl'),
            'bandwidth': video[0].get('bandwidth'),
            'mime': video[0].get('mimeType'),
            'codec': video[0].get('codecs'),
        }

    audio = dash.get('audio')
    if audio and audio[0]:
        media_info['audio'] = {
            'url': audio[0].get('baseUrl'),
            'bandwidth': audio[0].get('bandwidth'),
            'mime': audio[0].get('mimeType'),
            'codec': audio[0].get('codecs'),
        }
        
    return media_info

def lambda_handler(event, context):
    params = event.get('queryStringParameters')
    if not params:
        return error(400, ERR_INVALID_BVID)

    bvid = params.get('bvid')
    if not bvid:
        return error(400, ERR_INVALID_BVID)

    url_default = URL_FORMAT.format(bvid)
    with requests.get(url_default, headers=REQ_HEADERS) as response_default:
        content_default = response_default.text
        if PATTERN_PLAYINFO not in content_default or PATTERN_INITIAL_STATE not in content_default:
            return error(400, ERR_INVALID_BVID)

    initial_state = content_default[content_default.index(PATTERN_INITIAL_STATE) + len(PATTERN_INITIAL_STATE):]
    initial_state = initial_state[:initial_state.index('};(')+1]
    initial_state_data = json.loads(initial_state)
    video_data = initial_state_data.get('videoData')
    if not video_data:
        return error(400, ERR_INVALID_BVID)
    
    title = video_data.get('title')
    
    pages = video_data.get('pages')
    if not pages:
        return error(400, ERR_INVALID_BVID)

    if len(pages) == 1:
        return success({
            'title': title,
            'media': [extract_media_url(content_default)],
        })
    else:
        pages_media = []
        for page in pages:
            page_no = page.get('page')
            page_title = page.get('part')

            with requests.get(url_default+f"/?p={page_no}", headers=REQ_HEADERS) as response_page:
                content_page = response_page.text
                media = extract_media_url(content_page)
                media['page'] = page_no
                media['page_title'] = page_title
                pages_media.append(media)

        return success({
            'title': title,
            'media': pages_media,
        })
