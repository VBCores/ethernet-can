#include "circ_buffer.h"

uint8_t write_buffer(buffer_instance * s, uint8_t * local_buffer, uint16_t num_to_write)
{
  if( buf_size - s->bytes_written > num_to_write )
  {
      int16_t start_index = s->tail; // can be negative
      uint16_t local_tail = s->tail;
      for( int i = 0; i < num_to_write; i++)
      {
          /// check on the end of buffer
          /// if so, the start index is moved to the beginning of the buffer.
          /// normally should be fired no more than once per write operation (otherwise the message is bigger than buffer).
          if( start_index + i > buf_size - 1 )
          {
              start_index -= buf_size;
          }
          s->buffer_body[ start_index + i ] = local_buffer[i];
      }

      s->bytes_written += num_to_write;
      s->tail = update_index( s->tail, buf_size, num_to_write);
  }
  else
  {
    /// buffer is full!
    return 1;
  }
  return 0;
}

uint8_t read_buffer(buffer_instance * s, uint8_t * local_buffer, uint16_t num_to_read)
{
    if( num_to_read > s->bytes_written )
    {
        /// too much data is required to be read!
        return 1;
    }
    else
    {
        int16_t start_index = s->head; // can be negative
        uint16_t local_head = s->head;
        for( int i = 0; i < num_to_read; i++)
        {
            /// check on the end of buffer
            /// if so, the start index is moved to the beginning of the buffer.
            /// normally should be fired no more than once per write operation (otherwise the message is bigger than buffer).
            if( start_index + i > buf_size - 1 )
            {
                start_index -= buf_size;
            }
            local_buffer[i] = s->buffer_body[ start_index + i ];
        }

        s->bytes_written -= num_to_read;
        s->head = update_index( s->head, buf_size, num_to_read);
    }
    return 0;
}

uint16_t update_index( uint16_t index, uint16_t buffer_size, uint16_t shift)
{
  uint16_t local_head = index + shift;
  if( local_head >= buf_size )
  {
      local_head -= buf_size;
  }
  return local_head;
}
