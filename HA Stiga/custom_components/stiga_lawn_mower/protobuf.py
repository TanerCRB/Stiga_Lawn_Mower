"""Minimal protobuf encoder/decoder for Stiga MQTT messages."""
from __future__ import annotations


def _encode_varint(value: int) -> bytes:
    bits = []
    while True:
        towrite = value & 0x7F
        value >>= 7
        if value:
            bits.append(towrite | 0x80)
        else:
            bits.append(towrite)
            break
    return bytes(bits)


def _encode_varint_field(field_number: int, value: int) -> bytes:
    tag = (field_number << 3) | 0  # wire type 0 = varint
    return _encode_varint(tag) + _encode_varint(value)


def _encode_length_delimited_field(field_number: int, value: bytes) -> bytes:
    tag = (field_number << 3) | 2  # wire type 2 = length-delimited
    return _encode_varint(tag) + _encode_varint(len(value)) + value


def encode_status_request_fields(
    battery: bool = True,
    mowing: bool = True,
    location: bool = True,
    network: bool = True,
) -> bytes:
    """Encode the status request sub-message {battery:1, mowing:2, location:3, network:4}."""
    result = b""
    if battery:
        result += _encode_varint_field(1, 1)
    if mowing:
        result += _encode_varint_field(2, 1)
    if location:
        result += _encode_varint_field(3, 1)
    if network:
        result += _encode_varint_field(4, 1)
    return result


def encode_robot_command(command_type: int, fields: bytes | None = None) -> bytes:
    """Encode a robot command: { 1: cmd_type, [2: fields], 3: cmd_type }.

    Fields is an optional nested protobuf sub-message (e.g. status request types).
    Matches JS: encodeRobotCommand(type, fields) in StigaAPIElements.js.
    """
    payload = _encode_varint_field(1, command_type)
    if fields is not None:
        payload += _encode_length_delimited_field(2, fields)
    payload += _encode_varint_field(3, command_type)
    return payload


def encode_protobuf(fields: dict) -> bytes:
    """General-purpose protobuf encoder.

    Values can be int (varint), dict (nested message), or bytes (raw length-delimited).
    """
    result = b""
    for field_num in sorted(fields):
        value = fields[field_num]
        if isinstance(value, bool):
            result += _encode_varint_field(field_num, int(value))
        elif isinstance(value, int):
            result += _encode_varint_field(field_num, value)
        elif isinstance(value, dict):
            result += _encode_length_delimited_field(field_num, encode_protobuf(value))
        elif isinstance(value, (bytes, bytearray)):
            result += _encode_length_delimited_field(field_num, bytes(value))
    return result


def _decode_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if not (byte & 0x80):
            break
    return result, pos


def decode_protobuf(data: bytes) -> dict[int, int | bytes]:
    """Decode a protobuf message into {field_number: value} dict."""
    fields: dict[int, int | bytes] = {}
    pos = 0
    while pos < len(data):
        tag, pos = _decode_varint(data, pos)
        field_number = tag >> 3
        wire_type = tag & 0x7

        if wire_type == 0:  # varint
            value, pos = _decode_varint(data, pos)
            fields[field_number] = value
        elif wire_type == 2:  # length-delimited (string, bytes, nested message)
            length, pos = _decode_varint(data, pos)
            if pos + length > len(data):
                break
            fields[field_number] = data[pos : pos + length]
            pos += length
        elif wire_type == 1:  # 64-bit fixed
            if pos + 8 > len(data):
                break
            fields[field_number] = int.from_bytes(data[pos : pos + 8], "little")
            pos += 8
        elif wire_type == 5:  # 32-bit fixed
            if pos + 4 > len(data):
                break
            fields[field_number] = int.from_bytes(data[pos : pos + 4], "little")
            pos += 4
        else:
            break  # unknown wire type, stop parsing
    return fields
