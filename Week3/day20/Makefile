CC = gcc
CFLAGS = -O2 -Wall -Wextra -std=c11
LIBS = -loqs -lcrypto -lpthread

all: server client

server: server.c common.h
	$(CC) $(CFLAGS) -o server server.c $(LIBS)

client: client.c common.h
	$(CC) $(CFLAGS) -o client client.c $(LIBS)

clean:
	rm -f server client server_dsa_pub.key
