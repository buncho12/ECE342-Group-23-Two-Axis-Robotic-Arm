from nicegui import ui
import serial
import serial.tools.list_ports
import time
import math

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

ui.label('Select a serial port, connect, and choose a drawing function.')

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
        ser = serial.Serial(port_select.value, BAUD, timeout=0.2)
        time.sleep(2)

        ser.reset_input_buffer()
        ser.reset_output_buffer()

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
# G-code generators
# ------------------------
def line_to_gcode(x1: float, y1: float, x2: float, y2: float, feed: float = 800, segment_len: float = 30.0):
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


def square_to_gcode(x: float, y: float, side: float, feed: float = 800, segment_len: float = 30.0):
    if side <= 0:
        return []

    points = [
        (x, y),
        (x + side, y),
        (x + side, y + side),
        (x, y + side),
        (x, y),
    ]

    gcode = [
        "G21",
        "G90",
        f"G0 X{x:.2f} Y{y:.2f}",
    ]

    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]

        dx = x2 - x1
        dy = y2 - y1
        dist = math.hypot(dx, dy)

        if dist == 0:
            gcode.append(f"G1 X{x2:.2f} Y{y2:.2f} F{int(feed)}")
        else:
            n = max(1, math.ceil(dist / segment_len))
            for j in range(1, n + 1):
                t = j / n
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

            while True:
                resp = ser.readline().decode("utf-8", errors="ignore").strip()

                if not resp:
                    continue

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


# ------------------------
# GUI: Draw Line
# ------------------------
ui.separator()
ui.label('Draw Line').classes('text-lg font-semibold')

with ui.row().classes('gap-4 items-center'):
    line_x1 = ui.number(label='Start X', value=10, format='%.2f').classes('w-32')
    line_y1 = ui.number(label='Start Y', value=30, format='%.2f').classes('w-32')
    line_x2 = ui.number(label='End X', value=50, format='%.2f').classes('w-32')
    line_y2 = ui.number(label='End Y', value=30, format='%.2f').classes('w-32')


def draw_line():
    try:
        x1 = float(line_x1.value if line_x1.value is not None else 0)
        y1 = float(line_y1.value if line_y1.value is not None else 0)
        x2 = float(line_x2.value if line_x2.value is not None else 0)
        y2 = float(line_y2.value if line_y2.value is not None else 0)
        feed = float(feed_input.value if feed_input.value is not None else 800)

        lines = line_to_gcode(x1, y1, x2, y2, feed=feed)
        print(f'SUCCESS: Line G-code generated: ({x1}, {y1}) -> ({x2}, {y2})')
        send_gcode_lines(lines)

    except Exception as e:
        ui.notify('Invalid line input', color='red')
        print('FAIL: Invalid line input:', e)


ui.button('Draw Line', on_click=draw_line).props('color=secondary')


# ------------------------
# GUI: Draw Square
# ------------------------
ui.separator()
ui.label('Draw Square').classes('text-lg font-semibold')

with ui.row().classes('gap-4 items-center'):
    square_x = ui.number(label='Start X', value=10, format='%.2f').classes('w-32')
    square_y = ui.number(label='Start Y', value=30, format='%.2f').classes('w-32')
    square_side = ui.number(label='Side Length', value=20, format='%.2f').classes('w-32')


def draw_square():
    try:
        x = float(square_x.value if square_x.value is not None else 0)
        y = float(square_y.value if square_y.value is not None else 0)
        side = float(square_side.value if square_side.value is not None else 0)
        feed = float(feed_input.value if feed_input.value is not None else 800)

        if side <= 0:
            ui.notify('Side length must be > 0', color='red')
            print('FAIL: Invalid square side length')
            return

        lines = square_to_gcode(x, y, side, feed=feed)
        print(f'SUCCESS: Square G-code generated: start=({x}, {y}), side={side}')
        send_gcode_lines(lines)

    except Exception as e:
        ui.notify('Invalid square input', color='red')
        print('FAIL: Invalid square input:', e)


ui.button('Draw Square', on_click=draw_square).props('color=accent')

ui.run()