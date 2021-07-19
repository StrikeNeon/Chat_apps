from threading import Thread
from main_server_logic import room_server

server = room_server(ip="127.0.0.1")
room_thread = Thread(target=server.room_service, args=())
room_thread.start()
room_thread.join()
