from nicegui import ui
import serial
import serial.tools.list_ports
import time
import math

BAUD = 115200
ser = None


# ------------------------
# SCARA Geometry
# ------------------------


L1 = 19.0
L2 = 16.0

STEPS_PER_REV = 200
MICROSTEP = 16

STEPS_PER_DEG = (STEPS_PER_REV * MICROSTEP) / 360.0

prev_theta1 = 0.0
prev_theta2 = 0.0

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


def connect():
    global ser

    if not port_select.value:
        ui.notify('Select a port first', color='red')
        return

    try:
        ser = serial.Serial(port_select.value, BAUD, timeout=0.5)

        time.sleep(2)

        ser.reset_input_buffer()
        ser.reset_output_buffer()

        status.text = 'Connected'
        status.props('color=green')

        ui.notify(f'Connected to {port_select.value}', color='green')

    except Exception as e:
        ui.notify('Connection failed', color='red')
        print(e)


def disconnect():
    global ser

    if ser:
        ser.close()

    ser = None

    status.text = 'Disconnected'
    status.props('color=red')

    ui.notify('Disconnected')


with ui.row().classes('gap-2'):
    ui.button('Refresh', on_click=refresh)
    ui.button('Connect', on_click=connect).props('color=primary')
    ui.button('Disconnect', on_click=disconnect).props('color=negative')


# ------------------------
# SCARA Inverse Kinematics
# ------------------------

def scara_ik(x, y):

    r2 = x*x + y*y

    cos_t2 = (r2 - L1*L1 - L2*L2) / (2 * L1 * L2)
    cos_t2 = max(-1, min(1, cos_t2))

    theta2 = math.acos(cos_t2)

    k1 = L1 + L2 * math.cos(theta2)
    k2 = L2 * math.sin(theta2)

    theta1 = math.atan2(y, x) - math.atan2(k2, k1)

    return math.degrees(theta1), math.degrees(theta2)


# ------------------------
# Angle → Motor Steps
# ------------------------

def angles_to_steps(theta1, theta2):

    global prev_theta1
    global prev_theta2

    d1 = theta1 - prev_theta1
    d2 = theta2 - prev_theta2

    steps1 = int(d1 * STEPS_PER_DEG)
    steps2 = int(d2 * STEPS_PER_DEG)

    prev_theta1 = theta1
    prev_theta2 = theta2

    return steps1, steps2


# ------------------------
# Send Motor Command
# ------------------------

def send_motor_steps(s1, s2, delay):

    global ser

    if not ser:
        ui.notify('Not connected to Arduino', color='red')
        return

    cmd = f"M {s1} {s2} {int(delay)}\n"

    ser.write(cmd.encode())

    print(">>", cmd.strip())

    while True:

        resp = ser.readline().decode(errors="ignore").strip()

        if resp:

            print("<<", resp)

            if resp == "ok_motors":
                time.sleep(0.01);
                break
            if resp == "error":
                ui.notify("Arduino reported error", color="red")
                break

# ------------------------
# Draw Line
# ------------------------

ui.separator()
ui.label('Draw Line').classes('text-lg font-semibold')

with ui.row().classes('gap-4 items-center'):
    line_x1 = ui.number(label='Start X', value=-35, format='%.2f').classes('w-32')
    line_y1 = ui.number(label='Start Y', value=0, format='%.2f').classes('w-32')
    line_x2 = ui.number(label='End X', value=20, format='%.2f').classes('w-32')
    line_y2 = ui.number(label='End Y', value=20, format='%.2f').classes('w-32')


def draw_line():

    try:

        x1 = float(line_x1.value)
        y1 = float(line_y1.value)

        x2 = float(line_x2.value)
        y2 = float(line_y2.value)

        feed = float(feed_input.value)

        dx = x2 - x1
        dy = y2 - y1

        dist = math.hypot(dx, dy)

        segments = max(10, int(dist * 5))

        for i in range(segments + 1):

            t = i / segments

            x = x1 + dx * t
            y = y1 + dy * t

            theta1, theta2 = scara_ik(x, y)

            s1, s2 = angles_to_steps(theta1, theta2)

            if s1 != 0 or s2 != 0:
                send_motor_steps(s1, s2, feed)

        ui.notify("Line drawn", color="green")

    except Exception as e:
        print(e)
        ui.notify("Invalid input", color="red")


ui.button('Draw Line', on_click=draw_line).props('color=secondary')


# ------------------------
# Draw Square
# ------------------------

ui.separator()
ui.label('Draw Square').classes('text-lg font-semibold')

with ui.row().classes('gap-4 items-center'):
    square_x = ui.number(label='Start X', value=-5, format='%.2f').classes('w-32')
    square_y = ui.number(label='Start Y', value=5, format='%.2f').classes('w-32')
    square_side = ui.number(label='Side Length', value=5, format='%.2f').classes('w-32')


def draw_square():

    try:

        start_x = float(square_x.value)
        start_y = float(square_y.value)
        side = float(square_side.value)
        feed = float(feed_input.value)

        points = [
            (start_x, start_y),
            (start_x + side, start_y),
            (start_x + side, start_y + side),
            (start_x, start_y + side),
            (start_x, start_y)
        ]

        for i in range(len(points) - 1):

            x1, y1 = points[i]
            x2, y2 = points[i + 1]

            dx = x2 - x1
            dy = y2 - y1

            dist = math.hypot(dx, dy)

            # higher resolution
            segments = max(40, int(dist * 20))

            for j in range(segments + 1):

                t = j / segments

                px = x1 + dx * t
                py = y1 + dy * t

                theta1, theta2 = scara_ik(px, py)

                s1, s2 = angles_to_steps(theta1, theta2)

                if s1 != 0 or s2 != 0:
                    send_motor_steps(s1, s2, feed)

        ui.notify("Square drawn", color="green")

    except Exception as e:
        print(e)
        ui.notify("Invalid square input", color="red")
ui.button('Draw Square', on_click=draw_square).props('color=accent')


ui.run()