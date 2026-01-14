#!/usr/bin/env python3
"""
Example: Setting up decoders for predefined CAN IDs
This shows how to quickly configure decoders for all the system CAN IDs
"""

from can_decoder import CANDecoder, SignalDefinition
from can_ids import CAN_IDS, EXAMPLE_DECODERS

def setup_all_decoders():
    """Setup decoders for all predefined CAN IDs"""
    decoder = CANDecoder()
    
    for can_id, decoder_configs in EXAMPLE_DECODERS.items():
        for config in decoder_configs:
            # Determine signal parameters
            start_bit = config['byte_index'] * 8
            
            if config['data_type'] == 'uint8':
                length = 8
                is_signed = False
                is_little_endian = True
            elif config['data_type'] == 'uint16_le':
                length = 16
                is_signed = False
                is_little_endian = True
            elif config['data_type'] == 'uint16_be':
                length = 16
                is_signed = False
                is_little_endian = False
            elif config['data_type'] == 'int16_le':
                length = 16
                is_signed = True
                is_little_endian = True
            elif config['data_type'] == 'int16_be':
                length = 16
                is_signed = True
                is_little_endian = False
            else:
                continue
            
            signal = SignalDefinition(
                config['name'],
                start_bit,
                length,
                config['scale'],
                config['offset'],
                is_signed,
                is_little_endian,
                config['unit']
            )
            
            decoder.add_signal_definition(can_id, signal)
            print(f"Added decoder: CAN ID 0x{can_id:X} - {config['name']} ({config['unit']})")
    
    return decoder

if __name__ == '__main__':
    print("Setting up decoders for all predefined CAN IDs...")
    decoder = setup_all_decoders()
    print(f"\nTotal CAN IDs configured: {len(EXAMPLE_DECODERS)}")
    print("\nAvailable signals:")
    for can_id in EXAMPLE_DECODERS.keys():
        signals = decoder.get_available_signals(can_id)
        print(f"  0x{can_id:X}: {', '.join(signals)}")
