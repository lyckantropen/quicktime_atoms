"""Definitions of some atoms that are needed for extracting track size and sample rate."""

from __future__ import annotations

from dataclasses import dataclass, field
from struct import unpack
from typing import List


def to_fixed_point(integer_value: int, base: int = 32) -> float:
    """Convert an integer to a fixed-point value."""
    fractional_bits = base // 2
    fixed_point_value = integer_value / (1 << fractional_bits)
    return fixed_point_value


@dataclass
class TkhdAtom:
    """Track header atom."""

    version: int
    flags: int
    creation_time: int
    modification_time: int
    track_id: int
    duration: int
    layer: int
    alternate_group: int
    volume: float
    matrix: bytes
    width: float
    height: float

    @classmethod
    def from_payload_bytes(cls, payload: bytes) -> TkhdAtom:
        version, flags, creation_time, modification_time, track_id, duration, layer, alternate_group, volume, matrix, width, height =\
            unpack('>B3sIII4xI8xHHH2x36sII', payload[:84])
        return cls(version,
                   int.from_bytes(flags),
                   creation_time,
                   modification_time,
                   track_id,
                   duration,
                   layer,
                   alternate_group,
                   to_fixed_point(volume, 16),
                   matrix,
                   to_fixed_point(width, 32),
                   to_fixed_point(height, 32))


@dataclass
class HdlrAtom:
    """Handler reference atom."""

    version: int
    flags: int
    component_type: str
    component_subtype: str
    component_manufacturer: str
    component_flags: int
    component_flags_mask: int

    @classmethod
    def from_payload_bytes(cls, payload: bytes) -> HdlrAtom:
        version, flags, component_type, component_subtype, component_manufacturer, component_flags, component_flags_mask = unpack('>B3s4s4s4sII', payload[:24])
        return cls(version,
                   int.from_bytes(flags),
                   component_type.decode('ascii'),
                   component_subtype.decode('ascii'),
                   component_manufacturer.decode('ascii'),
                   component_flags,
                   component_flags_mask)


@dataclass
class StsdSoundSampleDesc:
    """Sound sample description atom."""

    sample_description_size: int
    data_format: int
    data_reference_index: int
    version: int
    revision_level: int
    vendor: int
    number_of_channels: int
    sample_size: int
    compression_id: int
    packet_size: int
    sample_rate: float
    _size: int = field(init=False, default=36)

    @classmethod
    def from_payload_bytes(cls, payload: bytes) -> StsdSoundSampleDesc:
        sample_description_size, data_format, data_reference_index, version, \
            revision_level, vendor, number_of_channels, sample_size, compression_id, packet_size, sample_rate = \
            unpack('>II6xHHHIHHHHI', payload[:36])
        return cls(sample_description_size,
                   data_format,
                   data_reference_index,
                   version,
                   revision_level,
                   vendor,
                   number_of_channels,
                   sample_size,
                   compression_id,
                   packet_size,
                   to_fixed_point(sample_rate, 32))


@dataclass
class StsdSoundAtom:
    """Sound sample description atom."""

    version: int
    flags: int
    number_of_entries: int
    sample_desc: List[StsdSoundSampleDesc] = field(default_factory=list)

    @classmethod
    def from_payload_bytes(cls, payload: bytes) -> StsdSoundAtom:
        version, flags, number_of_entries = unpack('>B3sI', payload[:8])
        sample_desc = []
        pos = 8
        for _ in range(number_of_entries):
            sample_desc.append(StsdSoundSampleDesc.from_payload_bytes(payload[pos:]))
            pos += sample_desc[-1]._size
        return cls(version, int.from_bytes(flags), number_of_entries, sample_desc)
