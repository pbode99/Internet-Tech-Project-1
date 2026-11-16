---
title: "CS 352 Project 3: Reliable UDP (RUDP)"
subtitle: "World Cup Live Scoreboard"
author:
  - "Peter Bode (NetID: pab282): client code, Wireshark captures"
  - "Adam Kurasinski (NetID: ak2779): server code"
geometry: margin=1in
fontsize: 11pt
---

# 1. Implementation Summary

All numbers below come from the recorded run (server seed 1, UDP port 30011), saved in `client_log.txt`, `server_log.txt` and the three pcap files.

## Handshake

The client picked **x = 2448259619** and the server picked **y = 1094907687**, both with `random.randint(0, 2**32 - 1)`.

1. Client sends SYN: seq = 2448259619.
2. Server sends SYN-ACK: seq = 1094907687, ack = 2448259620 (x + 1).
3. Client sends ACK: seq = 2448259620 (x + 1), ack = 1094907688 (y + 1).

The client accepts a SYN-ACK only if its flags are SYN|ACK and its ack equals x + 1. In this run the first SYN-ACK was dropped. The client timed out after 0.5 s and sent the SYN again. The server saw a duplicate SYN and resent the same SYN-ACK with the same y.

The server moves to ESTABLISHED when it gets an ACK with seq = x + 1 and ack = y + 1. The first DATA packet carries the same seq, ack and ACK flag, so it also completes the handshake if the final ACK is lost.

## Data Transfer (Stop-and-Wait)

The client sends each line of `match_feed.txt` as one DATA packet with the ACK flag and ack = y + 1. The first DATA has seq = x + 1. Each later seq is the previous seq plus the previous payload length, using `seq_add()` so values wrap at 2^32.

After sending DATA(seq = s, len = n), the client waits for an ACK with ack = s + n. ACKs with any other number are late replies and are ignored. If no matching ACK arrives within 0.5 s, the client resends. After 5 tries it prints an error and exits.

The server keeps `expect_seq`, which starts at x + 1. If a DATA packet has seq = expect_seq, the server passes it to `board.apply()` and adds its length to expect_seq. Any other DATA is a duplicate and is not delivered. In both cases the server replies with ack = expect_seq through `send_unreliable()`.

## Teardown

The client sends FIN with seq = 2448260738 (its current seq) and waits for a FIN-ACK with ack = 2448260739 (seq + 1). The server accepts the FIN only if its seq equals expect_seq. It then sends the FIN-ACK, calls `board.save()` and resets to LISTEN. The FIN-ACK is kept in `last_close`, so a repeated FIN from the same client gets the same FIN-ACK again.

## Result

The server printed `FINAL SCORE: ESP 1 ARG 0`, and `diff match_feed.txt received_feed.txt` printed nothing. The same result held for seeds 1, 2, 3, 4, 5, 7, 11 and 42.

# 2. Capture Analysis

## Hand-Decoded Header

Frame 3 of `project3_handshake.pcap` is the SYN-ACK. The UDP data starts at offset 0x2A. Its first 11 bytes are:

```
41 42 f7 27  91 ed 7a 24  03  00 00
```

The format `'!I I B H'` uses network byte order (big-endian), so the first byte of each field is the most significant.

| Bytes | Field | Hex         | Decimal    | Meaning                       |
|-------|-------|-------------|------------|-------------------------------|
| 0-3   | seq   | 41 42 F7 27 | 1094907687 | server ISN y                  |
| 4-7   | ack   | 91 ED 7A 24 | 2448259620 | x + 1                         |
| 8     | flags | 03          | 3          | SYN (0x01) + ACK (0x02)       |
| 9-10  | len   | 00 00       | 0          | no payload                    |

**seq:** 0x41 = 65, 0x42 = 66, 0xF7 = 247, 0x27 = 39

65 x 2^24 + 66 x 2^16 + 247 x 2^8 + 39 = 1090519040 + 4325376 + 63232 + 39 = **1094907687**

**ack:** 0x91 = 145, 0xED = 237, 0x7A = 122, 0x24 = 36

145 x 2^24 + 237 x 2^16 + 122 x 2^8 + 36 = 2432696320 + 15532032 + 31232 + 36 = **2448259620**

**flags:** 0x03 = 0000 0011 in binary. Bit 0x01 (SYN) and bit 0x02 (ACK) are set, so this is a SYN-ACK.

**len:** 0x0000 = 0, so the packet has no payload.

These values match the log line `[CLIENT] RECV seq=1094907687 ack=2448259620 flags=SYN|ACK len=0`.

## Retransmissions in project3_data.pcap

Wireshark shows every packet as plain UDP. A retransmission is a client packet whose UDP data is identical to an earlier one. For example, frames 1, 2 and 3 all begin with:

```
91 ed 7a 24  41 42 f7 28  02  00 3c
```

This is seq = x + 1, ack = y + 1, flags = ACK, len = 60 (the KICKOFF line). The three copies were sent at 0.000 s, 0.501 s and 1.002 s. The 0.5 s gap matches the RTO.

| Original frame | Repeated in frames | Gap     |
|----------------|--------------------|---------|
| 1              | 2, 3               | 0.5 s   |
| 9              | 11, 12             | 0.5 s   |
| 18             | 19                 | 0.5 s   |
| 27             | 28, 29             | 0.5 s   |
| 35             | 36                 | 0.5 s   |

Frames 10 and 58 are copies of earlier server ACKs that were held back by the simulated delay. Frame 10 arrived after the client had moved to the next packet, so its ack number did not match and the client logged it as stale and ignored it. Frame 58 arrived after the connection had already closed.

# 3. Discussion

## Why a dropped or delayed reply triggers a retransmission

The client cannot tell a lost DATA packet from a lost ACK. Either way, no matching ACK arrives in time. A reply delayed past the 0.5 s timeout looks the same as a lost one. The client assumes the data never arrived and sends it again. If the late reply shows up afterward, its ack number no longer matches, so it is ignored.

## Why the server must not deliver a duplicate

Retransmissions mean the server often receives the same DATA more than once. The scoreboard applies every event it is given. Delivering a repeated GOAL line would show Spain winning 2-0. Comparing seq to expect_seq lets the server skip repeats. It still sends an ACK for each repeat so the client can move on.

## Why ISNs are random rather than 0

If every connection started at 0, a delayed packet from an old connection could have a seq that looks valid in a new connection and be accepted by mistake. Random ISNs make that overlap very unlikely. They also make it hard for an attacker to guess the next sequence number and inject fake packets.
