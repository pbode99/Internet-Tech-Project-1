#!/usr/bin/env python3
import socket
import struct
import random
import json
import sys

# Example query spec as JSON
dns_query_spec = {
    "id": 1337,
    "qr": 0,      # query
    "opcode": 0,  # standard query
    "rd": 1,      # recursion desired
    "questions": [
        {
            "qname": "example.com",
            "qtype": 2,   # NS record
            "qclass": 1   # IN
        }
    ]
}


def build_query(query_spec):
    # Header fields
    ID = query_spec["id"]
    QR = query_spec["qr"] << 15
    OPCODE = query_spec["opcode"] << 11
    AA, TC = 0, 0
    RD = query_spec["rd"] << 8
    RA, Z, RCODE = 0, 0, 0
    flags = QR | OPCODE | AA | TC | RD | RA | Z | RCODE

    QDCOUNT = len(query_spec["questions"])
    ANCOUNT, NSCOUNT, ARCOUNT = 0, 0, 0

    header = struct.pack("!HHHHHH", ID, flags, QDCOUNT, ANCOUNT, NSCOUNT, ARCOUNT)

    # Question section
    question_bytes = b""
    for q in query_spec["questions"]:
        labels = q["qname"].split(".")
        for label in labels:
            question_bytes += struct.pack("B", len(label)) + label.encode()
        question_bytes += b"\x00"  # end of qname
        question_bytes += struct.pack("!HH", q["qtype"], q["qclass"])

    return header + question_bytes


def parse_name(data, offset):
    # Returns (name, offset just past the name), following compression pointers
    labels = []
    jumped = False
    end_offset = offset
    while True:
        length = data[offset]
        if (length & 0xC0) == 0xC0:  # pointer: first two bits 11
            if not jumped:
                end_offset = offset + 2
            offset = ((length & 0x3F) << 8) | data[offset + 1]
            jumped = True
        elif length == 0:
            if not jumped:
                end_offset = offset + 1
            break
        else:
            labels.append(data[offset + 1:offset + 1 + length].decode())
            offset += length + 1
    return ".".join(labels), end_offset


def parse_records(data, offset, count):
    records = []
    for _ in range(count):
        name, offset = parse_name(data, offset)
        atype, aclass, ttl, rdlength = struct.unpack("!HHIH", data[offset:offset+10])
        offset += 10
        rdata = data[offset:offset+rdlength]
        if atype == 1 and rdlength == 4:  # A record
            records.append({"name": name, "type": atype, "ip": socket.inet_ntoa(rdata), "ttl": ttl})
        elif atype == 28 and rdlength == 16:  # AAAA record
            records.append({"name": name, "type": atype, "ip": socket.inet_ntop(socket.AF_INET6, rdata), "ttl": ttl})
        elif atype == 2:  # NS record, rdata is a domain name
            ns_name, _ = parse_name(data, offset)
            records.append({"name": name, "type": atype, "ns": ns_name, "ttl": ttl})
        offset += rdlength
    return records, offset


def parse_response(data):
    response = {}
    (ID, flags, QDCOUNT, ANCOUNT, NSCOUNT, ARCOUNT) = struct.unpack("!HHHHHH", data[:12])

    response["id"] = ID
    response["qr"] = (flags >> 15) & 1
    response["opcode"] = (flags >> 11) & 0xF
    response["aa"] = (flags >> 10) & 1
    response["tc"] = (flags >> 9) & 1
    response["rd"] = (flags >> 8) & 1
    response["ra"] = (flags >> 7) & 1
    response["rcode"] = flags & 0xF
    response["qdcount"] = QDCOUNT
    response["ancount"] = ANCOUNT
    response["nscount"] = NSCOUNT
    response["arcount"] = ARCOUNT

    offset = 12
    # Skip questions
    for _ in range(QDCOUNT):
        _, offset = parse_name(data, offset)
        offset += 4  # qtype + qclass

    # Parse answer, authority, and additional sections
    response["answers"], offset = parse_records(data, offset, ANCOUNT)
    response["authority"], offset = parse_records(data, offset, NSCOUNT)
    response["additional"], offset = parse_records(data, offset, ARCOUNT)
    return response


def dns_query(query_spec, server=("8.8.8.8", 53)):
    query = build_query(query_spec)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)
    sock.sendto(query, server)
    data, _ = sock.recvfrom(512)
    sock.close()
    result=parse_response(data)
    if result["tc"] == 1:
        sys.exit("Error: response was truncated")
    if result["ra"] == 0:
        sys.exit("Error: server does not support recursion")
    return result


def query_ns(domain):
    query_spec = {
        "id": 1337,
        "qr": 0,
        "opcode": 0,
        "rd": 1,
        "questions": [
            {
                "qname": domain,
                "qtype": 2,   # NS record
                "qclass": 1
            }
        ]
    }
    response = dns_query(query_spec)
    # NS names can be in the answer or authority section
    ns_names = [r["ns"] for r in response["answers"] + response["authority"] if r["type"] == 2]
    # Match NS names with glue A/AAAA records in the additional section
    glue = {}
    for r in response["additional"]:
        if r["type"] in (1, 28):
            glue.setdefault(r["name"], []).append(r["ip"])
    response["nameservers"] = [{"ns": ns, "glue": glue.get(ns, [])} for ns in ns_names]
    return response


if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else "example.com"
    response = query_ns(domain)
    print(json.dumps(response, indent=2))
    with open("output_partB.txt", "w") as out:
        out.write(json.dumps(response, indent=2) + "\n")
