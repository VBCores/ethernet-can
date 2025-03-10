#ifndef HELPERS_H
#define HELPERS_H

#include <stdint.h>

uint8_t decode_bus_num( uint32_t encoded_bus_num );
uint32_t decode_can_id( uint32_t encoded_can_id );
uint32_t encode_bus_id( uint8_t bus_num, uint32_t can_id );

#endif  // this file will only ever be copied in once to another file
