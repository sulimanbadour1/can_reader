#!/usr/bin/env python3
"""
DIY CAN Bus Reader and Analyzer
A free, powerful tool for CAN bus analysis with custom plots, filtering, and exporting.
"""

import can
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import argparse
import json
import csv
from collections import defaultdict
from typing import List, Dict, Optional, Callable
import signal
import sys


class CANReader:
    """CAN bus reader with filtering and data collection capabilities."""
    
    def __init__(self, interface: str = 'socketcan', channel: str = 'can0', 
                 bitrate: int = 500000, filters: Optional[List[Dict]] = None):
        """
        Initialize CAN reader.
        
        Args:
            interface: CAN interface type (socketcan, slcan, usb2can, etc.)
            channel: CAN channel/device name
            bitrate: CAN bus bitrate
            filters: List of filter dictionaries {'can_id': int, 'can_mask': int}
        """
        self.interface = interface
        self.channel = channel
        self.bitrate = bitrate
        self.filters = filters
        self.bus = None
        self.messages = []
        self.running = False
        
    def connect(self):
        """Connect to CAN bus."""
        try:
            config = {
                'interface': self.interface,
                'channel': self.channel,
                'bitrate': self.bitrate,
            }
            
            if self.filters:
                config['can_filters'] = self.filters
                
            self.bus = can.interface.Bus(**config)
            print(f"Connected to CAN bus: {self.interface} on {self.channel}")
            return True
        except Exception as e:
            print(f"Error connecting to CAN bus: {e}")
            print("\nTrying alternative connection methods...")
            # Try without bitrate for some interfaces
            try:
                config = {
                    'interface': self.interface,
                    'channel': self.channel,
                }
                if self.filters:
                    config['can_filters'] = self.filters
                self.bus = can.interface.Bus(**config)
                print(f"Connected to CAN bus: {self.interface} on {self.channel}")
                return True
            except Exception as e2:
                print(f"Failed to connect: {e2}")
                return False
    
    def disconnect(self):
        """Disconnect from CAN bus."""
        if self.bus:
            self.bus.shutdown()
            self.bus = None
            print("Disconnected from CAN bus")
    
    def read_messages(self, duration: Optional[float] = None, count: Optional[int] = None):
        """
        Read CAN messages.
        
        Args:
            duration: Duration in seconds to read (None = until interrupted)
            count: Number of messages to read (None = unlimited)
        """
        if not self.bus:
            if not self.connect():
                return
        
        self.running = True
        start_time = datetime.now()
        message_count = 0
        
        print(f"Reading CAN messages... (Press Ctrl+C to stop)")
        if duration:
            print(f"Duration: {duration} seconds")
        if count:
            print(f"Count: {count} messages")
        
        try:
            while self.running:
                if duration and (datetime.now() - start_time).total_seconds() >= duration:
                    break
                if count and message_count >= count:
                    break
                
                try:
                    msg = self.bus.recv(timeout=0.1)
                    if msg is not None:
                        self.messages.append({
                            'timestamp': datetime.now(),
                            'arbitration_id': msg.arbitration_id,
                            'data': msg.data,
                            'dlc': msg.dlc,
                            'is_extended_id': msg.is_extended_id,
                            'is_remote_frame': msg.is_remote_frame,
                            'is_error_frame': msg.is_error_frame,
                            'data_hex': msg.data.hex(),
                            'data_dec': [b for b in msg.data]
                        })
                        message_count += 1
                        if message_count % 100 == 0:
                            print(f"Received {message_count} messages...", end='\r')
                except can.CanError as e:
                    print(f"\nCAN error: {e}")
                    break
                    
        except KeyboardInterrupt:
            print("\n\nStopped by user")
        finally:
            self.running = False
        
        print(f"\nTotal messages received: {len(self.messages)}")
    
    def filter_messages(self, 
                       can_ids: Optional[List[int]] = None,
                       min_dlc: Optional[int] = None,
                       max_dlc: Optional[int] = None,
                       data_filter: Optional[Callable] = None) -> List[Dict]:
        """
        Filter collected messages.
        
        Args:
            can_ids: List of CAN IDs to include (None = all)
            min_dlc: Minimum data length code
            max_dlc: Maximum data length code
            data_filter: Custom function(data) -> bool
        
        Returns:
            Filtered list of messages
        """
        filtered = self.messages.copy()
        
        if can_ids:
            filtered = [m for m in filtered if m['arbitration_id'] in can_ids]
        
        if min_dlc is not None:
            filtered = [m for m in filtered if m['dlc'] >= min_dlc]
        
        if max_dlc is not None:
            filtered = [m for m in filtered if m['dlc'] <= max_dlc]
        
        if data_filter:
            filtered = [m for m in filtered if data_filter(m['data'])]
        
        return filtered


