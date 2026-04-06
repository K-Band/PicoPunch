"""
Pico W Wireless Punch Capture - main.py
Creates AP, samples sensors, sends punch data over TCP.
Save as main.py on the Pico W.
"""

# ============================================
# EASY CONFIG - CHANGE THESE
# ============================================
SAMPLE_RATE_HZ = 1000
PRE_MS = 250
POST_MS = 250
FSR_TRIGGER_V = 1.65
COOLDOWN_MS = 500
AP_SSID = "PicoPunch"
AP_PASS = "12345678"
TCP_PORT = 8888
# ============================================

import network
import socket
from machine import Pin, I2C, ADC
from time import sleep_ms, sleep_us, ticks_ms, ticks_us, ticks_diff
import struct
import array
import gc

SAMPLE_INTERVAL_US = 1000000 // SAMPLE_RATE_HZ
PRE_SAMPLES = (PRE_MS * SAMPLE_RATE_HZ) // 1000
POST_SAMPLES = (POST_MS * SAMPLE_RATE_HZ) // 1000

# --- Hardware ---
MPU_ADDR = 0x68
i2c = I2C(1, sda=Pin(6), scl=Pin(7), freq=400_000)
fsr = ADC(Pin(26))
led = Pin("LED", Pin.OUT)

def mpu_write(reg, val):
    i2c.writeto_mem(MPU_ADDR, reg, bytes([val]))

def mpu_read(reg, n):
    return i2c.readfrom_mem(MPU_ADDR, reg, n)

def mpu_init():
    devices = i2c.scan()
    if MPU_ADDR not in devices:
        print(f"ERROR:MPU not found. Bus: {[hex(d) for d in devices]}")
        return False
    mpu_write(0x6B, 0x00)
    sleep_ms(100)
    mpu_write(0x1C, 0x18)
    mpu_write(0x1B, 0x18)
    return True

def read_all():
    raw = mpu_read(0x3B, 14)
    ax = struct.unpack('>h', raw[0:2])[0] / 2048.0
    ay = struct.unpack('>h', raw[2:4])[0] / 2048.0
    az = struct.unpack('>h', raw[4:6])[0] / 2048.0
    gx = struct.unpack('>h', raw[8:10])[0] / 16.4
    gy = struct.unpack('>h', raw[10:12])[0] / 16.4
    gz = struct.unpack('>h', raw[12:14])[0] / 16.4
    return (ax, ay, az, gx, gy, gz)

# --- Buffers ---
V = 9
ring = array.array('f', [0.0] * (PRE_SAMPLES * V))
post = array.array('f', [0.0] * (POST_SAMPLES * V))
ridx = 0

def ring_write(t, ax, ay, az, gx, gy, gz, fr, fv):
    global ridx
    b = ridx * V
    ring[b]=t; ring[b+1]=ax; ring[b+2]=ay; ring[b+3]=az
    ring[b+4]=gx; ring[b+5]=gy; ring[b+6]=gz
    ring[b+7]=fr; ring[b+8]=fv
    ridx = (ridx + 1) % PRE_SAMPLES

# --- WiFi AP ---
def start_ap():
    ap = network.WLAN(network.AP_IF)
    ap.config(essid=AP_SSID, password=AP_PASS)
    ap.active(True)
    while not ap.active():
        sleep_ms(100)
        led.toggle()
    ip = ap.ifconfig()[0]
    print(f"AP ready: {AP_SSID} @ {ip}:{TCP_PORT}")
    led.on()
    return ip

# --- TCP send helper ---
def tcp_send(client, msg):
    """Send a line over TCP with newline terminator"""
    client.send((msg + "\n").encode())

