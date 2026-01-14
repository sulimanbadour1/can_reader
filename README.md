# can_reader

DIY CAN Bus Reader and Analyzer

A free, powerful Python tool for CAN bus analysis with custom plots, filtering, and exporting capabilities. Built with `python-can` and `matplotlib` for publication-quality visualizations.

## Features

- **GUI Application**: Tkinter-based GUI for easy CAN bus analysis
- **Signal Decoding**: Decode CAN messages into physical values (voltage, temperature, current, etc.)
- **Real-Time Plotting**: Live plots of decoded signals with customizable decoders
- **CAN Bus Reading**: Support for multiple interfaces (socketcan, slcan, usb2can, etc.)
- **Custom Filtering**: Filter by CAN ID, data length, or custom data patterns
- **Publication-Quality Plots**: Multiple visualization types using matplotlib
- **Data Export**: Export to CSV, JSON, or candump format
- **Flexible Analysis**: Analyze message frequency, intervals, byte values, and more

## Installation

### Quick Install (Automated)

**Linux/Mac:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows:**
```batch
setup.bat
```

### Manual Install

```bash
# 1. Create virtual environment
python3 -m venv venv

# 2. Activate virtual environment
# Linux/Mac:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Verify installation
python -c "import can, matplotlib, tkinter; print('✓ All libraries installed!')"
```

### System Dependencies

**Linux (socketcan):**
```bash
sudo apt-get install can-utils  # Ubuntu/Debian
# or
sudo yum install can-utils     # CentOS/RHEL

# Setup CAN interface
sudo ip link set can0 up type can bitrate 500000
```

**macOS:**
```bash
# Tkinter should be included, if not:
brew install python-tk
```

**Windows:**
- Tkinter usually included with Python
- Install drivers for your USB CAN adapter
- Use `slcan` or `usb2can` interface type
- Default settings: Interface=`slcan`, Channel=`COM3`

### Troubleshooting Installation

**"python3: command not found"**
- Use `python` instead of `python3`

**"No module named 'tkinter'"**
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk
# macOS
brew install python-tk
```

**Virtual environment activation:**
```bash
# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate

# Windows PowerShell (if blocked)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Quick Start

### GUI Application (Recommended)

```bash
python can_gui.py
```

**Basic Workflow:**
1. **Connect**: Select interface (slcan, socketcan, USB, etc.), channel (COM3, can0, etc.), bitrate → Click "Connect"
2. **Default Decoders**: Three default decoders are automatically loaded:
   - **CAN ID 0x259**: `analog_voltage_in1` at bytes 0-1 (uint16_le)
   - **CAN ID 0x25E**: `internal_voltage` at bytes 2-3 (uint16_le)
   - **CAN ID 0x25E**: `temperature` at bytes 4-5 (uint16_le)
3. **Add More Decoders** (optional): Configure additional signal decoders:
   - CAN ID (hex, e.g., `0x123`)
   - Signal name (e.g., `voltage`, `temperature`)
   - Byte index, scale, offset, data type
   - Use presets: "Voltage (16-bit)" or "Temp (16-bit)"
   - Or click "Load Predefined" for other CAN IDs
4. **Capture**: Click "Start Capture" to read messages
5. **Plot**: Select CAN ID and signal → Click "Add to Plot"
6. **Export**: Click "Export CSV" to save data

### Command Line Usage

**Basic Reading:**
```bash
# Read for 10 seconds
python can_reader.py --interface socketcan --channel can0 --duration 10

# Read specific number of messages
python can_reader.py --interface socketcan --channel can0 --count 1000
```

**Filtering:**
```bash
python can_reader.py --interface socketcan --channel can0 --duration 5 --can-ids 0x123 0x456
```

**Plotting:**
```bash
# Message frequency
python can_reader.py --interface socketcan --channel can0 --duration 10 --plot frequency

# CAN ID distribution
python can_reader.py --interface socketcan --channel can0 --duration 10 --plot distribution

# Specific byte over time
python can_reader.py --interface socketcan --channel can0 --duration 10 --plot byte --can-id 0x123 --byte-index 0

# Inter-message interval
python can_reader.py --interface socketcan --channel can0 --duration 10 --plot interval --can-id 0x123

# Heatmap
python can_reader.py --interface socketcan --channel can0 --duration 10 --plot heatmap
```

**Exporting:**
```bash
# CSV
python can_reader.py --interface socketcan --channel can0 --duration 10 --export csv --output data.csv

# JSON
python can_reader.py --interface socketcan --channel can0 --duration 10 --export json --output data.json

# candump format
python can_reader.py --interface socketcan --channel can0 --duration 10 --export candump --output data.log
```

