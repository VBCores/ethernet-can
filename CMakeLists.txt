cmake_minimum_required(VERSION 3.16)
project(ethernet-can)

include_directories()

file(GLOB SOURCES "src/*.cpp")
 
add_executable(ethernet-can ${SOURCES})

install(TARGETS ethernet-can RUNTIME DESTINATION /opt/voltbro/ethernet-can/bin)

install(PROGRAMS extra/start_ethernet_can.py DESTINATION /opt/voltbro/ethernet-can/bin)

install(FILES extra/ethernet-can.service DESTINATION /opt/voltbro/ethernet-can/systemd)