class CANPlotter:
    """Matplotlib-based plotting for CAN data."""
    
    def __init__(self, style: str = 'seaborn-v0_8'):
        """Initialize plotter with publication-quality style."""
        plt.style.use(style)
        self.fig = None
        self.axes = None
    
    def plot_message_frequency(self, messages: List[Dict], can_ids: Optional[List[int]] = None,
                               time_window: float = 1.0, figsize=(12, 6)):
        """
        Plot message frequency over time.
        
        Args:
            messages: List of message dictionaries
            can_ids: Specific CAN IDs to plot (None = all)
            time_window: Time window in seconds for frequency calculation
            figsize: Figure size tuple
        """
        if not messages:
            print("No messages to plot")
            return
        
        df = pd.DataFrame(messages)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        if can_ids:
            df = df[df['arbitration_id'].isin(can_ids)]
        
        # Group by time window and CAN ID
        df['time_bin'] = df['timestamp'].dt.floor(f'{time_window}S')
        freq_data = df.groupby(['time_bin', 'arbitration_id']).size().reset_index(name='count')
        
        self.fig, self.axes = plt.subplots(figsize=figsize)
        
        for can_id in freq_data['arbitration_id'].unique():
            id_data = freq_data[freq_data['arbitration_id'] == can_id]
            self.axes.plot(id_data['time_bin'], id_data['count'], 
                          marker='o', label=f'ID 0x{can_id:X}', linewidth=2)
        
        self.axes.set_xlabel('Time', fontsize=12)
        self.axes.set_ylabel(f'Message Count per {time_window}s', fontsize=12)
        self.axes.set_title('CAN Message Frequency Over Time', fontsize=14, fontweight='bold')
        self.axes.legend(loc='best', frameon=True, shadow=True)
        self.axes.grid(True, alpha=0.3)
        self.axes.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.xticks(rotation=45)
        plt.tight_layout()
    
    def plot_can_id_distribution(self, messages: List[Dict], figsize=(10, 6)):
        """Plot distribution of CAN IDs."""
        if not messages:
            print("No messages to plot")
            return
        
        can_ids = [m['arbitration_id'] for m in messages]
        id_counts = pd.Series(can_ids).value_counts().sort_index()
        
        self.fig, self.axes = plt.subplots(figsize=figsize)
        
        bars = self.axes.bar([f'0x{id:X}' for id in id_counts.index], 
                            id_counts.values, 
                            color='steelblue', edgecolor='black', alpha=0.7)
        
        self.axes.set_xlabel('CAN ID', fontsize=12)
        self.axes.set_ylabel('Message Count', fontsize=12)
        self.axes.set_title('CAN ID Message Distribution', fontsize=14, fontweight='bold')
        self.axes.grid(True, alpha=0.3, axis='y')
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            self.axes.text(bar.get_x() + bar.get_width()/2., height,
                          f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
    
    def plot_data_bytes(self, messages: List[Dict], can_id: int, byte_index: int = 0,
                       figsize=(12, 6)):
        """
        Plot specific data byte over time.
        
        Args:
            messages: List of message dictionaries
            can_id: CAN ID to plot
            byte_index: Byte index (0-7)
            figsize: Figure size tuple
        """
        filtered = [m for m in messages if m['arbitration_id'] == can_id]
        if not filtered:
            print(f"No messages found for CAN ID 0x{can_id:X}")
            return
        
        timestamps = [m['timestamp'] for m in filtered]
        byte_values = []
        for m in filtered:
            if len(m['data']) > byte_index:
                byte_values.append(m['data'][byte_index])
            else:
                byte_values.append(0)
        
        self.fig, self.axes = plt.subplots(figsize=figsize)
        self.axes.plot(timestamps, byte_values, marker='o', linewidth=2, markersize=4)
        self.axes.set_xlabel('Time', fontsize=12)
        self.axes.set_ylabel(f'Byte {byte_index} Value', fontsize=12)
        self.axes.set_title(f'CAN ID 0x{can_id:X} - Byte {byte_index} Over Time', 
                           fontsize=14, fontweight='bold')
        self.axes.grid(True, alpha=0.3)
        self.axes.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.xticks(rotation=45)
        plt.tight_layout()
    
    def plot_multiple_bytes(self, messages: List[Dict], can_id: int, 
                           byte_indices: List[int] = None, figsize=(14, 8)):
        """
        Plot multiple data bytes for a CAN ID.
        
        Args:
            messages: List of message dictionaries
            can_id: CAN ID to plot
            byte_indices: List of byte indices to plot (None = all bytes)
            figsize: Figure size tuple
        """
        filtered = [m for m in messages if m['arbitration_id'] == can_id]
        if not filtered:
            print(f"No messages found for CAN ID 0x{can_id:X}")
            return
        
        timestamps = [m['timestamp'] for m in filtered]
        
        if byte_indices is None:
            # Determine max DLC for this CAN ID
            max_dlc = max([m['dlc'] for m in filtered])
            byte_indices = list(range(max_dlc))
        
        self.fig, self.axes = plt.subplots(figsize=figsize)
        
        colors = plt.cm.tab10(np.linspace(0, 1, len(byte_indices)))
        
        for i, byte_idx in enumerate(byte_indices):
            byte_values = []
            for m in filtered:
                if len(m['data']) > byte_idx:
                    byte_values.append(m['data'][byte_idx])
                else:
                    byte_values.append(0)
            
            self.axes.plot(timestamps, byte_values, marker='o', linewidth=2, 
                          markersize=3, label=f'Byte {byte_idx}', color=colors[i])
        
        self.axes.set_xlabel('Time', fontsize=12)
        self.axes.set_ylabel('Byte Value', fontsize=12)
        self.axes.set_title(f'CAN ID 0x{can_id:X} - Multiple Bytes Over Time', 
                           fontsize=14, fontweight='bold')
        self.axes.legend(loc='best', frameon=True, shadow=True)
        self.axes.grid(True, alpha=0.3)
        self.axes.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.xticks(rotation=45)
        plt.tight_layout()
    
    def plot_inter_message_interval(self, messages: List[Dict], can_id: int,
                                   figsize=(12, 6)):
        """Plot inter-message interval for a specific CAN ID."""
        filtered = [m for m in messages if m['arbitration_id'] == can_id]
        if len(filtered) < 2:
            print(f"Need at least 2 messages for CAN ID 0x{can_id:X}")
            return
        
        intervals = []
        for i in range(1, len(filtered)):
            delta = (filtered[i]['timestamp'] - filtered[i-1]['timestamp']).total_seconds()
            intervals.append(delta * 1000)  # Convert to milliseconds
        
        self.fig, self.axes = plt.subplots(figsize=figsize)
        self.axes.plot(range(len(intervals)), intervals, marker='o', linewidth=2, markersize=4)
        self.axes.set_xlabel('Message Index', fontsize=12)
        self.axes.set_ylabel('Interval (ms)', fontsize=12)
        self.axes.set_title(f'CAN ID 0x{can_id:X} - Inter-Message Interval', 
                           fontsize=14, fontweight='bold')
        self.axes.grid(True, alpha=0.3)
        plt.tight_layout()
    
    def plot_heatmap(self, messages: List[Dict], can_ids: Optional[List[int]] = None,
                    time_window: float = 1.0, figsize=(14, 8)):
        """
        Create a heatmap of message frequency by CAN ID and time.
        
        Args:
            messages: List of message dictionaries
            can_ids: CAN IDs to include (None = all)
            time_window: Time window in seconds
            figsize: Figure size tuple
        """
        if not messages:
            print("No messages to plot")
            return
        
        df = pd.DataFrame(messages)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        if can_ids:
            df = df[df['arbitration_id'].isin(can_ids)]
        
        df['time_bin'] = df['timestamp'].dt.floor(f'{time_window}S')
        heatmap_data = df.pivot_table(
            index='arbitration_id',
            columns='time_bin',
            values='timestamp',
            aggfunc='count',
            fill_value=0
        )
        
        self.fig, self.axes = plt.subplots(figsize=figsize)
        
        im = self.axes.imshow(heatmap_data.values, aspect='auto', cmap='YlOrRd', 
                             interpolation='nearest')
        
        # Set ticks
        self.axes.set_yticks(range(len(heatmap_data.index)))
        self.axes.set_yticklabels([f'0x{id:X}' for id in heatmap_data.index])
        
        # Format x-axis with time labels
        num_cols = len(heatmap_data.columns)
        if num_cols > 20:
            step = max(1, num_cols // 20)
            x_ticks = range(0, num_cols, step)
            x_labels = [heatmap_data.columns[i].strftime('%H:%M:%S') 
                       for i in x_ticks]
        else:
            x_ticks = range(num_cols)
            x_labels = [heatmap_data.columns[i].strftime('%H:%M:%S') 
                       for i in x_ticks]
        
        self.axes.set_xticks(x_ticks)
        self.axes.set_xticklabels(x_labels, rotation=45, ha='right')
        
        self.axes.set_xlabel('Time', fontsize=12)
        self.axes.set_ylabel('CAN ID', fontsize=12)
        self.axes.set_title('CAN Message Frequency Heatmap', fontsize=14, fontweight='bold')
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=self.axes)
        cbar.set_label('Message Count', fontsize=11)
        
        plt.tight_layout()
    
    def save_figure(self, filename: str, dpi: int = 300, format: str = 'png'):
        """Save current figure to file."""
        if self.fig:
            self.fig.savefig(filename, dpi=dpi, format=format, bbox_inches='tight')
            print(f"Figure saved to {filename}")
        else:
            print("No figure to save")
    
    def show(self):
        """Display the plot."""
        if self.fig:
            plt.show()
        else:
            print("No figure to display")


class CANExporter:
    """Export CAN data to various formats."""
    
    @staticmethod
    def to_csv(messages: List[Dict], filename: str):
        """Export messages to CSV."""
        if not messages:
            print("No messages to export")
            return
        
        df = pd.DataFrame(messages)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Flatten data columns
        df['data_hex'] = df['data'].apply(lambda x: x.hex())
        df['data_dec'] = df['data'].apply(lambda x: ','.join(map(str, x)))
        
        # Select columns for CSV
        export_df = df[['timestamp', 'arbitration_id', 'dlc', 'data_hex', 'data_dec',
                       'is_extended_id', 'is_remote_frame', 'is_error_frame']]
        
        export_df.to_csv(filename, index=False)
        print(f"Exported {len(messages)} messages to {filename}")
    
    @staticmethod
    def to_json(messages: List[Dict], filename: str):
        """Export messages to JSON."""
        if not messages:
            print("No messages to export")
            return
        
        # Convert datetime to string for JSON serialization
        export_data = []
        for msg in messages:
            export_msg = msg.copy()
            export_msg['timestamp'] = msg['timestamp'].isoformat()
            export_msg['data'] = list(msg['data'])
            export_data.append(export_msg)
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"Exported {len(messages)} messages to {filename}")
    
    @staticmethod
    def to_candump_format(messages: List[Dict], filename: str):
        """Export in candump format."""
        if not messages:
            print("No messages to export")
            return
        
        with open(filename, 'w') as f:
            for msg in messages:
                timestamp = msg['timestamp'].timestamp()
                can_id = f"{msg['arbitration_id']:03X}"
                if msg['is_extended_id']:
                    can_id = f"{msg['arbitration_id']:08X}"
                
                data_hex = ' '.join([f"{b:02X}" for b in msg['data']])
                f.write(f"({timestamp:.6f}) can0 {can_id}#{data_hex}\n")
        
        print(f"Exported {len(messages)} messages to {filename} (candump format)")


