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


async def test_c_Article_set_like(ar):
    try:
        await ar.set_like()
        await ar.set_like(False)
    except ResponseCodeException as e:
        if e.code not in (65006,):
            raise e


async def test_d_Article_set_favorite(ar):
    await ar.set_favorite()


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