**Save Plots:**
```bash
python can_reader.py --interface socketcan --channel can0 --duration 10 --plot frequency --save-plot --output plot.png --dpi 300
```

## GUI Usage Guide

### Default Decoders

The GUI automatically loads three default signal decoders on startup:

| CAN ID | Signal             | Bytes (index) | Data Type | Example Raw Value |
| ------ | ------------------ | ------------: | --------- | ----------------- |
| 0x259  | analog_voltage_in1 |         b0–b1 | uint16_le | 55043 (0xD703)    |
| 0x25E  | internal_voltage   |         b2–b3 | uint16_le | 60421 (0xEC05)    |
| 0x25E  | temperature        |         b4–b5 | uint16_le | 47366 (0xB906)    |

These decoders are configured to read raw uint16 little-endian values. You can adjust the scale and offset in the decoder panel if you need to convert to physical units (volts, degrees Celsius, etc.).

**Byte Interpretation:**
- Little-endian means: `raw = b0 + (b1 << 8)`
- Example: `03 D7` → `0x03 + (0xD7 << 8)` = `0xD703` = 55043

### Signal Decoder Configuration

Configure how to decode CAN messages into physical values:

**Common Configurations:**

**Voltage (16-bit, Little Endian):**
- CAN ID: `0x123` (your CAN ID)
- Signal Name: `voltage`
- Byte Index: `0`
- Scale: `0.1` (if 0.1V per count)
- Offset: `0`
- Unit: `V`
- Data Type: `uint16_le`

**Temperature (16-bit, Signed):**
- CAN ID: `0x123`
- Signal Name: `temperature`
- Byte Index: `2`
- Scale: `0.1` (if 0.1°C per count)
- Offset: `-40` (if offset is -40°C)
- Unit: `°C`
- Data Type: `int16_le`

**Current (16-bit, Signed):**
- CAN ID: `0x123`
- Signal Name: `current`
- Byte Index: `4`
- Scale: `0.01` (if 0.01A per count)
- Offset: `0`
- Unit: `A`
- Data Type: `int16_le`

### Data Types

- **uint8**: Unsigned 8-bit integer (0-255)
- **uint16_le**: Unsigned 16-bit, little endian (0-65535)
- **uint16_be**: Unsigned 16-bit, big endian (0-65535)
- **int16_le**: Signed 16-bit, little endian (-32768 to 32767)
- **int16_be**: Signed 16-bit, big endian (-32768 to 32767)

### Byte Order (Endianness)

- **Little Endian**: Least significant byte first (common on x86/x64)
  - Example: `0x1234` stored as `[0x34, 0x12]`
- **Big Endian**: Most significant byte first (network byte order)
  - Example: `0x1234` stored as `[0x12, 0x34]`

### Example Workflow: Using Default Decoders

1. **Launch GUI**: `python can_gui.py`
   - Default decoders are automatically loaded (analog_voltage_in1, internal_voltage, temperature)

2. **Connect** to CAN bus:
   - Default: Interface=`slcan`, Channel=`COM3` (Windows)
   - Or change to your interface/channel
   - Click "Connect"

3. **Start Capture**: Click "Start Capture" to begin reading messages

4. **Add Signals to Plot**:
   - Select CAN ID `0x259` → Select signal `analog_voltage_in1` → Click "Add to Plot"
   - Select CAN ID `0x25E` → Select signal `internal_voltage` → Click "Add to Plot"
   - Select CAN ID `0x25E` → Select signal `temperature` → Click "Add to Plot"

5. **Monitor** real-time plots showing all three signals

6. **Export** CSV for analysis or reporting

### Example Workflow: Custom Battery Voltage and Temperature

1. **Connect** to CAN bus (e.g., socketcan on can0)

2. **Add Voltage Decoder:**
   - CAN ID: `0x100`
   - Signal: `battery_voltage`
   - Byte Index: `0`
   - Scale: `0.01`
   - Offset: `0`
   - Unit: `V`
   - Data Type: `uint16_le`

3. **Add Temperature Decoder:**
   - CAN ID: `0x100`
   - Signal: `battery_temp`
   - Byte Index: `2`
   - Scale: `0.1`
   - Offset: `-40`
   - Unit: `°C`
   - Data Type: `int16_le`

4. **Start Capture** and watch messages appear

5. **Add to Plot:**
   - Select CAN ID `0x100`
   - Select signal `battery_voltage`
   - Click "Add to Plot"
   - Repeat for `battery_temp`

6. **Monitor** real-time plots showing voltage and temperature over time

