# bilibili_api.audio

import pytest

from bilibili_api.audio import Audio, AudioList, get_hot_song_list, get_user_stat
from bilibili_api.exceptions.ResponseCodeException import ResponseCodeException


@pytest.fixture(scope="module")
def audio(credential) -> Audio:
    return Audio(1033769, credential)


@pytest.fixture(scope="module")
def audio_list(credential) -> AudioList:
    return AudioList(26241, credential)


async def test_a_Audio_get_info(audio):
    await audio.get_info()


async def test_b_Audio_get_tags(audio):
    await audio.get_tags()


async def test_c_get_user_stat(credential):
    await get_user_stat(660303135, credential)


async def test_d_Audio_get_download_url(audio):
    await audio.get_download_url()


async def test_e_Audio_add_coins(audio):
    try:
        await audio.add_coins()
    except ResponseCodeException as e:
        if e.code not in (34005, -104):
            raise e


async def test_f_AudioList_get_info(audio_list):
    await audio_list.get_info()


async def test_g_AudioList_get_song_list(audio_list):
    await audio_list.get_song_list()


async def test_h_AudioList_get_tags(audio_list):
    await audio_list.get_tags()


async def test_j_get_hot_song_list():
    await get_hot_song_list()
