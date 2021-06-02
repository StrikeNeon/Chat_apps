from datetime import datetime
from socket import (socket, AF_INET,
                    SOCK_STREAM,
                    SOL_SOCKET,
                    SO_REUSEADDR)
import json
import logging
from logging.handlers import TimedRotatingFileHandler
import threading


def configure_logger():
    logger = logging.getLogger(__name__)
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', encoding='utf-8', level=logging.DEBUG)
    handler = TimedRotatingFileHandler("server_log.log",
                                       when="h",
                                       interval=24,
                                       backupCount=5)
    logger.addHandler(handler)
    return logger


logger = configure_logger()


def init_decode(message, socket):
    try:
        logging.info(f"recieved data at {socket.getpeername()}")
        decoded_data = json.loads(message.decode("utf-8"))
        if decoded_data.get("user"):
            return decoded_data
        else:
            logger.warning(f"valid json recieved, no user key found at socket {socket.getpeername()}")
    except UnicodeDecodeError:
        logger.warning(f"malformed data at {socket.getpeername()}")
    except json.JSONDecodeError:
        logger.warning(f"malformed json at {socket.getpeername()}")


def send_probe(socket):
    logging.info(f"sending probe to {socket.getpeername()}")
    probe = json.dumps({"action": "probe",
                        "time": datetime.now().timestamp(),
                        }).encode("utf-8")
    socket.send(probe)
    logger.info(f"sent a presence message to {socket.getpeername()}")


#TODO: exit program when client ends the connection
def connect(conn):
    while True:
        received = conn.recv(1024)
        if received == ' ':
            pass
        else:
            print(received.decode())


def sendMsg(conn):
    while True:
        send_msg = input().replace('b', '').encode()
        if send_msg == ' ':
            pass
        else:
            conn.sendall(send_msg)


def setup(port):
    s = socket(AF_INET, SOCK_STREAM)
    s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    s.bind(('', port))
    s.listen()
    (conn, addr) = s.accept()
    thread1 = threading.Thread(target=connect, args=([conn]))
    thread2 = threading.Thread(target=sendMsg, args=([conn]))
    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()
