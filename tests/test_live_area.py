# bilibili_api.live_area

from bilibili_api import live_area


async def test_a_get_list_by_area_id():
    await live_area.fetch_live_area_data()
    await live_area.get_list_by_area(
        area_id=live_area.get_area_info_by_name("虚拟主播")[0]["id"],
        page=1,
        # order 为 sort_type 字符串（取值见接口返回的 new_tags 字段）
        order="online",
    )
