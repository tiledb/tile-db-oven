#!/bin/bash
# reset-pico-w.sh
# Power-cycle Pico W USB port with 10s delay and USB verification

VENDOR_ID="2e8a"
PRODUCT_ID="0005"

DEVICE_PATH=""

echo "Listing USB devices before reset:"
lsusb
echo "---------------------------"

# Find the Pico W device
for DEV in /sys/bus/usb/devices/*; do
    if [ -f "$DEV/idVendor" ] && [ -f "$DEV/idProduct" ]; then
        VID=$(cat "$DEV/idVendor")
        PID=$(cat "$DEV/idProduct")
        if [ "$VID" == "$VENDOR_ID" ] && [ "$PID" == "$PRODUCT_ID" ]; then
            DEVICE_PATH="$DEV"
            break
        fi
    fi
done

if [ -z "$DEVICE_PATH" ]; then
    echo "Pico W not found!"
    exit 1
fi

DEV_NAME=$(basename "$DEVICE_PATH")
echo "Found Pico W at $DEVICE_PATH"

# Unbind (power off)
echo "Unbinding USB driver (power off)..."
echo -n "$DEV_NAME" | sudo tee /sys/bus/usb/drivers/usb/unbind
echo "Waiting 10 seconds for device to disconnect..."
sleep 10

echo "Listing USB devices after unbind:"
lsusb
echo "---------------------------"

# Bind (power on)
echo "Binding USB driver (power on)..."
echo -n "$DEV_NAME" | sudo tee /sys/bus/usb/drivers/usb/bind

echo "Listing USB devices after bind:"
lsusb
echo "---------------------------"

echo "Done! Pico W should reboot now."