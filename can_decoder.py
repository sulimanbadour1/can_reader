#!/usr/bin/env python3
# CAN Message Decoder
# Converts raw CAN bytes into voltage, temperature, etc.

from typing import Dict, List, Callable
import struct


class SignalDefinition:
    """Defines how to decode a signal from CAN data"""
    
    def __init__(self, name: str, start_bit: int, length: int, 
                 scale: float = 1.0, offset: float = 0.0,
                 is_signed: bool = True, is_little_endian: bool = True,
                 unit: str = ""):
        self.name = name
        self.start_bit = start_bit
        self.length = length
        self.scale = scale
        self.offset = offset
        self.is_signed = is_signed
        self.is_little_endian = is_little_endian
        self.unit = unit


class CANDecoder:
    """Decodes CAN messages into real values"""
    
    def __init__(self):
        self.signal_definitions: Dict[int, List[SignalDefinition]] = {}
        self.custom_decoders: Dict[int, Callable] = {}
    
    def add_signal_definition(self, can_id: int, signal: SignalDefinition):
        """Add a decoder for a CAN ID"""
        if can_id not in self.signal_definitions:
            self.signal_definitions[can_id] = []
        self.signal_definitions[can_id].append(signal)
    
    def add_custom_decoder(self, can_id: int, decoder_func: Callable):
        """Add a custom decoder function"""
        self.custom_decoders[can_id] = decoder_func
    
    def decode_message(self, can_id: int, data: bytes) -> Dict[str, float]:
        """Decode a CAN message into physical values"""
        decoded = {}
        
        # Check for custom decoder first
        if can_id in self.custom_decoders:
            return self.custom_decoders[can_id](data)
        
        # Use signal definitions
        if can_id in self.signal_definitions:
            for signal in self.signal_definitions[can_id]:
                try:
                    value = self._extract_signal(data, signal)
                    decoded[signal.name] = value
                except Exception as e:
                    decoded[signal.name] = None
        
        return decoded
    
    def _extract_signal(self, data: bytes, signal: SignalDefinition) -> float:
        """Extract a signal value from CAN data bytes"""
        start_byte = signal.start_bit // 8
        start_bit_in_byte = signal.start_bit % 8
        end_bit = signal.start_bit + signal.length
        end_byte = (end_bit - 1) // 8
        
        # Make sure we have enough data
        if end_byte >= len(data):
            return 0.0
        
        # Extract the bits
        if signal.is_little_endian:
            # Little endian: bytes in order
            value = 0
            bit_pos = 0
            for byte_idx in range(start_byte, end_byte + 1):
                byte_val = data[byte_idx]
                for bit_idx in range(8):
                    global_bit = byte_idx * 8 + bit_idx
                    if global_bit >= signal.start_bit and global_bit < signal.start_bit + signal.length:
                        if byte_val & (1 << bit_idx):
                            value |= (1 << bit_pos)
                        bit_pos += 1
        else:
            # Big endian: reverse byte order
            value = 0
            bit_pos = 0
            for byte_idx in range(end_byte, start_byte - 1, -1):
                byte_val = data[byte_idx]
                for bit_idx in range(7, -1, -1):
                    global_bit = byte_idx * 8 + (7 - bit_idx)
                    if global_bit >= signal.start_bit and global_bit < signal.start_bit + signal.length:
                        if byte_val & (1 << bit_idx):
                            value |= (1 << bit_pos)
                        bit_pos += 1
        
        # Handle signed values
        if signal.is_signed and value >= (1 << (signal.length - 1)):
            value -= (1 << signal.length)
        
        # Apply scale and offset
        physical_value = (value * signal.scale) + signal.offset
        
        return physical_value
    
    def get_available_signals(self, can_id: int) -> List[str]:
        """Get list of signal names for a CAN ID"""
        signals = []
        if can_id in self.signal_definitions:
            signals = [s.name for s in self.signal_definitions[can_id]]
        return signals


# Helper functions for common signals
def decode_voltage_8bit(data: bytes, byte_index: int = 0, scale: float = 0.1) -> float:
    """Decode voltage from 8-bit value"""
    if len(data) > byte_index:
        return data[byte_index] * scale
    return 0.0


def decode_voltage_16bit(data: bytes, byte_index: int = 0, scale: float = 0.01, 
                         offset: float = 0.0, little_endian: bool = True) -> float:
    """Decode voltage from 16-bit value"""
    if len(data) >= byte_index + 2:
        if little_endian:
            value = struct.unpack('<H', data[byte_index:byte_index+2])[0]
        else:
            value = struct.unpack('>H', data[byte_index:byte_index+2])[0]
        return (value * scale) + offset
    return 0.0


def decode_temperature_8bit(data: bytes, byte_index: int = 0, scale: float = 1.0, 
                           offset: float = -40.0) -> float:
    """Decode temperature from 8-bit value"""
    if len(data) > byte_index:
        return (data[byte_index] * scale) + offset
    return 0.0


def decode_temperature_16bit(data: bytes, byte_index: int = 0, scale: float = 0.1,
                             offset: float = -40.0, little_endian: bool = True) -> float:
    """Decode temperature from 16-bit value"""
    if len(data) >= byte_index + 2:
        if little_endian:
            value = struct.unpack('<h', data[byte_index:byte_index+2])[0]
        else:
            value = struct.unpack('>h', data[byte_index:byte_index+2])[0]
        return (value * scale) + offset
    return 0.0


def decode_current_16bit(data: bytes, byte_index: int = 0, scale: float = 0.01,
                        offset: float = -327.68, little_endian: bool = True) -> float:
    """Decode current from 16-bit signed value"""
    if len(data) >= byte_index + 2:
        if little_endian:
            value = struct.unpack('<h', data[byte_index:byte_index+2])[0]
        else:
            value = struct.unpack('>h', data[byte_index:byte_index+2])[0]
        return (value * scale) + offset
    return 0.0
