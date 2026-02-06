from nicegui import ui
import serial
import serial.tools.list_ports
import time

from letters import LETTERS, LETTER_SPACING

BAUD = 115200
ser = None

def list_ports():
    return [p.device for p in serial.tools.list_ports.comports()]


# Serial Controls
ui.label('SCARA Block 1 (using NiceGUI)').classes('text-2xl font-bold')
ui.label('Select a serial port, connect.')

with ui.row().classes('items-center gap-4'):
    port_select = ui.select(options=list_ports(), label='Serial Ports').classes('w-96')
    status = ui.badge('Disconnected').props('color=red')


def refresh():
    ports = list_ports()
    port_select.options = ports
    if ports and not port_select.value:
        port_select.value = ports[0]
    ui.notify(f'Found {len(ports)} port(s)')
    print('SUCCESS: Ports refreshed:', ports)


def connect():
    global ser
    if not port_select.value:
        ui.notify('Select a port first', color='red')
        print('FAIL: No port selected')
        return
    try:
        ser = serial.Serial(port_select.value, BAUD, timeout=.1)
        time.sleep(2)  # Arduino resets when serial opens
        status.text = 'Connected'
        status.props('color=green')
        ui.notify(f'Connected to {port_select.value}', color='green')
        print(f'SUCCESS: Connected to {port_select.value} @ {BAUD}')
    except Exception as e:
        ui.notify('Connection failed', color='red')
        print('FAIL: Connection error:', e)


def disconnect():
    global ser
    try:
        if ser:
            ser.close()
        ser = None
        status.text = 'Disconnected'
        status.props('color=red')
        ui.notify('Disconnected')
        print('SUCCESS: Disconnected')
    except Exception as e:
        print('FAIL: Disconnect error:', e)


with ui.row().classes('gap-2'):
    ui.button('Refresh', on_click=refresh)
    ui.button('Connect', on_click=connect).props('color=primary')
    ui.button('Disconnect', on_click=disconnect).props('color=negative')

# Drawing speed (ER-1)
speed_scale = ui.slider(min=0.2, max=2.0, step=0.1, value=1.0)\
    .props('label label-always')\
    .classes('w-full')
ui.label().bind_text_from(speed_scale, 'value', lambda v: f'Speed scale: {v:.1f}x')


# Text Input (ER-7)
ui.separator()
ui.label('Text Writing Mode').classes('text-lg font-semibold')

typed_text = ui.textarea(
    label='Enter text to draw',
    placeholder='Example: ABC',
).classes('w-full')

# Text -> G-code (mm, absolute)
def text_to_gcode(text: str, start_x=10, start_y=10, scale=1.0):
    gcode = [
        "G21",  # mm
        "G90",  # absolute
    ]

    x_offset = start_x

    for ch in text.upper():
        if ch == " ":
            x_offset += LETTER_SPACING
            continue

        if ch not in LETTERS:
            print(f"SKIP: Unsupported letter {ch}")
            continue

        for cmd in LETTERS[ch]:
            if cmd[0] == "G0":
                _, x, y = cmd
                gcode.append(f"G0 X{x_offset + x:.2f} Y{start_y + y:.2f}")
            else:  # G1
                _, x, y, f = cmd
                f2 = max(1, int(f * scale))
                gcode.append(f"G1 X{x_offset + x:.2f} Y{start_y + y:.2f} F{f2}")

        x_offset += LETTER_SPACING

    gcode.append("M2")
    return gcode


# Send G-code to MC
def send_gcode_lines(lines):
    global ser
    if not ser:
        ui.notify('Not connected to Arduino', color='red')
        print('FAIL: Not connected')
        return

    print('=== START SEND ===')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            ser.write((line + "\n").encode("ascii", errors="ignore"))
            print(">>", line)

            # optional handshake (MC should print "ok")
            resp = ser.readline().decode("utf-8", errors="ignore").strip()
            if resp:
                print("<<", resp)

        except Exception as e:
            print("FAIL: Send error:", e)
            ui.notify('Send failed (see terminal)', color='red')
            return

    print('=== DONE ===')
    ui.notify('G-code sent', color='green')


def send_text_as_gcode():
    text = typed_text.value or ""
    if not text.strip():
        ui.notify('No text entered', color='red')
        print('FAIL: No text')
        return

    lines = text_to_gcode(text, scale=float(speed_scale.value))
    print('SUCCESS: Generated G-code for:', text)
    send_gcode_lines(lines)


ui.button('Send Text as G-code', on_click=send_text_as_gcode).props('color=secondary')

ui.run()
