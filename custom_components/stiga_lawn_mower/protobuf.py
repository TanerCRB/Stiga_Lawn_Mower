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


def decode_protobuf_repeated(data: bytes) -> dict[int, list]:
    """Decode a protobuf message collecting repeated fields as lists."""
    fields: dict[int, list] = {}
    pos = 0
    while pos < len(data):
        tag, pos = _decode_varint(data, pos)
        field_number = tag >> 3
        wire_type = tag & 0x7
        if wire_type == 0:
            value, pos = _decode_varint(data, pos)
            fields.setdefault(field_number, []).append(value)
        elif wire_type == 2:
            length, pos = _decode_varint(data, pos)
            if pos + length > len(data):
                break
            fields.setdefault(field_number, []).append(data[pos : pos + length])
            pos += length
        elif wire_type == 1:
            if pos + 8 > len(data):
                break
            fields.setdefault(field_number, []).append(
                int.from_bytes(data[pos : pos + 8], "little")
            )
            pos += 8
        elif wire_type == 5:
            if pos + 4 > len(data):
                break
            fields.setdefault(field_number, []).append(
                int.from_bytes(data[pos : pos + 4], "little")
            )
            pos += 4
        else:
            break
    return fields


def _set_varint_in_submessage(data: bytes, field_num: int, value: int) -> bytes:
    """Replace or append a varint field within protobuf sub-message bytes."""
    parts: list[bytes] = []
    pos = 0
    replaced = False
    while pos < len(data):
        tag_start = pos
        tag, pos = _decode_varint(data, pos)
        fn = tag >> 3
        wt = tag & 0x7
        if wt == 0:
            _, pos = _decode_varint(data, pos)
            if fn == field_num and not replaced:
                parts.append(_encode_varint_field(field_num, value))
                replaced = True
            else:
                parts.append(data[tag_start:pos])
        elif wt == 2:
            length, pos = _decode_varint(data, pos)
            end = pos + length
            parts.append(data[tag_start:end])
            pos = end
        elif wt == 1:
            parts.append(data[tag_start : pos + 8])
            pos += 8
        elif wt == 5:
            parts.append(data[tag_start : pos + 4])
            pos += 4
        else:
            parts.append(data[tag_start:])
            break
    if not replaced:
        parts.append(_encode_varint_field(field_num, value))
    return b"".join(parts)


def patch_zone_cutting_mode(data: list[int], zone_id: int, mode_value: int) -> list[int]:
    """Patch cuttingMode (field 8) for zone_id in a data_points.data byte list.

    Outer layout: field 1 = repeated zone sub-messages.
    Each sub-message: field 1 = zone id (varint), field 8 = cuttingMode (varint).
    All other bytes are copied verbatim.
    """
    buf = bytes(data)
    out: list[bytes] = []
    pos = 0
    found = False
    while pos < len(buf):
        tag_start = pos
        tag, pos = _decode_varint(buf, pos)
        fn = tag >> 3
        wt = tag & 0x7
        if wt == 2:
            length, pos = _decode_varint(buf, pos)
            val_end = pos + length
            sub = buf[pos:val_end]
            if fn == 1 and not found:
                sub_fields = decode_protobuf(sub)
                if sub_fields.get(1) == zone_id:
                    new_sub = _set_varint_in_submessage(sub, 8, mode_value)
                    out.append(_encode_varint((fn << 3) | 2))
                    out.append(_encode_varint(len(new_sub)))
                    out.append(new_sub)
                    pos = val_end
                    found = True
                    continue
            out.append(buf[tag_start:val_end])
            pos = val_end
        elif wt == 0:
            _, pos = _decode_varint(buf, pos)
            out.append(buf[tag_start:pos])
        elif wt == 1:
            if pos + 8 > len(buf):
                break
            out.append(buf[tag_start : pos + 8])
            pos += 8
        elif wt == 5:
            if pos + 4 > len(buf):
                break
            out.append(buf[tag_start : pos + 4])
            pos += 4
        else:
            out.append(buf[tag_start:])
            break
    if not found:
        raise ValueError(f"Zone {zone_id} not found in perimeter data_points")
    return list(b"".join(out))


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