7. **Export** CSV for analysis or reporting

## Python API Usage

You can also use the classes programmatically:

```python
from can_reader import CANReader, CANPlotter, CANExporter

# Read CAN messages
reader = CANReader(interface='socketcan', channel='can0')
reader.connect()
reader.read_messages(duration=10)
reader.disconnect()

# Filter messages
filtered = reader.filter_messages(can_ids=[0x123, 0x456])

# Create plots
plotter = CANPlotter()
plotter.plot_message_frequency(filtered)
plotter.show()

# Export data
CANExporter.to_csv(filtered, 'output.csv')
CANExporter.to_json(filtered, 'output.json')
```

## Supported Interfaces

- **socketcan**: Linux SocketCAN (most common on Linux)
- **slcan**: Serial Line CAN (USB-to-CAN adapters)
- **usb2can**: USB2CAN adapters
- **pcan**: Peak CAN interfaces
- **ixxat**: IXXAT CAN interfaces
- **vector**: Vector CAN interfaces
- **virtual**: Virtual interface for testing
- And more (see python-can documentation)

## Plot Types

1. **Frequency Plot**: Shows message count per time window for each CAN ID
2. **Distribution Plot**: Bar chart showing total message count per CAN ID
3. **Byte Plot**: Time series of a specific byte value from a CAN ID
4. **Multi-Byte Plot**: Multiple bytes from a CAN ID overlaid on same plot
5. **Interval Plot**: Inter-message timing intervals for a CAN ID
6. **Heatmap**: 2D heatmap showing message frequency by CAN ID and time

## Common Use Cases

### 1. Quick Capture and View
```bash
python can_reader.py --interface socketcan --channel can0 --duration 10 --plot distribution
```

### 2. Monitor Specific CAN IDs
```bash
python can_reader.py --interface socketcan --channel can0 --duration 30 \
  --can-ids 0x123 0x456 --plot frequency
```

### 3. Analyze a Specific Signal
```bash
python can_reader.py --interface socketcan --channel can0 --duration 60 \
  --can-id 0x123 --plot byte --byte-index 0 --save-plot --output signal.png
```

### 4. Export for Analysis
```bash
python can_reader.py --interface socketcan --channel can0 --duration 30 \
  --export csv --output capture.csv
```

### 5. Publication-Quality Plot
```bash
python can_reader.py --interface socketcan --channel can0 --duration 60 \
  --plot frequency --save-plot --output publication_plot.png --dpi 300
```

## Troubleshooting

### Connection Issues

**"No messages received"**
- Check CAN interface is up: `ip link show can0` (Linux)
- Verify bitrate matches bus: `--bitrate 500000` (or 250000, 125000, etc.)
- Try different interface types if available

**"Permission denied"**
- SocketCAN may need root: `sudo python can_reader.py ...`
- Or add user to dialout group: `sudo usermod -a -G dialout $USER`

**"Interface not found"**
- List available interfaces: `ip link show`
- Check USB devices: `lsusb` (for USB adapters)
- Try `--interface slcan` for USB-to-CAN adapters

### GUI Issues

**No messages appearing:**
- Verify CAN interface is up: `ip link show can0` (Linux)
- Check bitrate matches your CAN bus
- Try different interface types if available

**Decoded values seem wrong:**
- Verify byte index is correct
- Check scale and offset values
- Try different data types (signed vs unsigned)
- Verify byte order (little vs big endian)

**Plot not updating:**
- Ensure "Start Capture" is active
- Verify signal decoder is configured correctly
- Check that messages with that CAN ID are being received

**Connection fails:**
- Check permissions (may need sudo on Linux)
- Verify interface name is correct
- Try virtual interface for testing: `--interface virtual`

## Requirements

- Python 3.7+
- python-can >= 4.3.1
- matplotlib >= 3.7.0
- numpy >= 1.24.0
- pandas >= 2.0.0
- pyserial >= 3.5 (required for slcan interface)

## Tips

- **Start with short durations** to test your setup
- **Use `--plot distribution`** first to see what CAN IDs are active
- **Filter early** with `--can-ids` to reduce data volume
- **Save plots** with `--save-plot` for documentation
- **Export data** for custom analysis in Python/Excel/etc.
- **Use presets** in GUI for quick decoder setup
- **Check raw data** in message display to verify byte positions

## Code Structure

This section explains what each file and major component does.

### File Overview

