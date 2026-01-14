#!/usr/bin/env python3
"""
Example usage of the CAN Reader API
Demonstrates programmatic usage for custom analysis workflows
"""

from can_reader import CANReader, CANPlotter, CANExporter
import matplotlib.pyplot as plt

def example_basic_reading():
    """Example: Basic CAN message reading"""
    print("Example 1: Basic Reading")
    print("-" * 50)
    
    reader = CANReader(interface='socketcan', channel='can0')
    
    if reader.connect():
        # Read for 5 seconds
        reader.read_messages(duration=5)
        print(f"Collected {len(reader.messages)} messages")
        reader.disconnect()
    else:
        print("Could not connect. Using mock data for demonstration.")
        # In real usage, you'd handle the error appropriately

def example_filtering():
    """Example: Filtering messages"""
    print("\nExample 2: Filtering")
    print("-" * 50)
    
    reader = CANReader(interface='socketcan', channel='can0')
    
    # Read messages first
    if reader.connect():
        reader.read_messages(duration=5)
        
        # Filter by CAN IDs
        filtered = reader.filter_messages(can_ids=[0x123, 0x456])
        print(f"Filtered to {len(filtered)} messages")
        
        # Filter by data length
        dlc_filtered = reader.filter_messages(min_dlc=4, max_dlc=8)
        print(f"DLC filtered: {len(dlc_filtered)} messages")
        
        reader.disconnect()

def example_plotting():
    """Example: Creating custom plots"""
    print("\nExample 3: Plotting")
    print("-" * 50)
    
    reader = CANReader(interface='socketcan', channel='can0')
    
    if reader.connect():
        reader.read_messages(duration=10)
        
        if reader.messages:
            plotter = CANPlotter()
            
            # Plot message frequency
            plotter.plot_message_frequency(reader.messages)
            plotter.save_figure('frequency_plot.png', dpi=300)
            
            # Plot CAN ID distribution
            plotter.plot_can_id_distribution(reader.messages)
            plotter.save_figure('distribution_plot.png', dpi=300)
            
            # Plot specific byte if we have a CAN ID
            if reader.messages:
                first_can_id = reader.messages[0]['arbitration_id']
                plotter.plot_data_bytes(reader.messages, first_can_id, byte_index=0)
                plotter.save_figure('byte_plot.png', dpi=300)
            
            print("Plots saved!")
        
        reader.disconnect()

def example_export():
    """Example: Exporting data"""
    print("\nExample 4: Exporting")
    print("-" * 50)
    
    reader = CANReader(interface='socketcan', channel='can0')
    
    if reader.connect():
        reader.read_messages(duration=5)
        
        if reader.messages:
            # Export to different formats
            CANExporter.to_csv(reader.messages, 'can_data.csv')
            CANExporter.to_json(reader.messages, 'can_data.json')
            CANExporter.to_candump_format(reader.messages, 'can_data.log')
            print("Data exported!")
        
        reader.disconnect()

def example_custom_analysis():
    """Example: Custom analysis workflow"""
    print("\nExample 5: Custom Analysis")
    print("-" * 50)
    
    reader = CANReader(interface='socketcan', channel='can0')
    
    if reader.connect():
        reader.read_messages(duration=10)
        
        if reader.messages:
            # Custom analysis: Find most frequent CAN ID
            from collections import Counter
            can_ids = [m['arbitration_id'] for m in reader.messages]
            id_counts = Counter(can_ids)
            most_common = id_counts.most_common(5)
            
            print("Top 5 most frequent CAN IDs:")
            for can_id, count in most_common:
                print(f"  0x{can_id:X}: {count} messages")
            
            # Analyze data patterns for a specific CAN ID
            if most_common:
                target_id = most_common[0][0]
                target_messages = [m for m in reader.messages 
                                 if m['arbitration_id'] == target_id]
                
                if target_messages:
                    # Calculate statistics for first byte
                    first_bytes = [m['data'][0] if len(m['data']) > 0 else 0 
                                 for m in target_messages]
                    
                    print(f"\nStatistics for CAN ID 0x{target_id:X}, Byte 0:")
                    print(f"  Min: {min(first_bytes)}")
                    print(f"  Max: {max(first_bytes)}")
                    print(f"  Mean: {sum(first_bytes) / len(first_bytes):.2f}")
        
        reader.disconnect()

def example_multi_plot():
    """Example: Creating multiple plots in one figure"""
    print("\nExample 6: Multi-Plot Figure")
    print("-" * 50)
    
    reader = CANReader(interface='socketcan', channel='can0')
    
    if reader.connect():
        reader.read_messages(duration=10)
        
        if reader.messages and len(reader.messages) > 0:
            # Get unique CAN IDs
            unique_ids = list(set([m['arbitration_id'] for m in reader.messages]))
            
            if len(unique_ids) > 0:
                target_id = unique_ids[0]
                
                # Create a figure with multiple subplots
                fig, axes = plt.subplots(2, 2, figsize=(14, 10))
                fig.suptitle(f'CAN ID 0x{target_id:X} - Comprehensive Analysis', 
                           fontsize=16, fontweight='bold')
                
                # Plot 1: Byte 0 over time
                plotter = CANPlotter()
                plotter.plot_data_bytes(reader.messages, target_id, byte_index=0)
                plotter.fig.savefig('multi_plot_byte0.png', dpi=300, bbox_inches='tight')
                
                # Plot 2: Inter-message interval
                plotter.plot_inter_message_interval(reader.messages, target_id)
                plotter.fig.savefig('multi_plot_interval.png', dpi=300, bbox_inches='tight')
                
                # Plot 3: Multiple bytes
                plotter.plot_multiple_bytes(reader.messages, target_id, [0, 1, 2, 3])
                plotter.fig.savefig('multi_plot_bytes.png', dpi=300, bbox_inches='tight')
                
                print("Multi-plot figures saved!")
        
        reader.disconnect()

if __name__ == '__main__':
    print("CAN Reader API Examples")
    print("=" * 50)
    print("\nNote: These examples require a CAN interface to be connected.")
    print("Modify the interface and channel parameters as needed for your setup.\n")
    
    # Uncomment the examples you want to run:
    
    # example_basic_reading()
    # example_filtering()
    # example_plotting()
    # example_export()
    # example_custom_analysis()
    # example_multi_plot()
    
    print("\nTo run examples, uncomment them in the script.")
