"""Web and network access tools."""

import httpx
from langchain_core.tools import tool
from markdownify import markdownify as md


@tool
async def web_fetch(url: str, max_length: int = 10000) -> str:
    """获取网页内容并转换为纯文本。

    Args:
        url: 要获取的网页URL
        max_length: 返回内容的最大长度，默认10000字符
    """
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 PRTS-Agent/1.0"
            })
            response.raise_for_status()

            text = md(response.text, strip=["script", "style", "nav", "footer", "header"])
            text = " ".join(text.split())

            if len(text) > max_length:
                text = text[:max_length] + f"\n\n... (内容被截断，总长度 {len(text)} 字符)"
            return text or "(页面无文本内容)"
    except httpx.HTTPStatusError as e:
        return f"HTTP 错误 {e.response.status_code}: {url}"
    except httpx.TimeoutException:
        return f"请求超时: {url}"
    except Exception as e:
        return f"错误: {str(e)}"


@tool
async def web_search(query: str, num_results: int = 5) -> str:
    """搜索互联网获取信息（需要配置搜索 API Key）。

    Args:
        query: 搜索关键词
        num_results: 返回结果数量，默认5
    """
    return f"搜索 '{query}': Web search requires SEARCH_API_KEY to be configured. Using web_fetch for targeted retrieval instead."


@tool
async def http_request(
    method: str = "GET",
    url: str = "",
    headers: str = "{}",
    body: str = "",
) -> str:
    """发送 HTTP 请求。

    Args:
        method: HTTP 方法 (GET/POST/PUT/DELETE)
        url: 请求 URL
        headers: JSON 格式的请求头
        body: 请求体内容
    """
    import json
    try:
        parsed_headers = json.loads(headers) if headers else {}
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.request(
                method=method.upper(),
                url=url,
                headers=parsed_headers,
                content=body if body else None,
            )
            return f"Status: {resp.status_code}\n\n{resp.text[:5000]}"
    except Exception as e:
        return f"HTTP 请求失败: {str(e)}"
