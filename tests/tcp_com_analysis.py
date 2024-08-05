import socket
import logging
logging.basicConfig(
    format="{asctime} - {levelname} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO
    )

IP_ADDRESS = '192.168.178.85'
PORT = 5100


def prettify_hex(data) -> str:
    result = []
    for d in data:
        h = str(hex(d))[2:]
        if len(h) == 1:
            h = "0" + h
        result.append(h)
    return ":".join(result)

def tcp_client(server_ip, server_port) -> None:
    # Erstellen eines TCP/IP-Sockets
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        # Verbinden mit dem Server
        client_socket.connect((server_ip, server_port))
        logging.info(f"Connection established to {server_ip}:{server_port}")

        while True:
            # Antwort vom Server empfangen
            data = client_socket.recv(1024)
            # data_in_hex = hex(int.from_bytes(data, "big"))

            if data[0] != 0x55:
                logging.warning(f"Invalid ESP3 telegram: { prettify_hex(data) }")
            else:
                logging.info(f"Received data: { prettify_hex(data) }")

    
    finally:
        # Verbindung schließen
        client_socket.close()
        logging.info("Connection closed")

# Beispielaufruf
tcp_client(IP_ADDRESS, PORT)