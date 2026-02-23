from nicegui import ui
import serial
import serial.tools.list_ports
import time

from letters import LETTERS, LETTER_SPACING

BAUD = 115200
ser = None


# ------------------------
# Serial utilities
# ------------------------
def list_ports():
    return [p.device for p in serial.tools.list_ports.comports()]


# ------------------------
# Serial Controls
# ------------------------
ui.label('SCARA Block 1 (NiceGUI)').classes('text-2xl font-bold')
ui.label('Select a serial port, connect, and enter text to draw.')

with ui.row().classes('items-center gap-4'):
    port_select = ui.select(options=list_ports(), label='Serial Port').classes('w-96')
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
        ser = serial.Serial(port_select.value, BAUD, timeout=0.01)
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


# ------------------------
# Text Input (ER-7)
# ------------------------
ui.separator()
ui.label('Text Writing Mode').classes('text-lg font-semibold')

typed_text = ui.textarea(
    label='Enter text to draw',
    placeholder='Example: ABC',
).classes('w-full')


# ------------------------
# Text -> G-code (mm, absolute)
# ------------------------
def text_to_gcode(text: str, start_x=10, start_y=10):
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
                gcode.append(f"G1 X{x_offset + x:.2f} Y{start_y + y:.2f} F{f}")

        x_offset += LETTER_SPACING

    gcode.append("M2")
    return gcode


# ------------------------
# Send G-code to MC
# ------------------------
def send_gcode_lines(lines):
    global ser
    if not ser:
        ui.notify('Not connected to Arduino', color='red')
        return

    print('=== START SEND ===')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            ser.write((line + "\n").encode("ascii"))
            print(">>", line)

            # TRUE HANDSHAKE
            while True:
                resp = ser.readline().decode("utf-8", errors="ignore").strip()

                if not resp:
                    continue  # wait again

                print("<<", resp)

                if resp == "ok":
                    break
                elif resp == "error":
                    ui.notify("Arduino reported error", color="red")
                    return

        except Exception as e:
            print("FAIL:", e)
            return

    print('=== DONE ===')
    ui.notify('G-code sent', color='green')


def send_text_as_gcode():
    text = typed_text.value or ""
    if not text.strip():
        ui.notify('No text entered', color='red')
        print('FAIL: No text')
        return

    lines = text_to_gcode(text)
    print('SUCCESS: Generated G-code for:', text)
    send_gcode_lines(lines)


ui.button('Send Text as G-code', on_click=send_text_as_gcode).props('color=secondary')

ui.run()
