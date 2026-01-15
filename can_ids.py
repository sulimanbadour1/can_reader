#!/usr/bin/env python3
# CAN ID Definitions
# Predefined CAN IDs for the system

# CAN ID constants
CAN_ID_KEEP_ALIVE = 600
CAN_ID_AIN1_4 = 601
CAN_ID_AIN5_8 = 602
CAN_ID_AIN9_12 = 603
CAN_ID_AIN13_16 = 604
CAN_ID_AIN17_20 = 605
CAN_ID_AIN21_temp = 606

# Dictionary for easy lookup
CAN_IDS = {
    'KEEP_ALIVE': CAN_ID_KEEP_ALIVE,
    'AIN1_4': CAN_ID_AIN1_4,
    'AIN5_8': CAN_ID_AIN5_8,
    'AIN9_12': CAN_ID_AIN9_12,
    'AIN13_16': CAN_ID_AIN13_16,
    'AIN17_20': CAN_ID_AIN17_20,
    'AIN21_temp': CAN_ID_AIN21_temp,
}

# CAN ID names (for display)
CAN_ID_NAMES = {
    CAN_ID_KEEP_ALIVE: 'Keep Alive',
    CAN_ID_AIN1_4: 'Analog Inputs 1-4',
    CAN_ID_AIN5_8: 'Analog Inputs 5-8',
    CAN_ID_AIN9_12: 'Analog Inputs 9-12',
    CAN_ID_AIN13_16: 'Analog Inputs 13-16',
    CAN_ID_AIN17_20: 'Analog Inputs 17-20',
    CAN_ID_AIN21_temp: 'Analog Input 21 / Temperature',
}

# Decoder configurations based on actual CAN message format
# Raw values are uint16 little-endian (b0 + b1<<8)
# CAN ID 0x259: analog voltage in1 at bytes 0-1 (raw: 0xD703 = 55043)
# CAN ID 0x25E: internal voltage at bytes 2-3 (raw: 0xEC05 = 60421), temperature at bytes 4-5 (raw: 0xB906 = 47366)
# Includes both raw values and default scaled values (V, °C) for easy access
EXAMPLE_DECODERS = {
    CAN_ID_AIN1_4: [
        # Default: Analog voltage with proper scaling (V)
        {'name': 'analog_voltage_in1', 'byte_index': 0, 'data_type': 'uint16_le', 'scale': 0.001, 'offset': 0, 'unit': 'V'},
        # Raw value option
        {'name': 'analog_voltage_in1_raw', 'byte_index': 0, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
    ],
    CAN_ID_AIN5_8: [
        {'name': 'AIN5', 'byte_index': 0, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
        {'name': 'AIN6', 'byte_index': 2, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
        {'name': 'AIN7', 'byte_index': 4, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
        {'name': 'AIN8', 'byte_index': 6, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
    ],
    CAN_ID_AIN9_12: [
        {'name': 'AIN9', 'byte_index': 0, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
        {'name': 'AIN10', 'byte_index': 2, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
        {'name': 'AIN11', 'byte_index': 4, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
        {'name': 'AIN12', 'byte_index': 6, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
    ],
    CAN_ID_AIN13_16: [
        {'name': 'AIN13', 'byte_index': 0, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
        {'name': 'AIN14', 'byte_index': 2, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
        {'name': 'AIN15', 'byte_index': 4, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
        {'name': 'AIN16', 'byte_index': 6, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
    ],
    CAN_ID_AIN17_20: [
        {'name': 'AIN17', 'byte_index': 0, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
        {'name': 'AIN18', 'byte_index': 2, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
        {'name': 'AIN19', 'byte_index': 4, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
        {'name': 'AIN20', 'byte_index': 6, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
    ],
    CAN_ID_AIN21_temp: [
        # Default: Internal voltage with proper scaling (V)
        {'name': 'internal_voltage', 'byte_index': 2, 'data_type': 'uint16_le', 'scale': 0.001, 'offset': 0, 'unit': 'V'},
        # Default: Temperature with proper scaling (°C)
        {'name': 'temperature', 'byte_index': 4, 'data_type': 'uint16_le', 'scale': 0.001, 'offset': 0, 'unit': '°C'},
        # Raw value options
        {'name': 'internal_voltage_raw', 'byte_index': 2, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
        {'name': 'temperature_raw', 'byte_index': 4, 'data_type': 'uint16_le', 'scale': 1.0, 'offset': 0, 'unit': 'raw'},
    ],
}

# Default decoders to load automatically (the three main signals)
# These convert raw values to physical units for plotting
# NOTE: Adjust scale/offset values based on your actual sensor calibration
DEFAULT_DECODERS = {
    CAN_ID_AIN1_4: [
        # Analog voltage: scale 0.001V per count (millivolt resolution)
        # Raw 55043 = 55.043V
        # If values seem wrong, try: 0.0001 (5.504V) or 0.00001 (0.550V)
        {'name': 'analog_voltage_in1', 'byte_index': 0, 'data_type': 'uint16_le', 'scale': 0.001, 'offset': 0, 'unit': 'V'},
    ],
    CAN_ID_AIN21_temp: [
        # Internal voltage: scale 0.001V per count
        # Raw 60421 = 60.421V
        # If values seem wrong, try: 0.0001 (6.042V)
        {'name': 'internal_voltage', 'byte_index': 2, 'data_type': 'uint16_le', 'scale': 0.001, 'offset': 0, 'unit': 'V'},
        # Temperature: scale 0.001°C per count
        # Raw 47366 = 47.366°C (more reasonable than 473.66°C)
        # Alternative: scale 0.01 with offset -273.15 for Kelvin conversion
        # If values seem wrong, try: 0.01 (473.66°C) or adjust offset
        {'name': 'temperature', 'byte_index': 4, 'data_type': 'uint16_le', 'scale': 0.001, 'offset': 0, 'unit': '°C'},
    ],
}

def get_can_id_hex(can_id):
    """Get hex representation of CAN ID"""
    return f"0x{can_id:X}"

def get_all_can_ids():
    """Get list of all CAN IDs"""
    return list(CAN_IDS.values())

def get_can_id_name(can_id):
    """Get human-readable name for CAN ID"""
    return CAN_ID_NAMES.get(can_id, f"0x{can_id:X}")
