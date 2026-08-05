# bilibili_api.manga

import pytest

from bilibili_api import manga


@pytest.fixture(scope="module")
def comic(credential) -> manga.Manga:
    return manga.Manga(manga_id=30023, credential=credential)


# async def test_c_Manga_get_images(comic):
#     await comic.get_images(1)


async def test_d_set_follow_manga(comic):
    await manga.set_follow_manga(manga=comic, status=True)
    await manga.set_follow_manga(manga=comic, status=False)


# async def test_e_get_manga_index(credential):
#     await manga.get_manga_index(credential=credential)


async def test_f_get_manga_update(credential):
    await manga.get_manga_update(credential=credential)


async def test_g_get_manga_home_recommend(credential):
    await manga.get_manga_home_recommend(credential=credential)
