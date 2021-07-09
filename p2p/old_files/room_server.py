from socket import (socket, AF_INET,
                    SOCK_STREAM,
                    SOL_SOCKET,
                    SO_REUSEADDR,
                    getaddrinfo)


conn_socket = socket(AF_INET, SOCK_STREAM)
conn_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
conn_socket.bind(('', 6660))
conn_socket.listen()