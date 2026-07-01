import serial
import time

# 시리얼 포트 설정 (환경에 맞게 COM 포트 수정)
ser = serial.Serial('COM6', 115200, timeout=1)

def send_packet_mrtexe(exe_index):
    exe_cmd = [
        0xff, 0xff, 0x4c, 0x53, 0x00,
        0x00, 0x00, 0x00, 0x30, 0x0c, 0x03,
        0x01, 0x00, 100, 0x00
    ]

    exe_cmd[11] = exe_index
    checksum = sum(exe_cmd[6:14]) & 0xFF
    exe_cmd[14] = checksum

    #ser.write(bytearray(exe_cmd))
    ser.write(exe_cmd)
    print(f"Sent packet: {exe_cmd}")
    time.sleep(0.1)

try:
    print("Sending packet repeatedly every 5 seconds...")
    while True:
        send_packet_mrtexe(18)
        time.sleep(10)

except KeyboardInterrupt:
    print("프로그램 종료")

finally:
    ser.close()