def main():
    parser = argparse.ArgumentParser(
        description='DIY CAN Bus Reader and Analyzer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Read CAN messages for 10 seconds
  python can_reader.py --interface socketcan --channel can0 --duration 10
  
  # Read 1000 messages and plot frequency
  python can_reader.py --interface socketcan --channel can0 --count 1000 --plot frequency
  
  # Filter specific CAN IDs and export to CSV
  python can_reader.py --interface socketcan --channel can0 --duration 5 --can-ids 0x123 0x456 --export csv
  
  # Plot specific byte from CAN ID
  python can_reader.py --interface socketcan --channel can0 --duration 5 --plot byte --can-id 0x123 --byte-index 0
        """
    )
    
    parser.add_argument('--interface', type=str, default='socketcan',
                       help='CAN interface type (socketcan, slcan, usb2can, etc.)')
    parser.add_argument('--channel', type=str, default='can0',
                       help='CAN channel/device name')
    parser.add_argument('--bitrate', type=int, default=500000,
                       help='CAN bus bitrate')
    parser.add_argument('--duration', type=float,
                       help='Duration in seconds to read messages')
    parser.add_argument('--count', type=int,
                       help='Number of messages to read')
    parser.add_argument('--can-ids', nargs='+', type=lambda x: int(x, 0),
                       help='Filter specific CAN IDs (hex: 0x123 or decimal: 291)')
    parser.add_argument('--plot', type=str, choices=['frequency', 'distribution', 'byte', 
                                                     'bytes', 'interval', 'heatmap'],
                       help='Type of plot to generate')
    parser.add_argument('--can-id', type=lambda x: int(x, 0),
                       help='CAN ID for byte/interval plots')
    parser.add_argument('--byte-index', type=int, default=0,
                       help='Byte index for byte plot (0-7)')
    parser.add_argument('--byte-indices', nargs='+', type=int,
                       help='Byte indices for multi-byte plot')
    parser.add_argument('--export', type=str, choices=['csv', 'json', 'candump'],
                       help='Export format')
    parser.add_argument('--output', type=str,
                       help='Output filename (for export or plot save)')
    parser.add_argument('--save-plot', action='store_true',
                       help='Save plot instead of displaying')
    parser.add_argument('--dpi', type=int, default=300,
                       help='DPI for saved plots')
    
    args = parser.parse_args()
    
    # Create CAN reader
    filters = None
    if args.can_ids:
        filters = [{'can_id': cid, 'can_mask': 0x7FF} for cid in args.can_ids]
    
    reader = CANReader(
        interface=args.interface,
        channel=args.channel,
        bitrate=args.bitrate,
        filters=filters
    )
    
    # Read messages
    reader.read_messages(duration=args.duration, count=args.count)
    
    if not reader.messages:
        print("No messages collected. Exiting.")
        return
    
    # Filter messages if needed
    messages = reader.messages
    if args.can_ids:
        messages = reader.filter_messages(can_ids=args.can_ids)
    
    # Export if requested
    if args.export:
        output_file = args.output or f"can_data.{args.export}"
        if args.export == 'csv':
            CANExporter.to_csv(messages, output_file)
        elif args.export == 'json':
            CANExporter.to_json(messages, output_file)
        elif args.export == 'candump':
            CANExporter.to_candump_format(messages, output_file)
    
    # Plot if requested
    if args.plot:
        plotter = CANPlotter()
        
        if args.plot == 'frequency':
            plotter.plot_message_frequency(messages, can_ids=args.can_ids)
        elif args.plot == 'distribution':
            plotter.plot_can_id_distribution(messages)
        elif args.plot == 'byte':
            if not args.can_id:
                print("Error: --can-id required for byte plot")
                return
            plotter.plot_data_bytes(messages, args.can_id, args.byte_index)
        elif args.plot == 'bytes':
            if not args.can_id:
                print("Error: --can-id required for bytes plot")
                return
            plotter.plot_multiple_bytes(messages, args.can_id, args.byte_indices)
        elif args.plot == 'interval':
            if not args.can_id:
                print("Error: --can-id required for interval plot")
                return
            plotter.plot_inter_message_interval(messages, args.can_id)
        elif args.plot == 'heatmap':
            plotter.plot_heatmap(messages, can_ids=args.can_ids)
        
        if args.save_plot:
            output_file = args.output or f"can_plot_{args.plot}.png"
            plotter.save_figure(output_file, dpi=args.dpi)
        else:
            plotter.show()
    
    # Cleanup
    reader.disconnect()


if __name__ == '__main__':
    main()
