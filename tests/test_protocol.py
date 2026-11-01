"""Tests du protocole WebSocket (spec/05-session-server, SRV-T3)."""

import json
import struct

from server.protocol import (
    MAX_IMAGE_BYTES,
    parse_binary,
    parse_client_message,
)


def test_valid_control_messages():
    assert parse_client_message({"type": "hello", "bike_id": "b-1", "access_code": "x",
                                 "client": {"ua": "a", "w": 1, "h": 2}})["type"] == "hello"
    assert parse_client_message('{"type": "start"}') == {"type": "start"}  # SRV-R3.1 : JSON texte
    assert parse_client_message({"type": "user_done", "t_ms": 1200})["t_ms"] == 1200
    assert parse_client_message({"type": "command", "cmd": "repeat", "t_ms": 3})["cmd"] == "repeat"
    assert parse_client_message({"type": "speaking", "on": True, "t_ms": 0})["on"] is True
    assert parse_client_message({"type": "pause"}) == {"type": "pause"}
    assert parse_client_message({"type": "stop"}) == {"type": "stop"}
    hello = parse_client_message({"type": "hello", "bike_id": "b-1", "client": {},
                                  "extra": 1})  # champs en plus permis
    assert hello["extra"] == 1


def test_invalid_control_messages_are_ignored():
    assert parse_client_message("{pas du json") is None
    assert parse_client_message("[1, 2]") is None
    assert parse_client_message({"no_type": 1}) is None
    assert parse_client_message({"type": "danse"}) is None
    assert parse_client_message({"type": "user_done"}) is None  # t_ms manquant
    assert parse_client_message({"type": "user_done", "t_ms": "12"}) is None  # mauvais type
    assert parse_client_message({"type": "user_done", "t_ms": True}) is None  # bool interdit
    assert parse_client_message({"type": "user_done", "t_ms": -5}) is None
    assert parse_client_message({"type": "command", "cmd": "danse", "t_ms": 1}) is None
    assert parse_client_message({"type": "speaking", "on": 1, "t_ms": 1}) is None
    assert parse_client_message({"type": "hello", "bike_id": "b-1", "client": "pas un objet"}) is None  # client facultatif, mais un objet s'il est là
    assert parse_client_message({"type": "hello", "bike_id": "b-1", "client": {},
                                 "access_code": 42}) is None


def test_binary_header_decoded():
    img = bytes([0x02]) + struct.pack(">Q", 12345) + b"\xff" * 10  # SRV-R3.2
    parsed = parse_binary(img)
    assert parsed["kind"] == "image" and parsed["t_ms"] == 12345
    assert parsed["payload"] == b"\xff" * 10 and parsed["too_big"] is False
    audio = bytes([0x01]) + struct.pack(">Q", 7) + b"\x00" * 3200
    assert parse_binary(audio)["kind"] == "audio"
    assert parse_binary(b"\x03" + struct.pack(">Q", 1) + b"x") is None  # type inconnu
    assert parse_binary(b"\x02\x00") is None  # trop court


def test_oversize_image_flagged():
    big = bytes([0x02]) + struct.pack(">Q", 9) + b"\xff" * (MAX_IMAGE_BYTES + 1)
    assert parse_binary(big)["too_big"] is True  # SRV-R3.3 : à ignorer
    limit = bytes([0x02]) + struct.pack(">Q", 9) + b"\xff" * MAX_IMAGE_BYTES
    assert parse_binary(limit)["too_big"] is False
    assert json.loads(json.dumps(parse_client_message({"type": "start"})))  # sérialisable
