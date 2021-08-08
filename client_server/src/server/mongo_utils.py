from pymongo import MongoClient, ReturnDocument
import loguru
from passlib.exc import UnknownHashError
from jose import JWTError, jwt
from datetime import timedelta, datetime
from settings import pwd_context, SECRET_KEY, ALGORITHM


class MongoManager():
    """This class has all the code for db-relevant operations in the project,
       also sec operations are here for now"""
    def __init__(self):
        """sets up a mongo connection, specifies db name,
           room and user collection names"""
        self.client = MongoClient('127.0.0.1:27017')

        self.db = self.client['chat_apps']
        self.room_collection = self.db['client-server_rooms']
        self.user_collection = self.db['client-server_users']
        self.archive_collection = self.db['client-server_archival']

        self.db_logger = loguru.logger

    def get_password_hash(self, password):
        """hashes the plain password according to pwd context"""
        return pwd_context.hash(password)

    def verify_password(self, plain_password, hashed_password):
        """verifies plain password to a hashed one"""
        try:
            verification = pwd_context.verify(plain_password, hashed_password)
            return verification
        except UnknownHashError:
            return 403

    def verify_token(self, token: str):
        """decodes jwt and verifies user data"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                return 403
        except JWTError:
            return 403
        user = self.user_collection.find_one({"username": username})
        if user is None:
            403
        return user

    def create_access_token(self, data: dict, expires_delta: timedelta = 30):
        """creates jwt token from username and expiry"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def add_room(self, room):
        """adds a room structure to db
        default is empty blacklist, whitelist and a black users dict"""
        added_room = self.room_collection.insert_one({"ROOM": room, "Blacklist": [], "Whitelist": [], "Users": {}}).inserted_id
        self.db_logger.info(f"created room records, room № {room}")
        return added_room

    def remove_room(self, room):
        """removes room record form db"""
        self.room_collection.find_one_and_delete({"ROOM": room})
        self.db_logger.info(f"deleted records, room № {room}")

    def add_user(self, username, password, about_me):
        """adds a user record to db if username is unique"""
        user_check = self.user_collection.find_one({"username": username})
        if not user_check:
            added = self.user_collection.insert_one({"username": username, "password": self.get_password_hash(password), "about_me": about_me, "contacts": []})
            return added
        else:
            return None

    def check_user(self, username, password):
        """checks if user-sent password matches the hashed stored one"""
        user_check = self.user_collection.find_one({"username": username})
        if user_check:
            self.db_logger.debug(f"found user {username}")
            if self.verify_password(password, user_check["password"]):
                return user_check
            else:
                self.db_logger.info(f"failed, user: {user_check.get('username')} wrong password")

    def add_user_to_room(self, user_ip, username, room_port, users):
        """adds a user to room record, returns the updated users dict and updated record"""
        users[username] = {"user_location": user_ip, "username": username}
        updated = self.room_collection.find_one_and_update({"ROOM": room_port}, {'$set': {"Users": users}}, return_document=ReturnDocument.AFTER)
        room_zero = self.room_collection.find_one({"ROOM": 0})
        current_users = room_zero.get("Users")
        self.db_logger.debug(room_port)
        current_users[username] = room_port
        self.room_collection.find_one_and_update({"ROOM": 0}, {'$set': {"Users": current_users}})
        return users, updated

    def remove_user_from_room(self, user_ip, room_port, users):
        """removes user from room if user is found"""
        self.db_logger.debug(users)
        for username, location in users.items():
            if tuple(location) == user_ip:
                to_delete = username
                break
        users.pop(to_delete)
        updated = self.room_collection.find_one_and_update({"ROOM": room_port}, {'$set': {"Users": users}}, return_document=ReturnDocument.AFTER)
        self.db_logger.debug(f"after cleaning {updated}")
        room_zero = self.room_collection.find_one({"ROOM": 0})
        current_users = room_zero.get("Users")
        try:
            current_users.pop(to_delete)
            self.room_collection.find_one_and_update({"ROOM": 0}, {'$set': {"Users": current_users}})
            return users, to_delete
        except KeyError:
            return users, None

    def delete_user(self, username):
        """deleted a user record from db"""
        self.user_collection.delete_one({"username": username})
        self.db_logger.info(f"deleted user {username}")

    def add_to_contacts(self, username, other_username):
        """adds a user to another user's contact list if new user is not in contacts"""
        user_contacts = self.user_collection.find_one({"username": username})
        if other_username not in user_contacts.get("contacts"):
            updated = self.user_collection.find_one_and_update({"username": username}, {'$push': {"contacts": other_username}}, return_document=ReturnDocument.AFTER)
            return updated
        else:
            return user_contacts

    def remove_from_contacts(self, username, other_username):
        """removes a user to another user's contact list"""
        updated = self.user_collection.find_one_and_update({"username": username}, {'$pull': {"contacts": other_username}}, return_document=ReturnDocument.AFTER)
        return updated

    def get_contacts(self, username):
        """get a user's contact list"""
        user_data = self.user_collection.find_one({"username": username})
        if user_data:
            contacts = user_data.get("contacts")
            return contacts

    def find_users(self, usernames):
        """find which rooms are users from supplied list in"""
        users_data = self.room_collection.find_one({"ROOM": 0}).get("Users")
        self.db_logger.debug("user found")
        if users_data:
            locations = []
            for user in usernames:
                user_location = users_data.get(user)
                if user_location:
                    locations.append(str(user_location))
            self.db_logger.debug(locations)
            return locations

    def find_user_record(self, username):
        """get user's profile data"""
        user_data = self.user_collection.find_one({"username": username})
        if user_data:
            info = user_data.get("about_me")
            return info
        else:
            return 404

    def get_room_data(self):
        """get the amount of users in each active room except for room sero"""
        rooms = self.room_collection.find({"ROOM": {"$ne":0}})
        if rooms:
            room_data = {}
            for room in rooms:
                room_data[room.get("ROOM")] = len(room.get("Users"))
            return room_data
        else:
            return 500

    def flush_room_zero(self):
        """resets the room zero record"""
        old_room = self.room_collection.find_one({"ROOM": 0})
        if old_room:
            self.room_collection.find_one_and_update({"ROOM": 0}, {"$set": {"Users": {}}})
            self.db_logger.info("created room records, room 0")
        else:
            self.room_collection.insert_one({"ROOM": 0, "Blacklist": [], "Whitelist": [], "Users": {}})
            self.db_logger.info("created room records, room 0")