# --- Main ---
def main():
    global ridx

    if not mpu_init():
        return

    gc.collect()
    ip = start_ap()

    # Set up TCP server
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((ip, TCP_PORT))
    srv.listen(1)
    print(f"Waiting for dashboard to connect on {ip}:{TCP_PORT}...")

    while True:
        # Wait for a client connection
        client, addr = srv.accept()
        print(f"Dashboard connected from {addr}")
        led.off()
        sleep_ms(100)
        led.on()

        try:
            tcp_send(client, "PUNCH_READY")
            tcp_send(client, f"CONFIG: {SAMPLE_RATE_HZ}Hz | {PRE_MS}ms pre + {POST_MS}ms post | {PRE_SAMPLES}+{POST_SAMPLES}={PRE_SAMPLES+POST_SAMPLES} samples/punch")

            last_trigger = 0
            punch_num = 0

            # Reset ring buffer
            for i in range(len(ring)):
                ring[i] = 0.0
            ridx = 0

            while True:
                t_loop = ticks_us()

                ax, ay, az, gx, gy, gz = read_all()
                fr = fsr.read_u16()
                fv = fr * 3.3 / 65535
                t = ticks_ms()

                ring_write(t, ax, ay, az, gx, gy, gz, fr, fv)

                # Check trigger
                if fv >= FSR_TRIGGER_V and ticks_diff(t, last_trigger) > COOLDOWN_MS:
                    led.on()
                    last_trigger = t
                    punch_num += 1
                    trigger_t = t

                    # Capture post-trigger into buffer (no sending!)
                    post_start = ticks_us()
                    for i in range(POST_SAMPLES):
                        tp = ticks_us()
                        ax, ay, az, gx, gy, gz = read_all()
                        fr = fsr.read_u16()
                        fv = fr * 3.3 / 65535
                        b = i * V
                        post[b] = ticks_ms()
                        post[b+1]=ax; post[b+2]=ay; post[b+3]=az
                        post[b+4]=gx; post[b+5]=gy; post[b+6]=gz
                        post[b+7]=fr; post[b+8]=fv
                        el = ticks_diff(ticks_us(), tp)
                        if el < SAMPLE_INTERVAL_US:
                            sleep_us(SAMPLE_INTERVAL_US - el)
                    post_elapsed = ticks_diff(ticks_us(), post_start)
                    post_hz = POST_SAMPLES * 1000000 / post_elapsed if post_elapsed > 0 else 0

                    led.off()

                    # Now send everything over TCP
                    tcp_send(client, f"PUNCH_START:{punch_num}")

                    # Pre-trigger
                    pre_count = 0
                    for i in range(PRE_SAMPLES):
                        idx = ((ridx + i) % PRE_SAMPLES) * V
                        st = ring[idx]
                        if st == 0:
                            continue
                        dt = ticks_diff(int(st), trigger_t)
                        tcp_send(client, f"{dt},{ring[idx+1]:.2f},{ring[idx+2]:.2f},{ring[idx+3]:.2f},{ring[idx+4]:.1f},{ring[idx+5]:.1f},{ring[idx+6]:.1f},{int(ring[idx+7])},{ring[idx+8]:.3f}")
                        pre_count += 1

                    # Post-trigger
                    for i in range(POST_SAMPLES):
                        b = i * V
                        dt = ticks_diff(int(post[b]), trigger_t)
                        tcp_send(client, f"{dt},{post[b+1]:.2f},{post[b+2]:.2f},{post[b+3]:.2f},{post[b+4]:.1f},{post[b+5]:.1f},{post[b+6]:.1f},{int(post[b+7])},{post[b+8]:.3f}")

                    tcp_send(client, "PUNCH_END")
                    tcp_send(client, f"STATS:punch={punch_num},pre={pre_count},post={POST_SAMPLES},post_hz={post_hz:.0f},total={pre_count+POST_SAMPLES}")

                # Maintain sample rate
                elapsed = ticks_diff(ticks_us(), t_loop)
                if elapsed < SAMPLE_INTERVAL_US:
                    sleep_us(SAMPLE_INTERVAL_US - elapsed)

        except OSError as e:
            print(f"Connection lost: {e}")
            try:
                client.close()
            except:
                pass
            print("Waiting for reconnect...")

try:
    main()
except KeyboardInterrupt:
    print("STOPPED")
