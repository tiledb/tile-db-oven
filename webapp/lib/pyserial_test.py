import serial
ser = serial.Serial("/dev/ttyACM0", 115200)
print("Connected")
ser.close()
