"""
bilibili_api.clients
"""

ALL_PROVIDED_CLIENTS = [
    ("aiohttp", "AioHTTPClient", {"chunk_size": 262144}),
    ("httpx", "HTTPXClient", {"http2": False, "chunk_size": 262144}),
]
