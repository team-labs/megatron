from typing import List


class BotConnection:
    def broadcast(self, broadcast: dict, user_ids: List[str], capture_feedback: bool):
        raise NotImplementedError

    def message(self, bot_user_id: str, msg: str):
        raise NotImplementedError

    def dm_user(self, bot_user_id: str, msg: str):
        raise NotImplementedError

    def join_or_create_channel(self, channel_name):
        raise NotImplementedError

    def update_msg(self, ts, channel_id, new_msg):
        raise NotImplementedError
