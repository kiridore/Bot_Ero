# API Warpper

from core import ws_controller as ws


def send_msg(message_tpye: str, target_id, *message,) -> int:
    # https://github.com/botuniverse/onebot-11/blob/master/api/public.md#send_msg-%E5%8F%91%E9%80%81%E6%B6%88%E6%81%AF
    if message_tpye == "group":
        return send_group_msg(target_id, *message)
    else:
        return send_private_msg(target_id, *message)

def send_private_msg(user_id, *message) -> int:
    # https://github.com/botuniverse/onebot-11/blob/master/api/public.md#send_private_msg-%E5%8F%91%E9%80%81%E7%A7%81%E8%81%8A%E6%B6%88%E6%81%AF
    params = {"user_id": user_id, "message": message}
    ret = ws.call_api("send_private_msg", params)
    return 0 if ret is None or ret["status"] == "failed" else ret["data"]["message_id"]

def send_group_msg(group_id, *message) -> int:
    # https://github.com/botuniverse/onebot-11/blob/master/api/public.md#send_group_msg-%E5%8F%91%E9%80%81%E7%BE%A4%E6%B6%88%E6%81%AF
    params = {"group_id": group_id, "message": message}
    ret = ws.call_api("send_group_msg", params)
    return 0 if ret is None or ret["status"] == "failed" else ret["data"]["message_id"]

def get_group_member_info(group_id, user_id):
    #https://github.com/botuniverse/onebot-11/blob/master/api/public.md#get_group_member_info-%E8%8E%B7%E5%8F%96%E7%BE%A4%E6%88%90%E5%91%98%E4%BF%A1%E6%81%AF
    params = {"group_id": group_id, "user_id": user_id}
    ret = ws.call_api("get_group_member_info", params)
    return ret["data"]

def get_image(file):
    # https://github.com/botuniverse/onebot-11/blob/master/api/public.md#get_image-%E8%8E%B7%E5%8F%96%E5%9B%BE%E7%89%87
    params = {"file": file}
    ret = ws.call_api("get_image", params)
    if ret["status"] == "ok":
        return ret["data"]["file"]
    else :
        return ""

def get_qq_avatar(user_id):
    params = {"user_id": user_id}
    ret = ws.call_api("get_qq_avatar", params)
    return ret["data"]["url"]

def set_friend_add_request(flag, approve = True):
    params = {"flag": flag, "approve" : approve, "remark": ""}
    ws.call_api("set_friend_add_request", params)
