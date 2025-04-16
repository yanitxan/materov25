import pigpio
import socket
import time
import threading

MOTORS = {
    'L': {'PWM': 12, 'DIR': 20},  # left
    'R': {'PWM': 13, 'DIR': 21},  # right
    'U': {'PWM': 18, 'DIR': 5},   # up
    'D': {'PWM': 19, 'DIR': 6},   # down
}

CLAW_SERVO_PIN = 17  
PWM_FREQ = 1000

# pigpio
pi = pigpio.pi()
if not pi.connected:
    print("failed to connect to pigpio daemon thingy")
    exit()

# Set pin modes
for motor in MOTORS.values():
    pi.set_mode(motor['PWM'], pigpio.OUTPUT)
    pi.set_mode(motor['DIR'], pigpio.OUTPUT)

pi.set_mode(CLAW_SERVO_PIN, pigpio.OUTPUT)

# motor control
def set_motor(name, speed):
    motor = MOTORS[name]
    direction = 1 if speed >= 0 else 0
    duty = min(abs(speed), 255)

    pi.write(motor['DIR'], direction)
    pi.set_PWM_dutycycle(motor['PWM'], duty)

def stop_all_motors():
    for name in MOTORS:
        pi.set_PWM_dutycycle(MOTORS[name]['PWM'], 0)

def move_claw(angle):
    angle = max(0, min(180, angle))
    pulse = 500 + (angle / 180) * 2000
    pi.set_servo_pulsewidth(CLAW_SERVO_PIN, pulse)

# watchdog
last_command_time = time.time()
def watchdog():
    global last_command_time
    while True:
        if time.time() - last_command_time > 5:
            stop_all_motors()
        time.sleep(1)

threading.Thread(target=watchdog, daemon=True).start()

# socket setup
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('', 8080))
server.listen(1)
print("waiting for controller connection")

try:
    conn, addr = server.accept()
    print("controller connected from", addr)
    buffer = ""

    while True:
        data = conn.recv(1024).decode()
        if not data:
            break
        buffer += data
        while '\n' in buffer:
            line, buffer = buffer.split('\n', 1)
            try:
                print("received:", line)
                parts = line.strip().split(",")
                cmd = {p.split(":")[0]: int(p.split(":")[1]) for p in parts}

                set_motor('L', cmd.get("L", 0))
                set_motor('R', cmd.get("R", 0))
                set_motor('U', cmd.get("U", 0) if cmd.get("D", 0) == 0 else 0)
                set_motor('D', cmd.get("D", 0) if cmd.get("U", 0) == 0 else 0)
                move_claw(cmd.get("Claw", 90))

                last_command_time = time.time()

            except Exception as e:
                print("errror:", e)

except KeyboardInterrupt:
    print("shutting down")

finally:
    stop_all_motors()
    pi.set_servo_pulsewidth(CLAW_SERVO_PIN, 0)
    pi.stop()
    conn.close()
    server.close()
    print("exit")
