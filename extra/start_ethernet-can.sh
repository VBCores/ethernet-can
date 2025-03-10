#!/bin/bash

sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set vcan0 mtu 72
sudo ip link set vcan0 up

/opt/voltbro/bin/ethernet-can --config /opt/voltbro/ethernet-can/config.ini