**`can_reader.py`** - Command-line CAN bus reader and analyzer
- `CANReader` class: Handles CAN bus connection and message reading
- `CANPlotter` class: Creates various types of plots (frequency, distribution, bytes, etc.)
- `CANExporter` class: Exports data to CSV, JSON, or candump format
- Main function: Parses command-line arguments and orchestrates reading/plotting/exporting

**`can_gui.py`** - Graphical user interface application
- `CANAnalyzerGUI` class: Main GUI window with all controls and displays
- Connection panel: Configure CAN interface, channel, and bitrate
- Decoder panel: Set up signal decoders (voltage, temperature, etc.)
- Message display: Shows raw CAN messages with decoded values
- Real-time plot: Live updating matplotlib plot of decoded signals
- Uses threading to read CAN messages without blocking the GUI

**`can_decoder.py`** - Signal decoding engine
- `SignalDefinition` class: Defines how to extract a signal from CAN bytes
- `CANDecoder` class: Decodes CAN messages into physical values
- Helper functions: Pre-built decoders for voltage, temperature, current

**`can_ids.py`** - CAN ID definitions and default decoders
- Predefined CAN IDs: 0x258 (Keep Alive), 0x259 (AIN1-4), 0x25A-0x25E (other inputs)
- `DEFAULT_DECODERS`: Three default signals automatically loaded in GUI
- `EXAMPLE_DECODERS`: Additional decoder configurations for all CAN IDs

**`run_gui.py`** - Simple launcher script for the GUI

**`example_usage.py`** - Example code showing how to use the API programmatically

**`example_setup.py`** - Example showing how to set up all decoders programmatically

**`setup.sh` / `setup.bat`** - Automated installation scripts

### Main Classes Explained

#### CANReader (`can_reader.py`)

**Purpose**: Connects to CAN bus and collects messages

**Key Methods**:
- `__init__()`: Sets up interface, channel, bitrate, and optional filters
- `connect()`: Establishes connection to CAN bus (tries with/without bitrate)
- `disconnect()`: Closes CAN bus connection
- `read_messages()`: Reads messages for specified duration or count
- `filter_messages()`: Filters collected messages by CAN ID, DLC, or custom function

**How it works**:
1. Creates a CAN bus interface using python-can library
2. Reads messages in a loop, storing them with timestamps
3. Messages stored as dictionaries with arbitration_id, data, dlc, etc.

#### CANPlotter (`can_reader.py`)

**Purpose**: Creates publication-quality plots from CAN message data

**Key Methods**:
- `plot_message_frequency()`: Shows how often each CAN ID appears over time
- `plot_can_id_distribution()`: Bar chart of total messages per CAN ID
- `plot_data_bytes()`: Time series of a specific byte value
- `plot_multiple_bytes()`: Multiple bytes overlaid on one plot
- `plot_inter_message_interval()`: Timing between messages for a CAN ID
- `plot_heatmap()`: 2D heatmap of message frequency vs time

**How it works**:
1. Converts message list to pandas DataFrame for easy manipulation
2. Groups data by time windows and CAN IDs
3. Uses matplotlib to create plots with proper labels and legends
4. Supports saving plots at high DPI for publications

#### CANExporter (`can_reader.py`)

**Purpose**: Exports CAN message data to various file formats

**Key Methods**:
- `to_csv()`: Exports to CSV with timestamp, CAN ID, hex data, decoded values
- `to_json()`: Exports to JSON format (includes all message metadata)
- `to_candump_format()`: Exports in candump-compatible format

**How it works**:
1. Formats message data appropriately for each format
2. Handles datetime serialization for JSON
3. Preserves all message information (ID, data, flags, etc.)

#### CANAnalyzerGUI (`can_gui.py`)

**Purpose**: Provides graphical interface for CAN bus analysis

**Key Components**:

**Connection Panel** (`_setup_connection_panel`):
- Dropdown to select CAN interface type
- Entry field for channel/device name
- Bitrate selection
- Connect/Disconnect button
- Status indicator

**Decoder Panel** (`_setup_decoder_panel`):
- Fields to configure signal decoders:
  - CAN ID (hex)
  - Signal name
  - Byte index (where signal starts)
  - Scale factor (multiplier)
  - Offset (additive constant)
  - Unit (V, °C, A, etc.)
  - Data type (uint8, int16_le, etc.)
- Preset buttons for common signals
- List of active decoders

**Plot Controls** (`_setup_plot_controls`):
- Start/Stop capture button
- Clear data button
- Export CSV button
- Max data points setting

**Message Display** (`_setup_message_display`):
- Scrolled text area showing raw CAN messages
- Shows timestamp, CAN ID, data length, hex data
- Displays decoded values next to raw data
- Filter by CAN ID

