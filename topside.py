import pygame
import socket
import time
import threading

# config
raspi_ip = "192.168.1.50"  # ip
port = 8080
DEAD_ZONE = 0.1

# init
pygame.init()
if pygame.joystick.get_count() == 0:
    print("No joystick found")
    exit()

joystick = pygame.joystick.Joystick(0)
joystick.init()
print("Joystick started")


UP_BUTTON = 0   
DOWN_BUTTON = 3 

claw_pos = 0
step_delay = 0.005
claw_lock = threading.Lock()

def apply_dead_zone(value, threshold=DEAD_ZONE):
    return 0 if abs(value) < threshold else value

def get_motor_commands():
    pygame.event.pump()

    forward_back = -apply_dead_zone(joystick.get_axis(1))  # forward/backward
    baseSpeed = round(forward_back * 255)

    turn = apply_dead_zone(joystick.get_axis(3))  # turning
    turnSpeed = round(turn * 255)

    leftMotor = max(min(baseSpeed + turnSpeed, 255), -255)
    rightMotor = max(min(baseSpeed - turnSpeed, 255), -255)

    up_thrust = joystick.get_axis(5)
    down_thrust = joystick.get_axis(2)
    upMotor = round(((up_thrust + 1) / 2) * 255)
    downMotor = round(((down_thrust + 1) / 2) * 255)

    return leftMotor, rightMotor, upMotor, downMotor

def connect_to_raspi():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((raspi_ip, port))
        print(f"Connected to Raspberry Pi at {raspi_ip}:{port}")
        return sock
    except Exception as e:
        print("Connection error:", e)
        return None


def control_claw():
    global claw_pos
    while True:
        pygame.event.pump()
        if joystick.get_button(UP_BUTTON):
            with claw_lock:
                if claw_pos < 180:  # maximum claw angle
                    claw_pos += 1  # open increment
        elif joystick.get_button(DOWN_BUTTON):
            with claw_lock:
                if claw_pos > 0:  # minimum claw angle
                    claw_pos -= 1  # close increment
        time.sleep(step_delay)

claw_thread = threading.Thread(target=control_claw, daemon=True)
claw_thread.start()

# main command sending
client_socket = None

while True:
    if client_socket is None:
        print("Attempting to connect to Raspberry Pi...")
        client_socket = connect_to_raspi()
        if client_socket is None:
            print("Retrying connection in 3 seconds...")
            time.sleep(3)
            continue

    left, right, up, down = get_motor_commands()

    with claw_lock:
        command = f"L:{left},R:{right},U:{up},D:{down},Claw:{claw_pos}\n"

    try:
        client_socket.sendall(command.encode())
        print("Command sent:", command.strip())
    except Exception as e:
        print("Error during send:", e)
        client_socket.close()
        client_socket = None
        time.sleep(2)
        continue

    time.sleep(0.1)  # update rate
