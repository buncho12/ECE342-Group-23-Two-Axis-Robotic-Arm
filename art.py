from nicegui import ui
import serial
import serial.tools.list_ports
import time
import math

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
feed_input = ui.slider(min=200, max=2000, step=100, value=800).props('label-always')
ui.label().bind_text_from(feed_input, 'value', lambda v: f'Feed Speed: {int(v)}')
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

ui.separator()
ui.label('Line Drawing Mode').classes('text-lg font-semibold')

with ui.row().classes('gap-4 items-center'):
    start_x_input = ui.number(label='Start X', value=10, format='%.2f').classes('w-32')
    start_y_input = ui.number(label='Start Y', value=10, format='%.2f').classes('w-32')
    end_x_input = ui.number(label='End X', value=50, format='%.2f').classes('w-32')
    end_y_input = ui.number(label='End Y', value=50, format='%.2f').classes('w-32')

# ------------------------
# Text -> G-code (mm, absolute)
# ------------------------
def text_to_gcode(text: str, start_x=10, start_y=10, segment_len=2.0, feed=800):
    gcode = [
        "G21",  # mm
        "G90",  # absolute
    ]

    x_offset = start_x
    current_x = None
    current_y = None

    for ch in text.upper():
        if ch == " ":
            x_offset += LETTER_SPACING
            current_x = None
            current_y = None
            continue

        if ch not in LETTERS:
            print(f"SKIP: Unsupported letter {ch}")
            continue

        for cmd in LETTERS[ch]:
            if cmd[0] == "G0":
                _, x, y = cmd
                tx = x_offset + x
                ty = start_y + y

                gcode.append(f"G0 X{tx:.2f} Y{ty:.2f}")
                current_x = tx
                current_y = ty

            else:  # G1
                _, x, y, f = cmd
                tx = x_offset + x
                ty = start_y + y

                # 如果前面没有当前位置，就直接补一条 G1
                if current_x is None or current_y is None:
                    gcode.append(f"G1 X{tx:.2f} Y{ty:.2f} F{int(feed)}")
                    current_x = tx
                    current_y = ty
                    continue

                dx = tx - current_x
                dy = ty - current_y
                dist = math.hypot(dx, dy)

                if dist == 0:
                    gcode.append(f"G1 X{tx:.2f} Y{ty:.2f} F{int(feed)}")
                else:
                    n = max(1, math.ceil(dist / segment_len))
                    for i in range(1, n + 1):
                        t = i / n
                        xi = current_x + dx * t
                        yi = current_y + dy * t
                        gcode.append(f"G1 X{xi:.2f} Y{yi:.2f} F{int(feed)}")

                current_x = tx
                current_y = ty

        x_offset += LETTER_SPACING
        current_x = None
        current_y = None

    gcode.append("M2")
    return gcode


def line_to_gcode(x1: float, y1: float, x2: float, y2: float, feed: float = 800, segment_len: float = 2.0):
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)

    gcode = [
        "G21",
        "G90",
        f"G0 X{x1:.2f} Y{y1:.2f}",
    ]

    if dist == 0:
        gcode.append(f"G1 X{x2:.2f} Y{y2:.2f} F{int(feed)}")
    else:
        n = max(1, math.ceil(dist / segment_len))
        for i in range(1, n + 1):
            t = i / n
            xi = x1 + dx * t
            yi = y1 + dy * t
            gcode.append(f"G1 X{xi:.2f} Y{yi:.2f} F{int(feed)}")

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

                if resp == "ok_gcode" or resp == "ok_motors":
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
    feed = float(feed_input.value if feed_input.value is not None else 800)
    lines = text_to_gcode(text, feed=feed)
    print('SUCCESS: Generated G-code for:', text)
    send_gcode_lines(lines)

def send_line_as_gcode():
    try:
        x1 = float(start_x_input.value if start_x_input.value is not None else 0)
        y1 = float(start_y_input.value if start_y_input.value is not None else 0)
        x2 = float(end_x_input.value if end_x_input.value is not None else 0)
        y2 = float(end_y_input.value if end_y_input.value is not None else 0)
        feed = float(feed_input.value if feed_input.value is not None else 800)

        lines = line_to_gcode(x1, y1, x2, y2, feed)
        print(f'SUCCESS: Generated line G-code: ({x1}, {y1}) -> ({x2}, {y2}), F={feed}')
        send_gcode_lines(lines)

    except Exception as e:
        ui.notify('Invalid line input', color='red')
        print('FAIL: Invalid line input:', e)

with ui.row().classes('gap-2'):
    ui.button('Send Text as G-code', on_click=send_text_as_gcode).props('color=secondary')
    ui.button('Send Line', on_click=send_line_as_gcode).props('color=accent')

ui.run()
