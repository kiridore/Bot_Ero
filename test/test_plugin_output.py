from unittest.mock import Mock

import pytest

from core.message_output import MessageOutput


def test_merge_order_targets_and_special_messages():
    sent = []
    output = MessageOutput(lambda r: sent.append(r) or 1, ("group", 1))
    output.submit("后", merge="reply", order=20)
    output.submit("前", merge="reply", order=10)
    output.submit("同序", merge="reply", order=20)
    output.submit("私聊", target=("private", 1), merge="reply")
    output.submit("其他群", target=("group", 2), merge="reply")
    output.submit("独立一")
    output.submit("独立二")
    image = [{"type": "image", "data": {"file": "test.png"}}]
    output.submit(image, kind="segments", merge="reply")
    output.submit([{"type": "node", "data": {"id": "1"}}], kind="nodes", merge="reply")
    image.clear()
    output.flush()
    assert len(sent) == 7
    assert sent[-1].content == "前\n后\n同序"
    assert sent[0].target == ("private", 1)
    assert sent[1].target == ("group", 2)
    assert sent[4].content[0]["type"] == "image"


def test_capture_discards_failed_outputs():
    sent = []
    output = MessageOutput(lambda r: sent.append(r) or 1, ("group", 1))
    with pytest.raises(RuntimeError):
        with output.capture():
            output.submit("不发送")
            raise RuntimeError()
    with output.capture():
        output.submit("发送")
    output.flush()
    assert [r.content for r in sent] == ["发送"]


def test_length_boundary_preserves_every_character():
    sent = []
    output = MessageOutput(lambda r: sent.append(r) or 1, ("private", 1), max_text_chars=3)
    output.submit("甲乙丙丁\n戊")
    output.flush()
    assert "".join(r.content for r in sent) == "甲乙丙丁\n戊"
    assert all(len(r.content) <= 3 for r in sent)


@pytest.mark.parametrize("result", [0, None, RuntimeError("timeout")])
def test_failure_does_not_retry(result, caplog):
    send = Mock(side_effect=result if isinstance(result, Exception) else None, return_value=result)
    output = MessageOutput(send, ("group", 1))
    output.submit("已完成")
    output.flush()
    output.flush()
    send.assert_called_once()
    assert "不自动重试" in caplog.text


def test_rejects_missing_or_invalid_destination():
    output = MessageOutput(lambda r: 1)
    for target in (None, ("group", 0), ("private", True), ("bad", 1)):
        with pytest.raises(ValueError):
            output.submit("不能发送", target=target)
