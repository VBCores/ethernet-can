

### libs
https://github.com/metayeti/mINI


### build
mkdir build && cd build

cmake ..
cmake --build .

sudo cmake --install .

After install look /opt/voltbro

#### Add to robot startup

sudo cp ./extra/ethernet-can.service /lib/systemd/system/
sudo systemctl start ethernet-can.service
sudo systemctl enable ethernet-can.service