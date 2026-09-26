# bilibili_api.interactive_video

import asyncio

import pytest

from bilibili_api import interactive_video


@pytest.fixture(scope="module")
def v(credential) -> interactive_video.InteractiveVideo:
    return interactive_video.InteractiveVideo("BV1Dt411N7LY", credential=credential)


@pytest.mark.cred1
async def test_a_InteractiveVideo_get_graph_version(v):
    await v.get_graph_version()


@pytest.mark.cred1
async def test_b_InteractiveVideo_get_edge_info(v):
    await v.get_edge_info()


@pytest.mark.cred1
async def test_c_get_all_nodes(v):
    edges_info = {}

    queue: list[interactive_video.InteractiveNode] = [await (await v.get_graph()).get_root_node()]

    def createEdge(edge_id: int):
        """
        创建节点信息到 edges_info
        """
        edges_info[edge_id] = {"title": None, "cid": None, "option": None}

    while queue:
        # 节点间 0.5s 节流，避免图遍历连发请求触发风控（research R8）
        await asyncio.sleep(0.5)
        now_node = queue.pop()

        now_node.get_jumping_condition().get_result()

        if (
            now_node.get_node_id() in edges_info
            and edges_info[now_node.get_node_id()]["title"] is not None
            and edges_info[now_node.get_node_id()]["cid"] is not None
        ):
            continue

        retry = 3
        while True:
            try:
                node = await now_node.get_info()
                title = node["title"]
                break
            except Exception as e:
                retry -= 1
                if retry < 0:
                    raise e

        if node["edge_id"] not in edges_info:
            createEdge(node["edge_id"])

        edges_info[node["edge_id"]]["title"] = title

        if "questions" not in node["edges"]:
            continue

        for n in await now_node.get_children():
            if n.get_node_id() not in edges_info:
                createEdge(n.get_node_id())

            edges_info[n.get_node_id()]["cid"] = n.get_cid()
            edges_info[n.get_node_id()]["option"] = n.get_self_button().get_text()

            # 所有可达顶点 ID 入队
            queue.insert(0, n)

    assert edges_info, "应至少遍历到一个互动视频节点"


@pytest.mark.cred2
async def test_d_mark_score(v):
    # 自身状态类白名单（data-model 安全策略表）：互动视频评分仅自身可见（可重复评分覆盖），
    # 不属于六态清单、无对外发布形态，成文归 cred2
    await v.mark_score(5)
