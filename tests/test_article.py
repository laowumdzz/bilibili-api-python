# bilibili_api.article

import pytest

from bilibili_api import article
from bilibili_api.exceptions.ResponseCodeException import ResponseCodeException


@pytest.fixture(scope="module")
def ar(credential) -> article.Article:
    return article.Article(17973349, credential)


@pytest.fixture(scope="module")
def al(credential) -> article.ArticleList:
    return article.ArticleList(10, credential)


@pytest.mark.cred1
async def test_a_Article_markdown_get_content(ar):
    await ar.fetch_content()

    ar.markdown()


@pytest.mark.cred1
async def test_b_Article_json_get_content(ar):
    await ar.fetch_content()

    ar.json()


@pytest.mark.cred2
async def test_c_Article_set_like(ar, teardown_retry):
    # 可逆写配对单用例：点赞后立即取消点赞（FR-006 配对恢复）；取消点赞为
    # teardown 级清理义务（finally + teardown_retry，失败明确残留警告）
    changed = False
    try:
        try:
            await ar.set_like()
        except ResponseCodeException as e:
            # 65006：初始已点赞，状态未变，无需恢复
            if e.code != 65006:
                raise e
        else:
            changed = True
    finally:
        if changed:
            await teardown_retry("文章点赞残留（article_id=17973349）", lambda: ar.set_like(False))


@pytest.mark.cred2
async def test_d_Article_set_favorite(ar, teardown_retry):
    # 可逆写配对单用例：收藏后取消收藏（FR-006 配对恢复）；取消收藏为
    # teardown 级清理义务（finally + teardown_retry，失败明确残留警告）
    changed = False
    try:
        await ar.set_favorite()
        changed = True
    finally:
        if changed:
            await teardown_retry("文章收藏残留（article_id=17973349）", lambda: ar.set_favorite(False))


# 资源消耗类（文章投币，消耗硬币资源，research R7）→ cred3
@pytest.mark.cred3
async def test_e_Article_add_coins(ar):
    try:
        await ar.add_coins()
    except ResponseCodeException as e:
        if e.code not in (34005, -104):
            raise e


@pytest.mark.cred1
async def test_f_Article_get_info(ar):
    await ar.get_info()


@pytest.mark.cred1
async def test_g_ArticleList_get_article_list(al):
    await al.get_content()


@pytest.mark.cred1
async def test_h_get_article_rank():
    await article.get_article_rank()
