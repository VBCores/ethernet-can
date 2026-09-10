cmake_minimum_required(VERSION 3.16)
project(ethernet-can VERSION 0.3.0)

include_directories()

file(GLOB SOURCES "src/*.cpp")
 
add_executable(ethernet-can ${SOURCES})

install(TARGETS ethernet-can RUNTIME DESTINATION /opt/voltbro/ethernet-can/bin)

install(PROGRAMS extra/start_ethernet_can.py DESTINATION /opt/voltbro/ethernet-can/bin)

install(FILES extra/ethernet-can.service DESTINATION /opt/voltbro/ethernet-can/systemd)
install(FILES extra/ethernet-can-mdns.conf DESTINATION /opt/voltbro/ethernet-can/systemd)

install(FILES extra/ethernet-can.service DESTINATION /lib/systemd/system)
install(DIRECTORY extra/configs/ DESTINATION /opt/voltbro/ethernet-can/examples)
install(FILES README.md README_ru.md DESTINATION /opt/voltbro/ethernet-can/docs)
install(DIRECTORY instructions DESTINATION /opt/voltbro/ethernet-can/docs)
install(DIRECTORY extra/ DESTINATION /opt/voltbro/ethernet-can/docs/extra
        PATTERN "__pycache__" EXCLUDE)

set(ETHERCAN_DEB_VERSION "${PROJECT_VERSION}~rc2" CACHE STRING "Debian package version")
set(CPACK_GENERATOR DEB)
set(CPACK_PACKAGE_NAME ethernet-can-host)
set(CPACK_PACKAGE_CONTACT "VBCores")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Ethernet-CAN to Linux SocketCAN bridge")
set(CPACK_PACKAGE_VERSION "${ETHERCAN_DEB_VERSION}")
set(CPACK_DEBIAN_PACKAGE_SECTION net)
set(CPACK_DEBIAN_PACKAGE_PRIORITY optional)
set(CPACK_DEBIAN_PACKAGE_SHLIBDEPS ON)
set(CPACK_DEBIAN_PACKAGE_DEPENDS "python3 (>= 3.10), python3-requests, python3-tenacity, iproute2, kmod, systemd, init-system-helpers")
set(CPACK_DEBIAN_PACKAGE_RECOMMENDS "can-utils, avahi-daemon, libnss-mdns")
execute_process(COMMAND dpkg --print-architecture
                OUTPUT_VARIABLE DEB_ARCH OUTPUT_STRIP_TRAILING_WHITESPACE
                RESULT_VARIABLE DEB_ARCH_RESULT)
if(NOT DEB_ARCH_RESULT EQUAL 0 OR NOT DEB_ARCH MATCHES "^(amd64|arm64)$")
  message(FATAL_ERROR "Debian packaging supports amd64 and arm64 only")
endif()
set(CPACK_DEBIAN_PACKAGE_ARCHITECTURE "${DEB_ARCH}")
set(CPACK_DEBIAN_FILE_NAME "ethernet-can-host_${DEB_ARCH}.deb")
set(CPACK_DEBIAN_PACKAGE_CONTROL_STRICT_PERMISSION ON)
set(CPACK_DEBIAN_PACKAGE_CONTROL_EXTRA
    "${CMAKE_CURRENT_SOURCE_DIR}/package/debian/postinst"
    "${CMAKE_CURRENT_SOURCE_DIR}/package/debian/prerm"
    "${CMAKE_CURRENT_SOURCE_DIR}/package/debian/postrm")
include(CPack)
