#!/usr/bin/env python3
# CAN Bus Analyzer GUI
# Simple Tkinter app to read CAN messages and plot voltage, temp, etc.
#  SB2025

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import matplotlib.animation as animation
from datetime import datetime
import threading
import queue
import can
from collections import defaultdict, deque
from can_reader import CANReader
from can_decoder import CANDecoder, SignalDefinition
from can_ids import CAN_IDS, CAN_ID_NAMES, EXAMPLE_DECODERS, DEFAULT_DECODERS, get_can_id_hex

# Use a nicer matplotlib style
try:
    plt.style.use('seaborn-v0_8-darkgrid')
except:
    plt.style.use('seaborn-darkgrid')


class CANAnalyzerGUI:
    """Main GUI window"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("CAN Bus Analyzer - SB2025")
        self.root.geometry("1400x900")
        
        # Configure root window style
        self.root.configure(bg='#f0f0f0')
        
        # Configure ttk style
        ttk_style = ttk.Style()
        ttk_style.theme_use('clam')
        ttk_style.configure('TLabel', background='#f0f0f0', font=('Segoe UI', 9))
        ttk_style.configure('TFrame', background='#f0f0f0')
        ttk_style.configure('TLabelFrame', background='#f0f0f0', font=('Segoe UI', 9, 'bold'))
        ttk_style.configure('TLabelFrame.Label', background='#f0f0f0', font=('Segoe UI', 9, 'bold'))
        ttk_style.configure('TButton', font=('Segoe UI', 9))
        ttk_style.map('TButton', background=[('active', '#e0e0e0')])
        
        # CAN stuff
        self.reader = None
        self.decoder = CANDecoder()
        self.is_connected = False
        self.is_capturing = False
        
        # Store decoded data: {can_id: {signal_name: deque of values}}
        self.message_queue = queue.Queue()
        self.decoded_data = defaultdict(lambda: defaultdict(deque))
        self.max_data_points = 1000
        
        # Error banner state
        self.error_banner_frame = None
        self.error_label = None
        self.current_error = None
        
        # What signals to plot
        self.plot_signals = {}
        # Use a nicer color palette
        self.colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E', 
                      '#BC4749', '#F77F00', '#FCBF49', '#06A77D', '#118AB2']
        self.color_index = 0
        
        # Track decoder listbox items for removal
        self.decoder_listbox_items = []  # List of (can_id, signal_name) tuples
        
        # Threading stuff
        self.processing_thread = None
        self.stop_processing = False
        self.ani = None
        
        self._setup_ui()
        
        # Load default decoders automatically
        self._load_default_decoders()
        
    def _setup_ui(self):
        """Build the GUI"""
        # Error banner at the top (always visible when there's an error)
        self._setup_error_banner()
        
        # Split window into left (controls) and right (plots/messages)
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)
        
        self._setup_connection_panel(left_frame)
        self._setup_decoder_panel(left_frame)
        self._setup_plot_controls(left_frame)
        self._setup_message_display(right_frame)
        self._setup_plot_area(right_frame)
    
    def _setup_error_banner(self):
        """Create error banner at the top of the window"""
        self.error_banner_frame = tk.Frame(self.root, bg="#dc3545", height=0)
        self.error_banner_frame.pack(fill=tk.X, side=tk.TOP, padx=0, pady=0)
        self.error_banner_frame.pack_propagate(False)
        
        # Error content frame
        error_content = tk.Frame(self.error_banner_frame, bg="#dc3545")
        error_content.pack(fill=tk.X, padx=10, pady=8)
        
        # Error icon and message
        error_icon = tk.Label(error_content, text="⚠", bg="#dc3545", 
                             fg="white", font=('Segoe UI', 14, 'bold'))
        error_icon.pack(side=tk.LEFT, padx=(0, 10))
        
        self.error_label = tk.Label(error_content, text="", bg="#dc3545", 
                                    fg="white", font=('Segoe UI', 10),
                                    wraplength=1200, justify=tk.LEFT)
        self.error_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Close button
        close_btn = tk.Button(error_content, text="✕", bg="#dc3545", fg="white",
                             font=('Segoe UI', 12, 'bold'), relief=tk.FLAT,
                             command=self._hide_error_banner, cursor="hand2",
                             activebackground="#c82333", activeforeground="white",
                             bd=0, padx=5, pady=2)
        close_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Initially hidden
        self._hide_error_banner()
    
    def _show_error_banner(self, error_message):
        """Show error banner with message"""
        self.current_error = error_message
        if self.error_label:
            self.error_label.config(text=error_message)
            self.error_banner_frame.config(height=50)
            self.error_banner_frame.pack(fill=tk.X, side=tk.TOP, padx=0, pady=0)
    
    def _hide_error_banner(self):
        """Hide error banner"""
        self.current_error = None
        if self.error_banner_frame:
            self.error_banner_frame.config(height=0)
            self.error_banner_frame.pack_forget()
        
    def _setup_connection_panel(self, parent):
        """CAN connection settings"""
        conn_frame = ttk.LabelFrame(parent, text="CAN Connection", padding=10)
        conn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Interface dropdown
        ttk.Label(conn_frame, text="Interface:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.interface_var = tk.StringVar(value="slcan")
        interface_combo = ttk.Combobox(conn_frame, textvariable=self.interface_var,
                                       values=["slcan", "socketcan", "usb2can", "pcan", 
                                              "ixxat", "vector", "virtual"],
                                       state="readonly", width=15)
        interface_combo.grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)
        
        # Channel/device name
        ttk.Label(conn_frame, text="Channel:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.channel_var = tk.StringVar(value="COM3")
        channel_entry = ttk.Entry(conn_frame, textvariable=self.channel_var, width=18)
        channel_entry.grid(row=1, column=1, sticky=tk.W, pady=2, padx=5)
        
        # Bitrate
        ttk.Label(conn_frame, text="Bitrate:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.bitrate_var = tk.StringVar(value="500000")
        bitrate_combo = ttk.Combobox(conn_frame, textvariable=self.bitrate_var,
                                     values=["125000", "250000", "500000", "1000000"],
                                     state="readonly", width=15)
        bitrate_combo.grid(row=2, column=1, sticky=tk.W, pady=2, padx=5)
        
        # Connect button
        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self._toggle_connection)
        self.connect_btn.grid(row=3, column=0, columnspan=2, pady=10, sticky=tk.EW)
        
        # Status label with better styling
        self.status_label = ttk.Label(conn_frame, text="Status: Disconnected", 
                                     foreground="red", font=('Segoe UI', 9, 'bold'))
        self.status_label.grid(row=4, column=0, columnspan=2, pady=5)
        
        # Max data points setting (always visible)
        ttk.Label(conn_frame, text="Max Data Points:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.max_points_var = tk.StringVar(value="1000")
        max_points_entry = ttk.Entry(conn_frame, textvariable=self.max_points_var, width=10)
        max_points_entry.grid(row=5, column=1, sticky=tk.W, pady=2, padx=5)
        
        # Author ID
        author_label = ttk.Label(conn_frame, text="SB2025", 
                                font=('Segoe UI', 7), foreground='#888888')
        author_label.grid(row=6, column=0, columnspan=2, pady=2)
        
    def _setup_decoder_panel(self, parent):
        """Panel to configure how to decode CAN messages into voltage, temp, etc."""
        decoder_frame = ttk.LabelFrame(parent, text="Signal Decoder", padding=10)
        decoder_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # CAN ID (hex) - dropdown with predefined IDs
        ttk.Label(decoder_frame, text="CAN ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.decode_can_id_var = tk.StringVar(value="")
        decode_id_combo = ttk.Combobox(decoder_frame, textvariable=self.decode_can_id_var,
                                      values=[f"{name} ({get_can_id_hex(cid)})" for name, cid in CAN_IDS.items()] + 
                                             [get_can_id_hex(cid) for cid in CAN_IDS.values()],
                                      width=20)
        decode_id_combo.grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)
        decode_id_combo.bind('<<ComboboxSelected>>', self._on_can_id_selected)
        self.decode_id_combo = decode_id_combo
        
        # Signal name (voltage, temperature, etc.)
        ttk.Label(decoder_frame, text="Signal Name:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.signal_name_var = tk.StringVar(value="voltage")
        signal_entry = ttk.Entry(decoder_frame, textvariable=self.signal_name_var, width=12)
        signal_entry.grid(row=1, column=1, sticky=tk.W, pady=2, padx=5)
        
        # Which byte to start reading from
        ttk.Label(decoder_frame, text="Byte Index:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.byte_index_var = tk.StringVar(value="0")
        byte_entry = ttk.Entry(decoder_frame, textvariable=self.byte_index_var, width=12)
        byte_entry.grid(row=2, column=1, sticky=tk.W, pady=2, padx=5)
        
        # Scale factor (multiply raw value by this)
        ttk.Label(decoder_frame, text="Scale:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.scale_var = tk.StringVar(value="0.1")
        scale_entry = ttk.Entry(decoder_frame, textvariable=self.scale_var, width=12)
        scale_entry.grid(row=3, column=1, sticky=tk.W, pady=2, padx=5)
        
        # Offset (add this to scaled value)
        ttk.Label(decoder_frame, text="Offset:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.offset_var = tk.StringVar(value="0")
        offset_entry = ttk.Entry(decoder_frame, textvariable=self.offset_var, width=12)
        offset_entry.grid(row=4, column=1, sticky=tk.W, pady=2, padx=5)
        
        # Unit (V, °C, A, etc.)
        ttk.Label(decoder_frame, text="Unit:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.unit_var = tk.StringVar(value="V")
        unit_combo = ttk.Combobox(decoder_frame, textvariable=self.unit_var,
                                 values=["V", "°C", "A", "rpm", "km/h", "bar", "kg", ""],
                                 state="readonly", width=10)
        unit_combo.grid(row=5, column=1, sticky=tk.W, pady=2, padx=5)
        
        # Data type (8-bit, 16-bit, signed/unsigned, endianness)
        ttk.Label(decoder_frame, text="Data Type:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.data_type_var = tk.StringVar(value="uint16_le")
        data_type_combo = ttk.Combobox(decoder_frame, textvariable=self.data_type_var,
                                       values=["uint8", "uint16_le", "uint16_be", 
                                              "int16_le", "int16_be"],
                                       state="readonly", width=12)
        data_type_combo.grid(row=6, column=1, sticky=tk.W, pady=2, padx=5)
        
        # Add decoder button
        add_decoder_btn = ttk.Button(decoder_frame, text="Add Signal", 
                                     command=self._add_signal_decoder)
        add_decoder_btn.grid(row=7, column=0, columnspan=2, pady=10, sticky=tk.EW)
        
        # Quick preset buttons
        preset_frame = ttk.Frame(decoder_frame)
        preset_frame.grid(row=8, column=0, columnspan=2, pady=5, sticky=tk.EW)
        
        ttk.Button(preset_frame, text="Voltage (16-bit)", 
                  command=lambda: self._apply_preset("voltage")).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Temp (16-bit)", 
                  command=lambda: self._apply_preset("temperature")).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Load Predefined", 
                  command=self._load_predefined_decoders).pack(side=tk.LEFT, padx=2)
        
        # List of active decoders
        ttk.Label(decoder_frame, text="Active Decoders:").grid(row=9, column=0, 
                                                               columnspan=2, sticky=tk.W, pady=(10,2))
        
        decoder_list_frame = ttk.Frame(decoder_frame)
        decoder_list_frame.grid(row=10, column=0, columnspan=2, sticky=tk.EW, pady=2)
        
        self.decoder_listbox = tk.Listbox(decoder_list_frame, height=6)
        self.decoder_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        decoder_scroll = ttk.Scrollbar(decoder_list_frame, orient=tk.VERTICAL,
                                       command=self.decoder_listbox.yview)
        decoder_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.decoder_listbox.config(yscrollcommand=decoder_scroll.set)
        
        remove_decoder_btn = ttk.Button(decoder_frame, text="Remove Selected", 
                                       command=self._remove_signal_decoder)
        remove_decoder_btn.grid(row=11, column=0, columnspan=2, pady=5, sticky=tk.EW)
        
    def _setup_plot_controls(self, parent):
        """Controls for capturing and exporting"""
        plot_ctrl_frame = ttk.LabelFrame(parent, text="Plot Controls", padding=10)
        plot_ctrl_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.capture_btn = ttk.Button(plot_ctrl_frame, text="Start Capture", 
                                     command=self._toggle_capture, state=tk.DISABLED)
        self.capture_btn.pack(fill=tk.X, pady=2)
        
        ttk.Button(plot_ctrl_frame, text="Clear Data", 
                  command=self._clear_data).pack(fill=tk.X, pady=2)
        
        ttk.Button(plot_ctrl_frame, text="Export CSV", 
                  command=self._export_csv).pack(fill=tk.X, pady=2)
        
    def _setup_message_display(self, parent):
        """Text area showing raw CAN messages"""
        msg_frame = ttk.LabelFrame(parent, text="CAN Messages", padding=5)
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.message_text = scrolledtext.ScrolledText(msg_frame, height=15, width=60,
                                                      font=("Consolas", 9),
                                                      bg='#ffffff', fg='#333333',
                                                      insertbackground='#333333',
                                                      selectbackground='#4a9eff',
                                                      selectforeground='white',
                                                      relief=tk.FLAT, borderwidth=1)
        self.message_text.pack(fill=tk.BOTH, expand=True)
        
        # Filter by CAN ID
        filter_frame = ttk.Frame(msg_frame)
        filter_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(filter_frame, text="Filter CAN ID:").pack(side=tk.LEFT, padx=5)
        self.filter_id_var = tk.StringVar(value="")
        filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_id_var, width=10)
        filter_entry.pack(side=tk.LEFT, padx=5)
        filter_entry.bind('<Return>', lambda e: self._update_message_filter())
        
    def _setup_plot_area(self, parent):
        """Matplotlib plot area for real-time graphs"""
        plot_frame = ttk.LabelFrame(parent, text="Real-Time Plots", padding=5)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create plot with better styling
        self.fig = Figure(figsize=(10, 6), dpi=100, facecolor='white')
        self.ax = self.fig.add_subplot(111, facecolor='#fafafa')
        self.ax.set_xlabel("Time (s)", fontsize=11, fontweight='bold')
        self.ax.set_ylabel("Value", fontsize=11, fontweight='bold')
        self.ax.set_title("CAN Signal Values", fontsize=13, fontweight='bold', pad=15)
        self.ax.grid(True, alpha=0.4, linestyle='--', linewidth=0.5)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['left'].set_color('#cccccc')
        self.ax.spines['bottom'].set_color('#cccccc')
        
        # Embed in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Toolbar for zoom/pan
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()
        
        # Controls to add/remove signals from plot
        plot_select_frame = ttk.Frame(plot_frame)
        plot_select_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(plot_select_frame, text="Plot Signal:").pack(side=tk.LEFT, padx=5)
        self.plot_can_id_var = tk.StringVar(value="")
        plot_id_combo = ttk.Combobox(plot_select_frame, textvariable=self.plot_can_id_var,
                                     values=[f"{name} ({get_can_id_hex(cid)})" for name, cid in CAN_IDS.items()] +
                                            [get_can_id_hex(cid) for cid in CAN_IDS.values()],
                                     width=20, state="readonly")
        plot_id_combo.pack(side=tk.LEFT, padx=5)
        plot_id_combo.bind('<<ComboboxSelected>>', lambda e: self._update_plot_selection())
        
        self.plot_signal_var = tk.StringVar(value="")
        plot_signal_combo = ttk.Combobox(plot_select_frame, textvariable=self.plot_signal_var,
                                        width=15, state="readonly")
        plot_signal_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(plot_select_frame, text="Add to Plot", 
                  command=self._add_to_plot).pack(side=tk.LEFT, padx=5)
        ttk.Button(plot_select_frame, text="Remove from Plot", 
                  command=self._remove_from_plot).pack(side=tk.LEFT, padx=5)
        
        # List of currently plotted signals
        ttk.Label(plot_select_frame, text="Plotted:").pack(side=tk.LEFT, padx=(10, 5))
        self.plotted_signals_listbox = tk.Listbox(plot_select_frame, height=1, width=30)
        self.plotted_signals_listbox.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(plot_select_frame, text="Remove Selected", 
                  command=self._remove_selected_from_plot).pack(side=tk.LEFT, padx=5)
        ttk.Button(plot_select_frame, text="Clear All", 
                  command=self._clear_all_plots).pack(side=tk.LEFT, padx=5)
        
        self.plot_id_combo = plot_id_combo
        self.plot_signal_combo = plot_signal_combo
        
    def _load_default_decoders(self):
        """Load the three default decoders automatically on startup"""
        for can_id, decoder_configs in DEFAULT_DECODERS.items():
            for config in decoder_configs:
                start_bit = config['byte_index'] * 8
                
                if config['data_type'] == 'uint16_le':
                    length = 16
                    is_signed = False
                    is_little_endian = True
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
                
                self.decoder.add_signal_definition(can_id, signal)
                
                # Add to listbox and track it
                decoder_str = f"0x{can_id:X}: {config['name']} ({config['unit']})"
                self.decoder_listbox.insert(tk.END, decoder_str)
                self.decoder_listbox_items.append((can_id, config['name']))
        
        self._update_plot_combos()
    
    def _apply_preset(self, preset_type):
        """Quick preset for voltage or temperature"""
        if preset_type == "voltage":
            self.signal_name_var.set("voltage")
            self.byte_index_var.set("0")
            self.scale_var.set("0.1")
            self.offset_var.set("0")
            self.unit_var.set("V")
            self.data_type_var.set("uint16_le")
        elif preset_type == "temperature":
            self.signal_name_var.set("temperature")
            self.byte_index_var.set("2")
            self.scale_var.set("0.1")
            self.offset_var.set("-40")
            self.unit_var.set("°C")
            self.data_type_var.set("int16_le")
    
    def _on_can_id_selected(self, event=None):
        """When CAN ID is selected from dropdown, extract the ID"""
        selected = self.decode_can_id_var.get()
        # Extract hex value if format is "NAME (0xXXX)"
        if '(' in selected and ')' in selected:
            hex_part = selected.split('(')[1].split(')')[0]
            self.decode_can_id_var.set(hex_part)
    
    def _load_predefined_decoders(self):
        """Load example decoders for selected CAN ID"""
        try:
            can_id_str = self.decode_can_id_var.get()
            # Extract hex value if format is "NAME (0xXXX)"
            if '(' in can_id_str and ')' in can_id_str:
                can_id_str = can_id_str.split('(')[1].split(')')[0]
            
            can_id = int(can_id_str, 0)
            
            if can_id in EXAMPLE_DECODERS:
                count = 0
                for decoder_config in EXAMPLE_DECODERS[can_id]:
                    start_bit = decoder_config['byte_index'] * 8
                    if decoder_config['data_type'] == 'uint8':
                        length = 8
                        is_signed = False
                        is_little_endian = True
                    elif decoder_config['data_type'] == 'uint16_le':
                        length = 16
                        is_signed = False
                        is_little_endian = True
                    elif decoder_config['data_type'] == 'uint16_be':
                        length = 16
                        is_signed = False
                        is_little_endian = False
                    elif decoder_config['data_type'] == 'int16_le':
                        length = 16
                        is_signed = True
                        is_little_endian = True
                    elif decoder_config['data_type'] == 'int16_be':
                        length = 16
                        is_signed = True
                        is_little_endian = False
                    else:
                        continue
                    
                    signal = SignalDefinition(
                        decoder_config['name'],
                        start_bit,
                        length,
                        decoder_config['scale'],
                        decoder_config['offset'],
                        is_signed,
                        is_little_endian,
                        decoder_config['unit']
                    )
                    self.decoder.add_signal_definition(can_id, signal)
                    
                    # Add to listbox
                    decoder_str = f"0x{can_id:X}: {decoder_config['name']} ({decoder_config['unit']})"
                    self.decoder_listbox.insert(tk.END, decoder_str)
                    count += 1
                
                self._update_plot_combos()
                messagebox.showinfo("Success", f"Loaded {count} predefined decoders for CAN ID 0x{can_id:X}")
            else:
                messagebox.showwarning("Warning", f"No predefined decoders for CAN ID {can_id_str}")
        except Exception as e:
            error_msg = f"Failed to load predefined decoders: {e}"
            self._show_error_banner(error_msg)
            messagebox.showerror("Error", error_msg)
    
    def _add_signal_decoder(self):
        """Add a new signal decoder"""
        try:
            can_id_str = self.decode_can_id_var.get()
            # Extract hex value if format is "NAME (0xXXX)"
            if '(' in can_id_str and ')' in can_id_str:
                can_id_str = can_id_str.split('(')[1].split(')')[0]
            can_id = int(can_id_str, 0)
            signal_name = self.signal_name_var.get()
            byte_index = int(self.byte_index_var.get())
            scale = float(self.scale_var.get())
            offset = float(self.offset_var.get())
            unit = self.unit_var.get()
            data_type = self.data_type_var.get()
            
            # Figure out signal parameters from data type
            if data_type == "uint8":
                start_bit = byte_index * 8
                length = 8
                is_signed = False
                is_little_endian = True
            elif data_type == "uint16_le":
                start_bit = byte_index * 8
                length = 16
                is_signed = False
                is_little_endian = True
            elif data_type == "uint16_be":
                start_bit = byte_index * 8
                length = 16
                is_signed = False
                is_little_endian = False
            elif data_type == "int16_le":
                start_bit = byte_index * 8
                length = 16
                is_signed = True
                is_little_endian = True
            elif data_type == "int16_be":
                start_bit = byte_index * 8
                length = 16
                is_signed = True
                is_little_endian = False
            else:
                raise ValueError(f"Unknown data type: {data_type}")
            
            signal = SignalDefinition(signal_name, start_bit, length, scale, offset,
                                     is_signed, is_little_endian, unit)
            self.decoder.add_signal_definition(can_id, signal)
            
            # Add to listbox and track it
            decoder_str = f"0x{can_id:X}: {signal_name} ({unit})"
            self.decoder_listbox.insert(tk.END, decoder_str)
            self.decoder_listbox_items.append((can_id, signal_name))
            
            # Update dropdowns
            self._update_plot_combos()
            
            messagebox.showinfo("Success", f"Added decoder for CAN ID 0x{can_id:X}, signal: {signal_name}")
            
        except Exception as e:
            error_msg = f"Failed to add decoder: {e}"
            self._show_error_banner(error_msg)
            messagebox.showerror("Error", error_msg)
    
    def _remove_signal_decoder(self):
        """Remove selected decoder from listbox and decoder"""
        selection = self.decoder_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a decoder to remove")
            return
        
        try:
            # Get the selected index
            index = selection[0]
            
            # Get the decoder info
            if index < len(self.decoder_listbox_items):
                can_id, signal_name = self.decoder_listbox_items[index]
                
                # Remove from decoder
                if can_id in self.decoder.signal_definitions:
                    # Find and remove the signal definition
                    signals_to_keep = [s for s in self.decoder.signal_definitions[can_id] 
                                      if s.name != signal_name]
                    if signals_to_keep:
                        self.decoder.signal_definitions[can_id] = signals_to_keep
                    else:
                        # No more signals for this CAN ID, remove the entry
                        del self.decoder.signal_definitions[can_id]
                
                # Remove from listbox
                self.decoder_listbox.delete(index)
                self.decoder_listbox_items.pop(index)
                
                # Remove from plot if it's being plotted
                key = f"0x{can_id:X}:{signal_name}"
                if key in self.plot_signals:
                    del self.plot_signals[key]
                    self._update_plot_legend()
                
                # Clear decoded data for this signal
                if can_id in self.decoded_data and signal_name in self.decoded_data[can_id]:
                    del self.decoded_data[can_id][signal_name]
                
                # Update dropdowns
                self._update_plot_combos()
                
                messagebox.showinfo("Success", f"Removed decoder: {signal_name} (0x{can_id:X})")
            else:
                messagebox.showerror("Error", "Invalid selection")
                
        except Exception as e:
            error_msg = f"Failed to remove decoder: {e}"
            self._show_error_banner(error_msg)
            messagebox.showerror("Error", error_msg)
    
    def _update_plot_combos(self):
        """Update the CAN ID and signal dropdowns"""
        can_ids = list(self.decoder.signal_definitions.keys())
        self.plot_id_combo['values'] = [f"0x{id:X}" for id in can_ids]
        
        if self.plot_can_id_var.get():
            try:
                can_id = int(self.plot_can_id_var.get(), 0)
                signals = self.decoder.get_available_signals(can_id)
                self.plot_signal_combo['values'] = signals
            except:
                pass
    
    def _add_to_plot(self):
        """Add a signal to the plot"""
        try:
            can_id_str = self.plot_can_id_var.get()
            signal_name = self.plot_signal_var.get()
            
            if not can_id_str or not signal_name:
                messagebox.showwarning("Warning", "Please select CAN ID and signal")
                return
            
            # Extract hex value if format is "NAME (0xXXX)"
            if '(' in can_id_str and ')' in can_id_str:
                can_id_str = can_id_str.split('(')[1].split(')')[0]
            can_id = int(can_id_str, 0)
            key = f"{can_id_str}:{signal_name}"
            
            if key not in self.plot_signals:
                self.plot_signals[key] = {
                    'can_id': can_id,
                    'signal': signal_name,
                    'color': self.colors[self.color_index % len(self.colors)]
                }
                self.color_index += 1
                self._update_plot_legend()
                self._update_plotted_signals_list()
                # Don't show messagebox for every add, just update silently
            else:
                messagebox.showinfo("Info", f"{signal_name} is already plotted")
            
        except Exception as e:
            error_msg = f"Failed to add to plot: {e}"
            self._show_error_banner(error_msg)
            messagebox.showerror("Error", error_msg)
    
    def _remove_from_plot(self):
        """Remove signal from plot using dropdown selection"""
        try:
            can_id_str = self.plot_can_id_var.get()
            signal_name = self.plot_signal_var.get()
            
            if not can_id_str or not signal_name:
                messagebox.showwarning("Warning", "Please select CAN ID and signal to remove")
                return
            
            # Extract hex value if format is "NAME (0xXXX)"
            if '(' in can_id_str and ')' in can_id_str:
                can_id_str = can_id_str.split('(')[1].split(')')[0]
            key = f"{can_id_str}:{signal_name}"
            
            if key in self.plot_signals:
                del self.plot_signals[key]
                self._update_plot_legend()
                self._update_plotted_signals_list()
                # Don't show messagebox, just update silently
            else:
                messagebox.showinfo("Info", f"{signal_name} is not currently plotted")
            
        except Exception as e:
            error_msg = f"Failed to remove from plot: {e}"
            self._show_error_banner(error_msg)
            messagebox.showerror("Error", error_msg)
    
    def _remove_selected_from_plot(self):
        """Remove selected signal from plotted signals listbox"""
        selection = self.plotted_signals_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a signal to remove from plot")
            return
        
        try:
            index = selection[0]
            item_text = self.plotted_signals_listbox.get(index)
            
            # Parse the item text to get the key
            # Format: "signal_name (CAN_ID) [unit]"
            parts = item_text.split(' (')
            if len(parts) >= 2:
                signal_name = parts[0]
                can_id_part = parts[1].split(')')[0]
                
                # Find the key in plot_signals
                for key, plot_info in list(self.plot_signals.items()):
                    if plot_info['signal'] == signal_name and f"0x{plot_info['can_id']:X}" == can_id_part:
                        del self.plot_signals[key]
                        self._update_plot_legend()
                        self._update_plotted_signals_list()
                        messagebox.showinfo("Success", f"Removed {signal_name} from plot")
                        return
                
                messagebox.showwarning("Warning", "Could not find signal to remove")
            else:
                messagebox.showerror("Error", "Invalid signal format")
                
        except Exception as e:
            error_msg = f"Failed to remove signal: {e}"
            self._show_error_banner(error_msg)
            messagebox.showerror("Error", error_msg)
    
    def _clear_all_plots(self):
        """Remove all signals from plot"""
        if self.plot_signals:
            self.plot_signals.clear()
            self._update_plot_legend()
            self._update_plotted_signals_list()
            messagebox.showinfo("Info", "All signals removed from plot")
        else:
            messagebox.showinfo("Info", "No signals to remove")
    
    def _update_plotted_signals_list(self):
        """Update the listbox showing currently plotted signals"""
        self.plotted_signals_listbox.delete(0, tk.END)
        
        for key, plot_info in self.plot_signals.items():
            can_id = plot_info['can_id']
            signal_name = plot_info['signal']
            
            # Get unit from decoder
            unit = ""
            for sig_def_list in self.decoder.signal_definitions.get(can_id, []):
                if sig_def_list.name == signal_name:
                    unit = sig_def_list.unit
                    break
            
            from can_ids import get_can_id_name
            can_id_name = get_can_id_name(can_id)
            
            if unit:
                display_text = f"{signal_name} ({can_id_name}) [{unit}]"
            else:
                display_text = f"{signal_name} ({can_id_name})"
            
            self.plotted_signals_listbox.insert(tk.END, display_text)
        
        # Adjust listbox height based on number of items
        num_items = len(self.plot_signals)
        self.plotted_signals_listbox.config(height=min(max(1, num_items), 4))
    
    def _update_plot_legend(self):
        """Update plot legend"""
        self.ax.clear()
        self.ax.set_facecolor('#fafafa')
        self.ax.set_xlabel("Time (s)", fontsize=11, fontweight='bold')
        self.ax.set_ylabel("Value", fontsize=11, fontweight='bold')
        self.ax.set_title("CAN Signal Values", fontsize=13, fontweight='bold', pad=15)
        self.ax.grid(True, alpha=0.4, linestyle='--', linewidth=0.5)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['left'].set_color('#cccccc')
        self.ax.spines['bottom'].set_color('#cccccc')
        
        if self.plot_signals:
            labels = [f"{v['signal']} (0x{v['can_id']:X})" 
                     for v in self.plot_signals.values()]
            self.ax.legend(labels, loc='best')
        
        self.canvas.draw()
    
    def _update_plot_selection(self):
        """Update signal dropdown when CAN ID changes"""
        try:
            can_id_str = self.plot_can_id_var.get()
            if can_id_str:
                # Extract hex value if format is "NAME (0xXXX)"
                if '(' in can_id_str and ')' in can_id_str:
                    can_id_str = can_id_str.split('(')[1].split(')')[0]
                can_id = int(can_id_str, 0)
                signals = self.decoder.get_available_signals(can_id)
                self.plot_signal_combo['values'] = signals
                if signals:
                    self.plot_signal_var.set(signals[0])
        except:
            pass
    
    def _toggle_connection(self):
        """Connect or disconnect"""
        if not self.is_connected:
            self._connect()
        else:
            self._disconnect()
    
    def _connect(self):
        """Connect to CAN bus"""
        try:
            interface = self.interface_var.get()
            channel = self.channel_var.get()
            bitrate = int(self.bitrate_var.get())
            
            self.reader = CANReader(interface=interface, channel=channel, bitrate=bitrate)
            
            if self.reader.connect():
                self.is_connected = True
                self.connect_btn.config(text="Disconnect")
                self.status_label.config(text="Status: Connected", foreground="#28a745")
                self.capture_btn.config(state=tk.NORMAL)
                self._hide_error_banner()  # Clear any previous errors
                messagebox.showinfo("Success", f"Connected to {interface} on {channel}")
            else:
                error_msg = "Failed to connect to CAN bus. Check interface and channel settings."
                self._show_error_banner(error_msg)
                messagebox.showerror("Error", error_msg)
                
        except Exception as e:
            error_msg = f"Connection error: {e}"
            self._show_error_banner(error_msg)
            messagebox.showerror("Error", error_msg)
    
    def _disconnect(self):
        """Disconnect from CAN bus"""
        if self.is_capturing:
            self._toggle_capture()
        
        if self.reader:
            self.reader.disconnect()
            self.reader = None
        
        self.is_connected = False
        self.connect_btn.config(text="Connect")
        self.status_label.config(text="Status: Disconnected", foreground="#dc3545")
        self.capture_btn.config(state=tk.DISABLED)
    
    def _toggle_capture(self):
        """Start or stop capturing messages"""
        if not self.is_capturing:
            self._start_capture()
        else:
            self._stop_capture()
    
    def _start_capture(self):
        """Start reading CAN messages"""
        if not self.is_connected:
            error_msg = "Not connected to CAN bus. Please connect first."
            self._show_error_banner(error_msg)
            messagebox.showerror("Error", error_msg)
            return
        
        self.is_capturing = True
        self.capture_btn.config(text="Stop Capture")
        self.stop_processing = False
        
        # Start reading messages in background thread
        self.read_thread = threading.Thread(target=self._read_messages_thread, daemon=True)
        self.read_thread.start()
        
        # Process messages in another thread
        self.processing_thread = threading.Thread(target=self._process_messages_thread, daemon=True)
        self.processing_thread.start()
        
        # Update plot every 100ms
        self.ani = animation.FuncAnimation(self.fig, self._update_plot, interval=100, blit=False)
        
    def _stop_capture(self):
        """Stop capturing"""
        self.is_capturing = False
        self.stop_processing = True
        self.capture_btn.config(text="Start Capture")
        
        if self.ani:
            self.ani.event_source.stop()
    
    def _read_messages_thread(self):
        """Background thread to read CAN messages"""
        while self.is_capturing and not self.stop_processing:
            try:
                if self.reader and self.reader.bus:
                    msg = self.reader.bus.recv(timeout=0.1)
                    if msg is not None:
                        self.message_queue.put({
                            'timestamp': datetime.now(),
                            'arbitration_id': msg.arbitration_id,
                            'data': msg.data,
                            'dlc': msg.dlc
                        })
            except Exception as e:
                if self.is_capturing:
                    error_msg = f"Error reading CAN message: {e}"
                    self._show_error_banner(error_msg)
                    print(f"Error reading message: {e}")
    
    def _process_messages_thread(self):
        """Background thread to decode messages and update data"""
        while not self.stop_processing:
            try:
                if not self.message_queue.empty():
                    msg = self.message_queue.get(timeout=0.1)
                    self._process_message(msg)
            except queue.Empty:
                continue
            except Exception as e:
                error_msg = f"Error processing message: {e}"
                self._show_error_banner(error_msg)
                print(f"Error processing message: {e}")
    
    def _process_message(self, msg):
        """Decode a message and store the values"""
        can_id = msg['arbitration_id']
        data = msg['data']
        timestamp = msg['timestamp']
        
        # Decode it
        decoded = self.decoder.decode_message(can_id, data)
        
        # Store decoded values
        for signal_name, value in decoded.items():
            if value is not None:
                self.decoded_data[can_id][signal_name].append({
                    'timestamp': timestamp,
                    'value': value
                })
                
                # Don't keep too much data
                max_points = int(self.max_points_var.get())
                if len(self.decoded_data[can_id][signal_name]) > max_points:
                    self.decoded_data[can_id][signal_name].popleft()
        
        # Show in message display
        filter_id = self.filter_id_var.get()
        if not filter_id or f"{can_id:X}" == filter_id.replace("0x", "").upper():
            self._display_message(msg, decoded)
    
    def _display_message(self, msg, decoded):
        """Show message in text area"""
        can_id = msg['arbitration_id']
        data_hex = ' '.join([f"{b:02X}" for b in msg['data']])
        timestamp_str = msg['timestamp'].strftime("%H:%M:%S.%f")[:-3]
        
        line = f"[{timestamp_str}] 0x{can_id:03X}  [{msg['dlc']}] {data_hex}"
        
        if decoded:
            # Format decoded values nicely
            decoded_parts = []
            for k, v in decoded.items():
                if v is None:
                    continue
                if isinstance(v, float):
                    # Use appropriate decimal places based on signal type and unit
                    if 'temperature' in k.lower() or '°C' in str(decoded.get(k, '')):
                        decoded_parts.append(f"{k}={v:.2f}°C")
                    elif 'voltage' in k.lower() or 'V' in str(decoded.get(k, '')):
                        decoded_parts.append(f"{k}={v:.3f}V")
                    else:
                        decoded_parts.append(f"{k}={v:.2f}")
                else:
                    decoded_parts.append(f"{k}={v}")
            
            if decoded_parts:
                line += f"  |  {', '.join(decoded_parts)}"
        
        line += "\n"
        
        self.message_text.insert(tk.END, line)
        self.message_text.see(tk.END)
        
        # Don't let it get too long
        lines = int(self.message_text.index('end-1c').split('.')[0])
        if lines > 1000:
            self.message_text.delete('1.0', '500.0')
    
    def _update_message_filter(self):
        """Update message filter (handled in _process_message)"""
        pass
    
    def _update_plot(self, frame):
        """Update the plot with latest data"""
        if not self.plot_signals:
            return
        
        self.ax.clear()
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.ax.set_title("CAN Signal Values")
        self.ax.grid(True, alpha=0.3)
        
        if not self.decoded_data:
            self.canvas.draw()
            return
        
        # Find most recent timestamp to use as reference
        ref_time = None
        for can_id, signals in self.decoded_data.items():
            for signal_name, data_points in signals.items():
                if data_points:
                    ref_time = data_points[-1]['timestamp']
                    break
            if ref_time:
                break
        
        if not ref_time:
            self.canvas.draw()
            return
        
        # Plot each signal
        for key, plot_info in self.plot_signals.items():
            can_id = plot_info['can_id']
            signal_name = plot_info['signal']
            color = plot_info['color']
            
            if can_id in self.decoded_data and signal_name in self.decoded_data[can_id]:
                data_points = self.decoded_data[can_id][signal_name]
                if data_points:
                    # Convert timestamps to seconds relative to ref_time
                    times = [(dp['timestamp'] - ref_time).total_seconds() 
                            for dp in data_points]
                    values = [dp['value'] for dp in data_points]
                    
                    # Get CAN ID name and unit if available
                    from can_ids import get_can_id_name
                    can_id_name = get_can_id_name(can_id)
                    
                    # Get unit from decoder
                    unit = ""
                    for sig_def_list in self.decoder.signal_definitions.get(can_id, []):
                        if sig_def_list.name == signal_name:
                            unit = sig_def_list.unit
                            break
                    
                    if unit:
                        label = f"{signal_name} ({can_id_name}) [{unit}]"
                    else:
                        label = f"{signal_name} ({can_id_name})"
                    
                    # Use nicer line styling
                    self.ax.plot(times, values, color=color, label=label, 
                               linewidth=2.5, alpha=0.8, marker='o', markersize=3, markevery=10)
        
        if self.plot_signals:
            self.ax.legend(loc='best', fontsize=10, framealpha=0.9, 
                         fancybox=True, shadow=True, frameon=True)
            # Set y-axis label based on what's being plotted
            units = set()
            for plot_info in self.plot_signals.values():
                can_id = plot_info['can_id']
                signal_name = plot_info['signal']
                if can_id in self.decoded_data and signal_name in self.decoded_data[can_id]:
                    # Try to get unit from decoder
                    for sig_def_list in self.decoder.signal_definitions.get(can_id, []):
                        if sig_def_list.name == signal_name:
                            units.add(sig_def_list.unit)
                            break
            
            if len(units) == 1:
                unit_str = list(units)[0]
                if unit_str:
                    self.ax.set_ylabel(f"Value ({unit_str})")
                else:
                    self.ax.set_ylabel("Value")
            elif len(units) > 1:
                # Multiple units - show as "Value (mixed units)"
                self.ax.set_ylabel("Value (mixed units)")
            else:
                self.ax.set_ylabel("Value")
        
        self.canvas.draw()
    
    def _clear_data(self):
        """Clear all data"""
        self.decoded_data.clear()
        self.message_text.delete('1.0', tk.END)
        self.ax.clear()
        self.ax.set_facecolor('#fafafa')
        self.ax.set_xlabel("Time (s)", fontsize=11, fontweight='bold')
        self.ax.set_ylabel("Value", fontsize=11, fontweight='bold')
        self.ax.set_title("CAN Signal Values", fontsize=13, fontweight='bold', pad=15)
        self.ax.grid(True, alpha=0.4, linestyle='--', linewidth=0.5)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['left'].set_color('#cccccc')
        self.ax.spines['bottom'].set_color('#cccccc')
        self._update_plotted_signals_list()
        self.canvas.draw()
        messagebox.showinfo("Info", "Data cleared")
    
    def _export_csv(self):
        """Export decoded data to CSV file"""
        if not self.decoded_data:
            messagebox.showwarning("Warning", "No data to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                import csv
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Timestamp', 'CAN_ID', 'Signal', 'Value'])
                    
                    for can_id, signals in self.decoded_data.items():
                        for signal_name, data_points in signals.items():
                            for dp in data_points:
                                writer.writerow([
                                    dp['timestamp'].isoformat(),
                                    f"0x{can_id:X}",
                                    signal_name,
                                    dp['value']
                                ])
                
                messagebox.showinfo("Success", f"Data exported to {filename}")
            except Exception as e:
                error_msg = f"Failed to export CSV: {e}"
                self._show_error_banner(error_msg)
                messagebox.showerror("Error", error_msg)


def main():
    root = tk.Tk()
    app = CANAnalyzerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