**Plot Area** (`_setup_plot_area`):
- Embedded matplotlib figure
- Real-time updating plot
- Dropdowns to select CAN ID and signal
- Add/Remove signals from plot

**Key Methods**:
- `_connect()` / `_disconnect()`: Manage CAN bus connection
- `_add_signal_decoder()`: Configure how to decode a signal
- `_start_capture()` / `_stop_capture()`: Control message reading
- `_read_messages_thread()`: Background thread reading CAN messages
- `_process_messages_thread()`: Background thread decoding messages
- `_process_message()`: Decode a single message and store values
- `_update_plot()`: Refresh plot with latest decoded data
- `_export_csv()`: Save decoded data to CSV file

**How it works**:
1. GUI uses Tkinter for the interface
2. Matplotlib embedded for real-time plotting
3. Three threads: GUI main thread, CAN reading thread, message processing thread
4. Queue-based communication between threads
5. Animation updates plot every 100ms
6. Decoded data stored in deques (limited size to prevent memory issues)

#### CANDecoder (`can_decoder.py`)

**Purpose**: Converts raw CAN bytes into physical values

**SignalDefinition Class**:
- Stores signal configuration: name, bit position, length, scale, offset, signed/unsigned, endianness, unit
- Used to define how to extract a value from CAN message bytes

**CANDecoder Class**:
- `add_signal_definition()`: Register a decoder for a CAN ID
- `add_custom_decoder()`: Register a custom decoder function
- `decode_message()`: Decode a CAN message into dictionary of signal names → values
- `_extract_signal()`: Extract bits from CAN data and apply scale/offset
- `get_available_signals()`: List all signals defined for a CAN ID

**How it works**:
1. For each CAN ID, stores list of SignalDefinition objects
2. When decoding a message:
   - Checks if custom decoder exists (takes priority)
   - Otherwise uses signal definitions
   - Extracts bits from data bytes based on start_bit and length
   - Handles little/big endian byte order
   - Applies signed/unsigned conversion
   - Multiplies by scale and adds offset
   - Returns physical value

**Helper Functions**:
- `decode_voltage_8bit()`: Quick decoder for 8-bit voltage
- `decode_voltage_16bit()`: Quick decoder for 16-bit voltage
- `decode_temperature_8bit()`: Quick decoder for 8-bit temperature
- `decode_temperature_16bit()`: Quick decoder for 16-bit temperature
- `decode_current_16bit()`: Quick decoder for 16-bit current

### Data Flow

**GUI Application Flow**:
```
User clicks "Connect"
  → CANReader.connect() creates CAN bus interface
  → User configures signal decoders
  → User clicks "Start Capture"
  → _read_messages_thread() reads messages → message_queue
  → _process_messages_thread() reads from queue
  → CANDecoder.decode_message() converts bytes to values
  → Values stored in decoded_data dictionary
  → _update_plot() animation reads decoded_data
  → Matplotlib updates plot display
```

**Command-Line Flow**:
```
can_reader.py --interface socketcan --channel can0 --duration 10
  → CANReader.read_messages() collects messages
  → Messages stored in reader.messages list
  → CANPlotter creates plot from messages
  → CANExporter saves data if --export specified
```

### Threading Architecture (GUI)

The GUI uses three threads to keep the interface responsive:

1. **Main Thread**: Runs Tkinter GUI event loop, handles user interactions
2. **CAN Reading Thread** (`_read_messages_thread`): Continuously reads CAN messages, puts them in queue
3. **Message Processing Thread** (`_process_messages_thread`): Reads from queue, decodes messages, updates data structures

**Why threading?**
- CAN message reading is blocking (waits for messages)
- GUI would freeze if reading happened in main thread
- Queue allows safe communication between threads
- Matplotlib animation runs in main thread, reads from shared data structures

### Key Data Structures

**`decoded_data`** (GUI):
```python
{
  can_id: {
    signal_name: deque([{timestamp, value}, ...])
  }
}
```
- Stores time series of decoded values
- Uses deque for efficient append/popleft operations
- Limited size to prevent memory issues

**`messages`** (CLI):
```python
[
  {
    'timestamp': datetime,
    'arbitration_id': int,
    'data': bytes,
    'dlc': int,
    'data_hex': str,
    'data_dec': list
  },
  ...
]
```
- List of all collected messages
- Includes both raw and formatted data

**`plot_signals`** (GUI):
```python
{
  "0x123:voltage": {
    'can_id': 0x123,
    'signal': 'voltage',
    'color': matplotlib_color
  }
}
```
- Tracks which signals are currently plotted
- Used to determine what to draw in plot

