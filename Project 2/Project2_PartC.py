#!/usr/bin/env python3
import socket
import struct
import random
import json

ROOT_SERVERS = [
    "198.41.0.4", # a.root-servers.net
    "199.9.14.201", # b.root-servers.net
    "192.33.4.12", # c.root-servers.net
]

# Example query spec as JSON
dns_query_spec = {
   "id": 1337,
    "qr": 0,      # query
    "opcode": 0,  # standard query
    "rd": 0,      # recursion desired
    "questions": [
        {
            "qname": "www.example.com",
            "qtype": 1,   # A  record
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
    labels = []
    jumped = False
    original_offset = offset

    while True:
        length = data[offset]
        if length == 0:
            offset += 1
            break
        # pointer
        if (length & 0xC0) == 0xC0:
            if not jumped:
                original_offset = offset + 2
            pointer = struct.unpack("!H", data[offset:offset+2])[0]
            offset = pointer & 0x3FFF
            jumped = True
            continue
        labels.append(data[offset+1:offset+1+length].decode())
        offset += length + 1

    if not jumped:
        return ".".join(labels), offset
    else:
        return ".".join(labels), original_offset

def parse_rr(data, offset):
    """Parse a single resource record and return record + new offset."""
    name, offset = parse_name(data, offset)
    atype, aclass, ttl, rdlength = struct.unpack("!HHIH", data[offset:offset+10])
    offset += 10
    rdata = data[offset:offset+rdlength]
    record={
        "hostname": name, 
        "ttl":      ttl, 
        "atype":    atype, 
        "rtype":    None, 
        "ip":       None, 
        "nsname":   None
    }
    match atype:
        case 1:   # A record
            record["rtype"] = "A"
            record["ip"] = socket.inet_ntoa(rdata)
        case 2:   # NS record
            record["rtype"] = "NS"
            record["nsname"], _ = parse_name(data, offset)
        case 28:  # AAAA record
            record["rtype"] = "AAAA"
            record["ip"] = socket.inet_ntop(socket.AF_INET6, rdata)
        case _:   # Unhandled record types
            pass
    offset += rdlength
    return record,offset


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
        while data[offset] != 0:
            offset += data[offset] + 1
        offset += 1
        offset += 4  # qtype + qclass

    # Parse Answer RRs
    answers = []
    for _ in range(ANCOUNT):
        rr, offset = parse_rr(data, offset)
        answers.append(rr)

    # Parse Authority RRs
    authorities = []
    for _ in range(NSCOUNT):
        rr, offset = parse_rr(data, offset)
        authorities.append(rr)

    # Parse Additional RRs
    additionals = []
    for _ in range(ARCOUNT):
        rr, offset = parse_rr(data, offset)
        additionals.append(rr)    

    response["answers"] = answers
    response["authorities"] = authorities
    response["additionals"] = additionals
    return response



def dns_query(query_spec, server=("8.8.8.8", 53)):
    query = build_query(query_spec)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)
    sock.sendto(query, server)
    data, _ = sock.recvfrom(512)
    sock.close()
    return parse_response(data)

def iterative_resolve(query_spec):
    # convert string input to query
    if isinstance(query_spec, str):
        query_spec = {
            "id": 1337,
            "qr": 0,
            "opcode": 0,
            "rd": 0,
            "questions": [{"qname": query_spec, "qtype": 1, "qclass": 1}]
        }
    current_server = ROOT_SERVERS[0]
    while True:
        response = dns_query(query_spec, server=(current_server, 53))
        # Check for Truncation flag or DNS Error Response
        if response["tc"] == 1:
            print("[Warning] Truncated response received (TC = 1). Proceeding with available glue records.")
        if response["rcode"] != 0:
            raise RuntimeError(f"Server returned error RCODE {response['rcode']}")
        # 1. Answer received
        if response["ancount"] > 0:
            return response
        # 2. Referral received
        if response["nscount"] > 0:
            target_ns = response["authorities"][0]["nsname"]
            # Look up matching glue IP in Additional records
            glue_ip = None
            for add in response["additionals"]:
                if add["atype"] == 1 and add["hostname"] == target_ns:
                    glue_ip = add["ip"]
                    break
            if not glue_ip:
                raise RuntimeError(f"Glue record missing for NS: {target_ns}")
            current_server = glue_ip
        else:
            raise RuntimeError("No answer received and no further delegation available.")

    return None
        
if __name__ == "__main__":
    response = iterative_resolve(dns_query_spec)
    print(json.dumps(response, indent=2))
    with open("output_partC.txt", "w") as f:
        json.dump(response, f, indent=2)
    print("Response saved to output_partC.txt")
