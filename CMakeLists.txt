cmake_minimum_required(VERSION 3.16)
project(ethernet-can)

find_package(Boost REQUIRED COMPONENTS program_options )
include_directories( ${Boost_INCLUDE_DIRS} )

#Bring the headers, such as Student.h into the project
include_directories()

#However, the file(GLOB...) allows for wildcard additions:
file(GLOB SOURCES "src/*.cpp")
 
add_executable(ethernet-can ${SOURCES})
target_link_libraries(ethernet-can ${Boost_LIBRARIES})

install(TARGETS ethernet-can RUNTIME DESTINATION /opt/voltbro/ethernet-can/bin)

install(PROGRAMS extra/start_ethernet_can.py DESTINATION /opt/voltbro/ethernet-can/bin)

install(FILES extra/ethernet-can.service DESTINATION /opt/voltbro/ethernet-can/systemd)
install(FILES extra/configs/example.ini DESTINATION /opt/voltbro/ethernet-can)
