cmake_minimum_required(VERSION 2.4)
project(ethernet-can)

find_package(Boost REQUIRED COMPONENTS program_options )
include_directories( ${Boost_INCLUDE_DIRS} )

#Bring the headers, such as Student.h into the project
include_directories()

#However, the file(GLOB...) allows for wildcard additions:
file(GLOB SOURCES "src/*.cpp")
 
add_executable(ethernet-can ${SOURCES})
target_link_libraries(ethernet-can ${Boost_LIBRARIES})


#install(TARGETS ethernet-can RUNTIME DESTINATION bin)
#install(DIRECTORY config DESTINATION $ENV{HOME}/.config/ethernet-can)

#install(TARGETS ethernet-can RUNTIME DESTINATION $ENV{HOME}/.local/bin)
#install(FILES config/config.ini DESTINATION $ENV{HOME}/.config/ethernet-can)

install(TARGETS ethernet-can RUNTIME DESTINATION /opt/voltbro/bin)
install(FILES config/config.ini DESTINATION /opt/voltbro/ethernet-can)

install(PROGRAMS extra/start_ethernet-can.sh DESTINATION /opt/voltbro/bin)
