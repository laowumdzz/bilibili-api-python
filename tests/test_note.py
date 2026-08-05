# bilibili_api.note

import pytest

from bilibili_api import bvid2aid, note


@pytest.fixture(scope="module")
def public_note(credential) -> note.Note:
    return note.Note(cvid=15160286, note_type=note.NoteType.PUBLIC, credential=credential)


@pytest.fixture(scope="module")
def private_note(credential) -> note.Note:
    return note.Note(
        aid=bvid2aid("BV18d4y1L7KB"),
        note_id=39719442425318400,
        note_type=note.NoteType.PRIVATE,
        credential=credential,
    )


async def test_a_public_Note_markdown_get_content(public_note):
    await public_note.fetch_content()

    public_note.markdown()


async def test_b_public_Note_json_get_content(public_note):
    await public_note.fetch_content()

    public_note.json()


async def test_c_public_Note_get_info(public_note):
    await public_note.get_info()


async def test_d_private_Note_markdown_get_content(private_note):
    await private_note.fetch_content()

    private_note.markdown()


async def test_e_private_Note_json_get_content(private_note):
    await private_note.fetch_content()

    private_note.json()


async def test_f_private_Note_get_info(public_note):
    await public_note.get_info()
