# 作者：寒烟似雪
# QQ：2273962061
# 转载时请勿删除
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session_with_retry(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    timeout=15
):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.timeout = timeout
    return session

def safe_request(session, method, url, **kwargs):
    for attempt in range(3):
        try:
            response = session.request(method, url,** kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt == 2:
                raise Exception(f"请求失败（尝试{attempt+1}次）：{str(e)}")
            time.sleep(1 + attempt * 0.5)