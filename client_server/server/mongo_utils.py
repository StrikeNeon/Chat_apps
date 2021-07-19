from pymongo import MongoClient, ReturnDocument
import loguru


class mongo_manager():
    def __init__(self):
        self.client = MongoClient('127.0.0.1:27017')

        self.db = self.client['chat_apps']
        self.room_collection = self.db['client-server_rooms']
        self.user_collection = self.db['client-server_users']
        self.archive_collection = self.db['client-server_archival']

        self.db_logger = loguru.logger

    def add_room(self, room):
        added_room = self.room_collection.insert_one({"ROOM": room, "Blacklist": [], "Whitelist": [], "Users": {}}).inserted_id
        self.db_logger.info(f"created room records, room № {room}")
        return added_room

    def remove_room(self, room):
        self.room_collection.delete_one({"ROOM": room})
        self.db_logger.info(f"deleted records, room № {room}")

    def add_user(self, username, password, user_data):
        user_check = self.user_collection.find_one({"username": username})
        if not user_check:
            added = self.user_collection.insert_one({"username": username, "password": password, "info": user_data, "contacts": []})
            return added
        else:
            return None

    def check_user(self, username, password):
        user_check = self.user_collection.find_one({"username": username})
        if user_check:
            self.db_logger.debug(f"found user {username}")
            if user_check.get("username") == username and user_check.get("password") == password:
                return True
            else:
                self.db_logger.info(f"failed, recorded name: {user_check.get('username')} supplied name: {username}, recorded password: {user_check.get('password')} supplied password: {password}")

    def add_user_to_room(self, user_ip, username, room_port, users):
        users[username] = {"user_location": user_ip, "username": username}
        updated = self.room_collection.find_one_and_update({"ROOM": room_port}, {'$set': {"Users": users}}, return_document=ReturnDocument.AFTER)
        room_zero = self.room_collection.find_one({"ROOM": 0})
        current_users = room_zero.get("Users")
        self.db_logger.debug(room_port)
        current_users[username] = room_port
        self.room_collection.find_one_and_update({"ROOM": 0}, {'$set': {"Users": current_users}})
        return users, updated

    def remove_user_from_room(self, user_ip, room_port, users):
        self.db_logger.debug(user_ip)
        for user in users.values():
            if tuple(user.get("user_location")) == user_ip:
                to_delete = user.get("username")
                break
        users.pop(to_delete)
        updated = self.room_collection.find_one_and_update({"ROOM": room_port}, {'$set': {"Users": users}}, return_document=ReturnDocument.AFTER)
        self.db_logger.debug(f"after cleaning {updated}")
        room_zero = self.room_collection.find_one({"ROOM": 0})
        current_users = room_zero.get("Users")
        current_users.pop(to_delete)
        self.room_collection.find_one_and_update({"ROOM": 0}, {'$set': {"Users": current_users}})
        return users, to_delete

    def delete_user(self, username):
        self.user_collection.delete_one({"username": username})
        self.db_logger.info(f"deleted user {username}")

    def add_to_contacts(self, username, other_username):
        updated = self.user_collection.find_one_and_update({"username": username}, {'$push': {"contacts": other_username}}, return_document=ReturnDocument.AFTER)
        return updated

    def remove_from_contacts(self, username, other_username):
        updated = self.user_collection.find_one_and_update({"username": username}, {'$pull': {"contacts": other_username}}, return_document=ReturnDocument.AFTER)
        return updated

    def flush_room_zero(self):
        old_room = self.room_collection.find_one({"ROOM": 0})
        if old_room:
            self.room_collection.find_one_and_update({"ROOM": 0}, {"$set": {"Users": {}}})
            self.db_logger.info("created room records, room 0")
        else:
            self.room_collection.insert_one({"ROOM": 0, "Blacklist": [], "Whitelist": [], "Users": {}})
            self.db_logger.info("created room records, room 0")