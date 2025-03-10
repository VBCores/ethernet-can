sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set vcan0 mtu 72
sudo ip link set vcan0 up
# sudo modprobe vcan &&

# sudo ip link add dev vcan1 type vcan
# sudo ip link set vcan1 mtu 72
# sudo ip link set vcan1 up

# sudo ip link add dev vcan3 type vcan
# sudo ip link set vcan3 mtu 72
# sudo ip link set vcan3 up

# sudo ip link add dev vcan4 type vcan
# sudo ip link set vcan4 mtu 72
# sudo ip link set vcan4 up
