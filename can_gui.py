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
        self.root.minsize(1000, 600)  # Set minimum window size
        
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
        self.error_banner_outer = None
        self.error_label = None
        self.error_title_label = None
        self.current_error = None
        self.error_banner_flashing = False
        
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
        
        # Create scrollable left frame for controls
        left_container = ttk.Frame(main_paned)
        main_paned.add(left_container, weight=1)
        
        # Canvas and scrollbar for left panel
        self.left_canvas = tk.Canvas(left_container, bg='#f0f0f0', highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=self.left_canvas.yview)
        left_frame = ttk.Frame(self.left_canvas)
        
        # Configure scrollable region
        def update_scroll_region(event=None):
            self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
        
        left_frame.bind("<Configure>", update_scroll_region)
        
        canvas_window = self.left_canvas.create_window((0, 0), window=left_frame, anchor="nw")
        self.left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        # Update canvas window width when canvas is resized
        def configure_canvas_width(event):
            canvas_width = event.width
            self.left_canvas.itemconfig(canvas_window, width=canvas_width)
        
        self.left_canvas.bind('<Configure>', configure_canvas_width)
        
        # Pack canvas and scrollbar
        self.left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Mouse wheel scrolling for left panel
        def _on_mousewheel(event):
            self.left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.left_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Create vertical paned window for right side (messages and plots)
        right_paned = ttk.PanedWindow(main_paned, orient=tk.VERTICAL)
        main_paned.add(right_paned, weight=3)
        
        # Top: Message display
        msg_container = ttk.Frame(right_paned)
        right_paned.add(msg_container, weight=1)
        
        # Bottom: Plot area
        plot_container = ttk.Frame(right_paned)
        right_paned.add(plot_container, weight=2)
        
        self._setup_connection_panel(left_frame)
        self._setup_decoder_panel(left_frame)
        self._setup_plot_controls(left_frame)
        self._setup_message_display(msg_container)
        self._setup_plot_area(plot_container)
    
    def _setup_error_banner(self):
        """Create error banner at the top of the window - visible and user-friendly"""
        # Outer frame with border/shadow effect
        self.error_banner_outer = tk.Frame(self.root, bg="#8B0000", height=0)
        self.error_banner_outer.pack_propagate(False)
        
        # Main error banner frame with bright red background
        self.error_banner_frame = tk.Frame(self.error_banner_outer, bg="#FF4444", 
                                          relief=tk.RAISED, bd=3)
        self.error_banner_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Error content frame with padding
        error_content = tk.Frame(self.error_banner_frame, bg="#FF4444")
        error_content.pack(fill=tk.X, padx=15, pady=12)
        
        # Left side: Large error icon
        icon_frame = tk.Frame(error_content, bg="#FF4444")
        icon_frame.pack(side=tk.LEFT, padx=(0, 15))
        
        error_icon = tk.Label(icon_frame, text="⚠", bg="#FF4444", 
                             fg="white", font=('Segoe UI', 24, 'bold'))
        error_icon.pack()
        
        # Center: Error message with better styling
        message_frame = tk.Frame(error_content, bg="#FF4444")
        message_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Error title
        self.error_title_label = tk.Label(message_frame, text="ERROR", 
                                         bg="#FF4444", fg="white", 
                                         font=('Segoe UI', 11, 'bold'),
                                         anchor=tk.W)
        self.error_title_label.pack(anchor=tk.W, pady=(0, 3))
        
        # Error message
        self.error_label = tk.Label(message_frame, text="", bg="#FF4444", 
                                    fg="white", font=('Segoe UI', 11),
                                    wraplength=1100, justify=tk.LEFT,
                                    anchor=tk.W)
        self.error_label.pack(anchor=tk.W, fill=tk.X)
        
        # Right side: Close button (more obvious)
        close_frame = tk.Frame(error_content, bg="#FF4444")
        close_frame.pack(side=tk.RIGHT, padx=(15, 0))
        
        close_btn = tk.Button(close_frame, text="✕ CLOSE", bg="#CC0000", fg="white",
                             font=('Segoe UI', 10, 'bold'), relief=tk.RAISED,
                             command=self._hide_error_banner, cursor="hand2",
                             activebackground="#990000", activeforeground="white",
                             bd=2, padx=12, pady=6,
                             highlightthickness=2, highlightbackground="#FF6666")
        close_btn.pack()
        
        # Animation state
        self.error_banner_flashing = False
        
        # Initially hidden
        self._hide_error_banner()
    
    def _flash_error_banner(self, count=0):
        """Flash the error banner to draw attention"""
        if not self.error_banner_frame or not self.error_banner_flashing:
            return
        
        try:
            if count < 6:  # Flash 6 times (3 cycles)
                if count % 2 == 0:
                    # Brighter red flash
                    bg_color = "#FF0000"
                    btn_bg = "#AA0000"
                else:
                    # Normal red
                    bg_color = "#FF4444"
                    btn_bg = "#CC0000"
                
                # Update main frame
                self.error_banner_frame.config(bg=bg_color)
                
                # Update all child widgets
                self._update_widget_colors(self.error_banner_frame, bg_color, btn_bg)
                
                # Schedule next flash
                self.root.after(150, lambda: self._flash_error_banner(count + 1))
            else:
                self.error_banner_flashing = False
        except tk.TclError:
            # Widget destroyed, stop flashing
            self.error_banner_flashing = False
    
    def _update_widget_colors(self, parent, bg_color, btn_bg):
        """Recursively update widget colors"""
        try:
            for widget in parent.winfo_children():
                if isinstance(widget, tk.Frame):
                    widget.config(bg=bg_color)
                    self._update_widget_colors(widget, bg_color, btn_bg)
                elif isinstance(widget, tk.Label):
                    widget.config(bg=bg_color)
                elif isinstance(widget, tk.Button):
                    widget.config(bg=btn_bg, activebackground="#990000")
        except (tk.TclError, AttributeError):
            pass  # Widget might be destroyed
    
    def _show_error_banner(self, error_message):
        """Show error banner with message - make it very obvious"""
        self.current_error = error_message
        if self.error_label and self.error_banner_frame:
            # Update message
            self.error_label.config(text=error_message)
            
            # Determine error type for title
            error_lower = error_message.lower()
            if "connection" in error_lower or "connect" in error_lower:
                error_type = "CONNECTION ERROR"
            elif "decoder" in error_lower:
                error_type = "DECODER ERROR"
            elif "plot" in error_lower:
                error_type = "PLOT ERROR"
            elif "export" in error_lower:
                error_type = "EXPORT ERROR"
            elif "reading message" in error_lower or "processing message" in error_lower:
                error_type = "CAN MESSAGE ERROR"
            else:
                error_type = "ERROR"
            
            self.error_title_label.config(text=error_type)
            
            # Set height to be more prominent
            self.error_banner_outer.config(height=80)
            
            # Pack it at the top (most visible position)
            try:
                # Try to pack before other widgets
                children = self.root.winfo_children()
                if children and self.error_banner_outer not in children:
                    self.error_banner_outer.pack(fill=tk.X, side=tk.TOP, padx=0, pady=0, before=children[0])
                elif self.error_banner_outer not in children:
                    self.error_banner_outer.pack(fill=tk.X, side=tk.TOP, padx=0, pady=0)
            except (tk.TclError, IndexError, AttributeError):
                # Fallback: just pack normally
                try:
                    self.error_banner_outer.pack(fill=tk.X, side=tk.TOP, padx=0, pady=0)
                except tk.TclError:
                    pass  # Already packed
            
            # Flash animation to draw attention
            self.error_banner_flashing = True
            self._flash_error_banner(0)
            
            # Auto-hide after 10 seconds (optional, user can still close manually)
            if hasattr(self, '_error_auto_hide_id'):
                self.root.after_cancel(self._error_auto_hide_id)
            self._error_auto_hide_id = self.root.after(10000, self._hide_error_banner)
    
    def _hide_error_banner(self):
        """Hide error banner"""
        self.current_error = None
        self.error_banner_flashing = False
        if self.error_banner_outer:
            self.error_banner_outer.config(height=0)
            self.error_banner_outer.pack_forget()
        
        # Cancel auto-hide if scheduled
        if hasattr(self, '_error_auto_hide_id'):
            self.root.after_cancel(self._error_auto_hide_id)
            delattr(self, '_error_auto_hide_id')
        
    def _setup_connection_panel(self, parent):
        """CAN connection settings"""
        conn_frame = ttk.LabelFrame(parent, text="CAN Connection", padding=10)
        conn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Configure grid weights for responsive layout
        conn_frame.columnconfigure(1, weight=1)
        
        # Interface dropdown
        ttk.Label(conn_frame, text="Interface:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.interface_var = tk.StringVar(value="slcan")
        interface_combo = ttk.Combobox(conn_frame, textvariable=self.interface_var,
                                       values=["slcan", "socketcan", "usb2can", "pcan", 
                                              "ixxat", "vector", "virtual"],
                                       state="readonly", width=15)
        interface_combo.grid(row=0, column=1, sticky=tk.EW, pady=2, padx=5)
        
        # Channel/device name
        ttk.Label(conn_frame, text="Channel:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.channel_var = tk.StringVar(value="COM3")
        channel_entry = ttk.Entry(conn_frame, textvariable=self.channel_var, width=18)
        channel_entry.grid(row=1, column=1, sticky=tk.EW, pady=2, padx=5)
        
        # Bitrate
        ttk.Label(conn_frame, text="Bitrate:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.bitrate_var = tk.StringVar(value="500000")
        bitrate_combo = ttk.Combobox(conn_frame, textvariable=self.bitrate_var,
                                     values=["125000", "250000", "500000", "1000000"],
                                     state="readonly", width=15)
        bitrate_combo.grid(row=2, column=1, sticky=tk.EW, pady=2, padx=5)
        
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
        
        # Configure grid weights for responsive layout
        decoder_frame.columnconfigure(1, weight=1)
        
        # CAN ID (hex) - dropdown with predefined IDs
        ttk.Label(decoder_frame, text="CAN ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.decode_can_id_var = tk.StringVar(value="")
        decode_id_combo = ttk.Combobox(decoder_frame, textvariable=self.decode_can_id_var,
                                      values=[f"{name} ({get_can_id_hex(cid)})" for name, cid in CAN_IDS.items()] + 
                                             [get_can_id_hex(cid) for cid in CAN_IDS.values()],
                                      width=20)
        decode_id_combo.grid(row=0, column=1, sticky=tk.EW, pady=2, padx=5)
        decode_id_combo.bind('<<ComboboxSelected>>', self._on_can_id_selected)
        self.decode_id_combo = decode_id_combo
        
        # Signal name (voltage, temperature, etc.)
        ttk.Label(decoder_frame, text="Signal Name:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.signal_name_var = tk.StringVar(value="voltage")
        signal_entry = ttk.Entry(decoder_frame, textvariable=self.signal_name_var, width=12)
        signal_entry.grid(row=1, column=1, sticky=tk.EW, pady=2, padx=5)
        
        # Which byte to start reading from
        ttk.Label(decoder_frame, text="Byte Index:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.byte_index_var = tk.StringVar(value="0")
        byte_entry = ttk.Entry(decoder_frame, textvariable=self.byte_index_var, width=12)
        byte_entry.grid(row=2, column=1, sticky=tk.EW, pady=2, padx=5)
        
        # Scale factor (multiply raw value by this)
        ttk.Label(decoder_frame, text="Scale:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.scale_var = tk.StringVar(value="0.1")
        scale_entry = ttk.Entry(decoder_frame, textvariable=self.scale_var, width=12)
        scale_entry.grid(row=3, column=1, sticky=tk.EW, pady=2, padx=5)
        
        # Offset (add this to scaled value)
        ttk.Label(decoder_frame, text="Offset:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.offset_var = tk.StringVar(value="0")
        offset_entry = ttk.Entry(decoder_frame, textvariable=self.offset_var, width=12)
        offset_entry.grid(row=4, column=1, sticky=tk.EW, pady=2, padx=5)
        
        # Unit (V, °C, A, etc.)
        ttk.Label(decoder_frame, text="Unit:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.unit_var = tk.StringVar(value="V")
        unit_combo = ttk.Combobox(decoder_frame, textvariable=self.unit_var,
                                 values=["V", "°C", "A", "rpm", "km/h", "bar", "kg", ""],
                                 state="readonly", width=10)
        unit_combo.grid(row=5, column=1, sticky=tk.EW, pady=2, padx=5)
        
        # Data type (8-bit, 16-bit, signed/unsigned, endianness)
        ttk.Label(decoder_frame, text="Data Type:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.data_type_var = tk.StringVar(value="uint16_le")
        data_type_combo = ttk.Combobox(decoder_frame, textvariable=self.data_type_var,
                                       values=["uint8", "uint16_le", "uint16_be", 
                                              "int16_le", "int16_be"],
                                       state="readonly", width=12)
        data_type_combo.grid(row=6, column=1, sticky=tk.EW, pady=2, padx=5)
        
        # Add decoder button
        add_decoder_btn = ttk.Button(decoder_frame, text="Add Signal", 
                                     command=self._add_signal_decoder)
        add_decoder_btn.grid(row=7, column=0, columnspan=2, pady=10, sticky=tk.EW)
        
        # Quick preset buttons
        preset_frame = ttk.Frame(decoder_frame)
        preset_frame.grid(row=8, column=0, columnspan=2, pady=5, sticky=tk.EW)
        preset_frame.columnconfigure(0, weight=1)
        preset_frame.columnconfigure(1, weight=1)
        preset_frame.columnconfigure(2, weight=1)
        preset_frame.columnconfigure(3, weight=1)
        
        ttk.Button(preset_frame, text="Voltage Ch1", 
                  command=lambda: self._apply_preset("analog_voltage_in1")).grid(row=0, column=0, sticky=tk.EW, padx=2)
        ttk.Button(preset_frame, text="Internal Voltage", 
                  command=lambda: self._apply_preset("internal_voltage")).grid(row=0, column=1, sticky=tk.EW, padx=2)
        ttk.Button(preset_frame, text="Temperature", 
                  command=lambda: self._apply_preset("temperature")).grid(row=0, column=2, sticky=tk.EW, padx=2)
        ttk.Button(preset_frame, text="Load Predefined", 
                  command=self._load_predefined_decoders).grid(row=0, column=3, sticky=tk.EW, padx=2)
        
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
        
        # Filter by CAN ID - responsive layout
        filter_frame = ttk.Frame(msg_frame)
        filter_frame.pack(fill=tk.X, pady=2)
        filter_frame.columnconfigure(1, weight=1)
        
        ttk.Label(filter_frame, text="Filter CAN ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.filter_id_var = tk.StringVar(value="")
        filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_id_var)
        filter_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
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
        
        # Controls to add/remove signals from plot - use grid for responsive layout
        plot_select_frame = ttk.Frame(plot_frame)
        plot_select_frame.pack(fill=tk.X, pady=2)
        
        # Configure grid columns for responsive layout
        plot_select_frame.columnconfigure(1, weight=2)  # CAN ID combo
        plot_select_frame.columnconfigure(2, weight=1)   # Signal combo
        plot_select_frame.columnconfigure(5, weight=3)  # Plotted listbox
        
        # Row 0: CAN ID and Signal selection
        ttk.Label(plot_select_frame, text="Plot Signal:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.plot_can_id_var = tk.StringVar(value="")
        # Make combobox editable to allow manual CAN ID entry
        # Include all predefined CAN IDs, especially defaults (0x259, 0x25E)
        default_values = [f"{name} ({get_can_id_hex(cid)})" for name, cid in CAN_IDS.items()] + \
                        [get_can_id_hex(cid) for cid in CAN_IDS.values()]
        plot_id_combo = ttk.Combobox(plot_select_frame, textvariable=self.plot_can_id_var,
                                     values=default_values,
                                     state="normal")  # Changed to "normal" to allow manual entry
        plot_id_combo.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        plot_id_combo.bind('<<ComboboxSelected>>', lambda e: self._update_plot_selection())
        plot_id_combo.bind('<KeyRelease>', lambda e: self._update_plot_selection())  # Update on typing
        
        self.plot_signal_var = tk.StringVar(value="")
        plot_signal_combo = ttk.Combobox(plot_select_frame, textvariable=self.plot_signal_var,
                                        state="readonly")
        plot_signal_combo.grid(row=0, column=2, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Button(plot_select_frame, text="Add to Plot", 
                  command=self._add_to_plot).grid(row=0, column=3, sticky=tk.EW, padx=5, pady=2)
        ttk.Button(plot_select_frame, text="Remove", 
                  command=self._remove_from_plot).grid(row=0, column=4, sticky=tk.EW, padx=5, pady=2)
        
        # Row 1: Plotted signals list
        ttk.Label(plot_select_frame, text="Plotted:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        
        # Frame for listbox and scrollbar
        listbox_frame = ttk.Frame(plot_select_frame)
        listbox_frame.grid(row=1, column=1, columnspan=3, sticky=tk.EW, padx=5, pady=2)
        listbox_frame.columnconfigure(0, weight=1)
        
        self.plotted_signals_listbox = tk.Listbox(listbox_frame, height=3)
        self.plotted_signals_listbox.grid(row=0, column=0, sticky=tk.EW)
        
        # Scrollbar for plotted signals listbox
        plotted_scroll = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL,
                                       command=self.plotted_signals_listbox.yview)
        plotted_scroll.grid(row=0, column=1, sticky=tk.NS)
        self.plotted_signals_listbox.config(yscrollcommand=plotted_scroll.set)
        
        ttk.Button(plot_select_frame, text="Remove Selected", 
                  command=self._remove_selected_from_plot).grid(row=1, column=4, sticky=tk.EW, padx=5, pady=2)
        ttk.Button(plot_select_frame, text="Clear All", 
                  command=self._clear_all_plots).grid(row=1, column=5, sticky=tk.EW, padx=5, pady=2)
        
        # Configure column weights for buttons (no expansion)
        plot_select_frame.columnconfigure(3, weight=0)
        plot_select_frame.columnconfigure(4, weight=0)
        plot_select_frame.columnconfigure(5, weight=0)
        
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
            
            # Update dropdowns after loading all defaults
            self._update_plot_combos()
    
    def _apply_preset(self, preset_type):
        """Quick preset for default signals: analog_voltage_in1, internal_voltage, or temperature"""
        if preset_type == "analog_voltage_in1":
            # Analog voltage in1: CAN ID 0x259, byte 0, scale 0.001, unit V
            self.decode_can_id_var.set("0x259")
            self.signal_name_var.set("analog_voltage_in1")
            self.byte_index_var.set("0")
            self.scale_var.set("0.001")
            self.offset_var.set("0")
            self.unit_var.set("V")
            self.data_type_var.set("uint16_le")
        elif preset_type == "internal_voltage":
            # Internal voltage: CAN ID 0x25E, byte 2, scale 0.001, unit V
            self.decode_can_id_var.set("0x25E")
            self.signal_name_var.set("internal_voltage")
            self.byte_index_var.set("2")
            self.scale_var.set("0.001")
            self.offset_var.set("0")
            self.unit_var.set("V")
            self.data_type_var.set("uint16_le")
        elif preset_type == "temperature":
            # Temperature: CAN ID 0x25E, byte 4, scale 0.001, unit °C
            self.decode_can_id_var.set("0x25E")
            self.signal_name_var.set("temperature")
            self.byte_index_var.set("4")
            self.scale_var.set("0.001")
            self.offset_var.set("0")
            self.unit_var.set("°C")
            self.data_type_var.set("uint16_le")
    
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
                    
                    # Add to listbox and track it
                    decoder_str = f"0x{can_id:X}: {decoder_config['name']} ({decoder_config['unit']})"
                    self.decoder_listbox.insert(tk.END, decoder_str)
                    self.decoder_listbox_items.append((can_id, decoder_config['name']))
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
        # Include all predefined CAN IDs plus any with decoders
        predefined_ids = list(CAN_IDS.values())
        decoder_ids = list(self.decoder.signal_definitions.keys())
        all_ids = sorted(set(predefined_ids + decoder_ids))
        
        # Build values list with names and hex
        values = []
        for cid in all_ids:
            # Add named version if available
            if cid in CAN_ID_NAMES:
                values.append(f"{CAN_ID_NAMES[cid]} ({get_can_id_hex(cid)})")
            # Add hex version
            values.append(get_can_id_hex(cid))
        
        # Update combobox values (keep existing selection if valid)
        current_value = self.plot_can_id_var.get()
        self.plot_id_combo['values'] = values
        
        # Restore selection if it was valid
        if current_value and current_value in values:
            self.plot_can_id_var.set(current_value)
        
        # Update signal dropdown
        if self.plot_can_id_var.get():
            try:
                can_id_str = self.plot_can_id_var.get()
                # Extract hex value if format is "NAME (0xXXX)"
                if '(' in can_id_str and ')' in can_id_str:
                    can_id_str = can_id_str.split('(')[1].split(')')[0]
                can_id = int(can_id_str, 0)
                signals = self.decoder.get_available_signals(can_id)
                self.plot_signal_combo['values'] = signals
                if signals and not self.plot_signal_var.get():
                    self.plot_signal_var.set(signals[0])
            except:
                pass
    
    def _add_to_plot(self):
        """Add a signal to the plot"""
        try:
            can_id_str = self.plot_can_id_var.get().strip()
            signal_name = self.plot_signal_var.get().strip()
            
            if not can_id_str:
                messagebox.showwarning("Warning", "Please enter or select a CAN ID")
                return
            
            if not signal_name:
                messagebox.showwarning("Warning", "Please select a signal")
                return
            
            # Extract hex value if format is "NAME (0xXXX)"
            if '(' in can_id_str and ')' in can_id_str:
                can_id_str = can_id_str.split('(')[1].split(')')[0].strip()
            
            # Parse CAN ID (supports hex, decimal, etc.)
            try:
                can_id = int(can_id_str, 0)
            except ValueError:
                messagebox.showerror("Error", f"Invalid CAN ID format: {can_id_str}\nUse hex (0x259) or decimal (601)")
                return
            
            # Normalize CAN ID string for key
            can_id_hex = f"0x{can_id:X}"
            key = f"{can_id_hex}:{signal_name}"
            
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
        """Update plot legend - refresh plot with current signals"""
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
        
        # Create professional legend entries even when no data yet
        if self.plot_signals:
            legend_handles = []
            legend_labels = []
            
            from can_ids import get_can_id_hex
            
            for plot_info in self.plot_signals.values():
                can_id = plot_info['can_id']
                signal_name = plot_info['signal']
                color = plot_info['color']
                can_id_hex = get_can_id_hex(can_id)
                
                # Get unit from decoder
                unit = ""
                for sig_def_list in self.decoder.signal_definitions.get(can_id, []):
                    if sig_def_list.name == signal_name:
                        unit = sig_def_list.unit
                        break
                
                # Create clear label distinguishing different signals from same CAN ID
                if unit:
                    # Use clearer formatting to distinguish signals from same CAN ID
                    if signal_name == 'temperature':
                        label = f"Temperature | {can_id_hex} | {unit}"
                    elif signal_name == 'internal_voltage':
                        label = f"Internal Voltage | {can_id_hex} | {unit}"
                    elif signal_name == 'analog_voltage_in1':
                        label = f"Analog Voltage In1 | {can_id_hex} | {unit}"
                    else:
                        label = f"{signal_name.replace('_', ' ').title()} | {can_id_hex} | {unit}"
                else:
                    label = f"{signal_name.replace('_', ' ').title()} | {can_id_hex}"
                
                # Create empty line for legend (no data yet)
                line, = self.ax.plot([], [], color=color, label=label,
                                   linewidth=2.5, alpha=0.85, marker='o',
                                   markersize=4, antialiased=True)
                
                legend_handles.append(line)
                legend_labels.append(label)
            
            # Create professional legend
            legend = self.ax.legend(handles=legend_handles, labels=legend_labels,
                                  loc='upper left', fontsize=9.5,
                                  framealpha=0.95, fancybox=True, shadow=True,
                                  frameon=True, edgecolor='#333333',
                                  facecolor='white', borderpad=0.8,
                                  labelspacing=0.7, columnspacing=1.2,
                                  handlelength=2.5, handletextpad=0.8)
            
            # Style legend text
            for text in legend.get_texts():
                text.set_fontweight('normal')
                text.set_fontfamily('monospace')
            
            # Add subtle border
            legend.get_frame().set_linewidth(1.2)
            legend.get_frame().set_linestyle('-')
        
        self.canvas.draw()
    
    def _update_plot_selection(self):
        """Update signal dropdown when CAN ID changes"""
        try:
            can_id_str = self.plot_can_id_var.get()
            if can_id_str:
                # Extract hex value if format is "NAME (0xXXX)"
                if '(' in can_id_str and ')' in can_id_str:
                    can_id_str = can_id_str.split('(')[1].split(')')[0]
                
                # Try to parse CAN ID (supports hex, decimal, etc.)
                try:
                    can_id = int(can_id_str, 0)
                except ValueError:
                    # Invalid CAN ID format, clear signal dropdown
                    self.plot_signal_combo['values'] = []
                    self.plot_signal_var.set("")
                    return
                
                # Get available signals for this CAN ID
                signals = self.decoder.get_available_signals(can_id)
                
                # If no signals found but this is a default CAN ID, suggest default signals
                if not signals and can_id in DEFAULT_DECODERS:
                    default_signals = [sig['name'] for sig in DEFAULT_DECODERS[can_id]]
                    signals = default_signals
                
                self.plot_signal_combo['values'] = signals
                if signals:
                    # Auto-select first signal if none selected
                    if not self.plot_signal_var.get() or self.plot_signal_var.get() not in signals:
                        self.plot_signal_var.set(signals[0])
                else:
                    # No signals available, clear selection
                    self.plot_signal_var.set("")
        except Exception as e:
            # Silently handle errors (user might be typing)
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
                    self.root.after(0, lambda: self._show_error_banner(error_msg))
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
                self.root.after(0, lambda: self._show_error_banner(error_msg))
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
        
        # Professional plot styling
        self.ax.set_facecolor('#fafafa')
        self.ax.set_xlabel("Time (s)", fontsize=11, fontweight='bold', color='#333333')
        self.ax.set_ylabel("Value", fontsize=11, fontweight='bold', color='#333333')
        self.ax.set_title("CAN Signal Values - Real-Time Monitoring", 
                         fontsize=13, fontweight='bold', pad=15, color='#1a1a1a')
        
        # Professional grid styling
        self.ax.grid(True, alpha=0.4, linestyle='--', linewidth=0.5, color='#cccccc')
        
        # Professional spine styling
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['left'].set_color('#cccccc')
        self.ax.spines['bottom'].set_color('#cccccc')
        self.ax.spines['left'].set_linewidth(1.2)
        self.ax.spines['bottom'].set_linewidth(1.2)
        
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
        
        # Plot each signal with professional styling
        legend_handles = []
        legend_labels = []
        
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
                    from can_ids import get_can_id_name, get_can_id_hex
                    can_id_name = get_can_id_name(can_id)
                    can_id_hex = get_can_id_hex(can_id)
                    
                    # Get unit from decoder
                    unit = ""
                    for sig_def_list in self.decoder.signal_definitions.get(can_id, []):
                        if sig_def_list.name == signal_name:
                            unit = sig_def_list.unit
                            break
                    
                    # Create professional label format: "Signal Name | CAN ID (0xXXX) | Unit"
                    # Make it clear that temperature and internal_voltage are separate signals
                    if unit:
                        # Use clearer formatting to distinguish signals from same CAN ID
                        if signal_name == 'temperature':
                            label = f"Temperature | {can_id_hex} | {unit}"
                        elif signal_name == 'internal_voltage':
                            label = f"Internal Voltage | {can_id_hex} | {unit}"
                        elif signal_name == 'analog_voltage_in1':
                            label = f"Analog Voltage In1 | {can_id_hex} | {unit}"
                        else:
                            label = f"{signal_name.replace('_', ' ').title()} | {can_id_hex} | {unit}"
                    else:
                        label = f"{signal_name.replace('_', ' ').title()} | {can_id_hex}"
                    
                    # Get current value for legend (most recent)
                    current_value = values[-1] if values else None
                    
                    # Format current value with appropriate precision
                    if current_value is not None:
                        if unit == '°C':
                            value_str = f"{current_value:.2f}°C"
                        elif unit == 'V':
                            value_str = f"{current_value:.3f}V"
                        else:
                            value_str = f"{current_value:.2f}{unit}" if unit else f"{current_value:.2f}"
                        
                        # Add current value to label with unit
                        label = f"{label} | Now: {value_str}"
                    
                    # Use professional line styling
                    line, = self.ax.plot(times, values, color=color, label=label, 
                                        linewidth=2.5, alpha=0.85, marker='o', 
                                        markersize=4, markevery=max(1, len(values)//20),
                                        antialiased=True)
                    
                    legend_handles.append(line)
                    legend_labels.append(label)
        
        # Create professional legend
        if legend_handles:
            legend = self.ax.legend(handles=legend_handles, labels=legend_labels,
                                  loc='upper left', fontsize=9.5,
                                  framealpha=0.95, fancybox=True, shadow=True,
                                  frameon=True, edgecolor='#333333', 
                                  facecolor='white', borderpad=0.8,
                                  labelspacing=0.7, columnspacing=1.2,
                                  handlelength=2.5, handletextpad=0.8)
            
            # Style legend text
            for text in legend.get_texts():
                text.set_fontweight('normal')
                text.set_fontfamily('monospace')
            
            # Add subtle border
            legend.get_frame().set_linewidth(1.2)
            legend.get_frame().set_linestyle('-')
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
