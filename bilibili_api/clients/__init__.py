"""
bilibili_api.clients
"""

ALL_PROVIDED_CLIENTS = [
    ("curl_cffi", "CurlCFFIClient", {"impersonate": "", "http2": False, "chunk_size": 262144}),
    ("aiohttp", "AioHTTPClient", {"chunk_size": 262144}),
    ("httpx", "HTTPXClient", {"http2": False, "chunk_size": 262144}),
]
