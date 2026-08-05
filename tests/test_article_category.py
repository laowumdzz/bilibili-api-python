# bilibili_api.article_category

from bilibili_api import article_category


def test_a_get_category_info_by_id():
    article_category.get_category_info_by_id(3)


def test_b_get_category_info_by_name():
    article_category.get_category_info_by_name("轻小说")


def test_c_get_category_list():
    article_category.get_categories_list()


def test_d_get_category_list_sub():
    article_category.get_categories_list_sub()


async def test_e_get_category_recommend_articles():
    await article_category.get_category_recommend_articles(
        category_id=3,
        order=article_category.ArticleOrder.FAVORITES,
        page_num=11,
        page_size=4514,
    )
