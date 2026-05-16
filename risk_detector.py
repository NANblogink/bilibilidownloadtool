#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
风控检测模块 - 用于检测B站API是否被风控
"""

import time
import logging
import threading
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class ApiTestResult:
    """API测试结果"""
    api_name: str
    api_url: str
    status: str  # 'normal', 'risk', 'error', 'timeout'
    message: str
    response_code: int = 0
    response_time: float = 0.0
    details: Dict = None
    critical: bool = False  # 是否为关键API

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class RiskDetector:
    """风控检测器"""

    # 关键API端点列表
    TEST_APIS = [
        {
            'name': '用户导航信息',
            'url': 'https://api.bilibili.com/x/web-interface/nav',
            'description': '获取用户登录状态和基本信息',
            'critical': True,
        },
        {
            'name': '视频信息查询',
            'url': 'https://api.bilibili.com/x/web-interface/view?aid=170001&jsonp=jsonp',
            'description': '获取视频详细信息',
            'critical': True,
        },
        {
            'name': '播放地址获取',
            'url': 'https://api.bilibili.com/x/player/playurl?cid=11783021&bvid=BV1xx411c7XD&qn=80&fnval=16',
            'description': '获取视频播放URL（需登录）',
            'critical': True,
        },
        {
            'name': '番剧信息查询',
            'url': 'https://api.bilibili.com/pgc/view/web/season?season_id=42589',
            'description': '获取番剧/纪录片信息',
            'critical': False,
        },
        {
            'name': 'UP主空间信息',
            'url': 'https://api.bilibili.com/x/space/acc/info?mid=2',
            'description': '获取UP主空间信息',
            'critical': False,
        },
        {
            'name': '搜索接口',
            'url': 'https://api.bilibili.com/x/web-interface/wbi/search/type?keyword=test&search_type=video',
            'description': '测试搜索功能是否正常',
            'critical': False,
        },
    ]

    def __init__(self):
        self.results: List[ApiTestResult] = []
        self.is_running = False
        self._cancel_flag = False

    def test_single_api(self, api_info: Dict, progress_callback: Callable = None) -> ApiTestResult:
        """
        测试单个API

        Args:
            api_info: API信息字典
            progress_callback: 进度回调函数 callback(message)

        Returns:
            ApiTestResult: 测试结果
        """
        import requests

        api_name = api_info['name']
        api_url = api_info['url']
        description = api_info.get('description', '')

        if progress_callback:
            progress_callback(f"正在测试: {api_name}...")

        start_time = time.time()
        result = ApiTestResult(
            api_name=api_name,
            api_url=api_url.split('?')[0],
            status='error',
            message='未知错误',
            critical=api_info.get('critical', False)
        )

        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com',
                'Origin': 'https://www.bilibili.com',
            })

            resp = session.get(api_url, timeout=15, allow_redirects=True)
            response_time = time.time() - start_time
            result.response_time = round(response_time * 1000, 2)  # 转换为毫秒
            result.response_code = resp.status_code

            if progress_callback:
                progress_callback(f"完成: {api_name} ({result.response_code}, {result.response_time}ms)")

            if resp.status_code == 200:
                content = resp.text.strip()

                if content.startswith('!'):
                    start_index = content.find('{')
                    if start_index != -1:
                        content = content[start_index:]

                try:
                    import json
                    data = json.loads(content)
                    code = data.get('code', 0)

                    if code == 0:
                        result.status = 'normal'
                        result.message = f'正常响应 ({result.response_time}ms)'
                        result.details = {
                            'code': code,
                            'data_keys': list(data.get('data', {}).keys())[:5] if isinstance(data.get('data'), dict) else None
                        }
                    elif code in [-403, 403]:
                        result.status = 'risk'
                        result.message = f'访问被拒绝 (错误码: {code})'
                        result.details = {'code': code, 'reason': '可能触发风控或权限不足'}
                    elif code == -352:
                        result.status = 'risk'
                        result.message = f'风控校验失败 (错误码: {code})'
                        result.details = {'code': code, 'reason': '触发B站风控机制'}
                    else:
                        from error_codes import ERROR_CODES
                        error_msg = ERROR_CODES.get(code, data.get('message', '未知错误'))
                        result.status = 'risk' if code < 0 else 'normal'
                        result.message = f'API返回错误: {error_msg} (code={code})'
                        result.details = {'code': code, 'message': error_msg}
                except Exception as e:
                    if '访问权限不足' in content or not content:
                        result.status = 'risk'
                        result.message = '内容异常，可能被风控拦截'
                        result.details = {'raw_content_length': len(content)}
                    else:
                        result.status = 'normal'
                        result.message = f'响应成功但非JSON格式 ({result.response_time}ms)'
                        result.details = {'content_preview': content[:200]}
            elif resp.status_code == 403:
                result.status = 'risk'
                result.message = 'HTTP 403 禁止访问 - 可能IP被封禁或触发风控'
                result.details = {'http_code': 403, 'headers': dict(resp.headers)}
            elif resp.status_code == 412:
                result.status = 'risk'
                result.message = 'HTTP 412 预检失败 - 可能触发了验证码机制'
                result.details = {'http_code': 412}
            else:
                result.status = 'error'
                result.message = f'HTTP {resp.status_code} 错误'
                result.details = {'http_code': resp.status_code}

        except requests.exceptions.Timeout:
            result.status = 'timeout'
            result.message = '请求超时 (>15秒) - 可能网络问题或被限速'
            result.response_time = 15000
        except requests.exceptions.ConnectionError as e:
            result.status = 'error'
            result.message = f'连接错误: {str(e)[:50]}'
        except Exception as e:
            result.status = 'error'
            result.message = f'请求异常: {str(e)[:50]}'

        return result

    def run_all_tests(self, progress_callback: Callable = None, complete_callback: Callable = None):
        """
        运行所有API测试

        Args:
            progress_callback: 进度回调 callback(current, total, message)
            complete_callback: 完成回调 callback(results)
        """
        def _run_tests():
            self.is_running = True
            self._cancel_flag = False
            self.results = []

            total_apis = len(self.TEST_APIS)

            for index, api_info in enumerate(self.TEST_APIS):
                if self._cancel_flag:
                    if progress_callback:
                        progress_callback(index + 1, total_apis, "测试已取消")
                    break

                if progress_callback:
                    progress_callback(index + 1, total_apis, f"正在测试: {api_info['name']}...")

                result = self.test_single_api(api_info, lambda msg: None)
                self.results.append(result)

                if index < total_apis - 1 and not self._cancel_flag:
                    time.sleep(0.5)  # 避免请求过快

            self.is_running = False

            if complete_callback:
                complete_callback(self.results)

        thread = threading.Thread(target=_run_tests, daemon=True)
        thread.start()

    def cancel_test(self):
        """取消正在运行的测试"""
        self._cancel_flag = True

    def generate_report(self) -> Dict:
        """
        生成检测报告

        Returns:
            Dict: 包含统计信息和详细结果的报告
        """
        if not self.results:
            return {'error': '尚未运行检测'}

        normal_count = sum(1 for r in self.results if r.status == 'normal')
        risk_count = sum(1 for r in self.results if r.status == 'risk')
        error_count = sum(1 for r in self.results if r.status == 'error')
        timeout_count = sum(1 for r in self.results if r.status == 'timeout')

        critical_risk = [r for r in self.results if r.critical and r.status == 'risk']

        overall_status = 'normal'
        if critical_risk:
            overall_status = 'danger'
        elif risk_count > 0:
            overall_status = 'warning'
        elif error_count > len(self.results) // 2:
            overall_status = 'error'

        return {
            'overall_status': overall_status,
            'summary': {
                'total': len(self.results),
                'normal': normal_count,
                'at_risk': risk_count,
                'errors': error_count,
                'timeouts': timeout_count,
            },
            'critical_issues': [
                {
                    'api': r.api_name,
                    'message': r.message,
                    'details': r.details
                } for r in critical_risk
            ],
            'detailed_results': [
                {
                    'name': r.api_name,
                    'url': r.api_url,
                    'status': r.status,
                    'message': r.message,
                    'response_time': r.response_time,
                    'response_code': r.response_code,
                    'is_critical': next((a['critical'] for a in self.TEST_APIS if a['name'] == r.api_name), False),
                } for r in self.results
            ],
            'recommendations': self._generate_recommendations(normal_count, risk_count, error_count, timeout_count)
        }

    def _generate_recommendations(self, normal, risk, error, timeout) -> List[str]:
        """生成建议列表"""
        recommendations = []

        if risk > 0:
            recommendations.append("检测到部分API返回风控相关错误码，建议：")
            recommendations.append("1. 检查账号状态，确认未违规")
            recommendations.append("2. 更换网络环境（如使用手机热点）")
            recommendations.append("3. 降低使用频率，避免频繁请求")
            recommendations.append("4. 如果持续出现，建议等待24小时后重试")

        if timeout > 0:
            recommendations.append("\n部分API请求超时，建议：")
            recommendations.append("1. 检查网络连接是否稳定")
            recommendations.append("2. 尝试关闭代理或VPN")
            recommendations.append("3. 切换DNS服务器")

        if error > 0 and risk == 0:
            recommendations.append("\n部分API返回错误，可能是临时性问题，稍后重试即可")

        if normal == len(self.results):
            recommendations.append("所有API均正常响应，当前网络环境良好！")

        return recommendations


# 全局实例
_detector_instance = None


def get_risk_detector():
    """获取风控检测器单例"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = RiskDetector()
    return _detector_instance
