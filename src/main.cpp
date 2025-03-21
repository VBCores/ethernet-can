// Server side implementation of UDP client-server model
#define MAX_EVENTS 5

#include <cassert>

#include <unistd.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <sys/epoll.h>
#include <sys/timerfd.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <fcntl.h>
#include <linux/can.h>
#include <linux/can/raw.h>

#include <iostream>
using namespace std;

#include "helpers.h"
#include "circ_buffer.h"

#include <boost/program_options.hpp>
#include "../libs/mINI/src/mini/ini.h" // Ini-file parser library

#define SRV_PORT     1556
#define CLT_PORT     1555

typedef struct
{
  uint16_t nominal_baudrate;
  uint16_t data_baudrate;
} FDCAN_PERIPH_PARAMS;

typedef struct
{
  uint32_t magic_number;
  uint32_t frames_integration_period;
  FDCAN_PERIPH_PARAMS bus[6];
} DEVICE_FDCAN_CONFIG;

namespace po = boost::program_options;

DEVICE_FDCAN_CONFIG sosiska = { 0 };

uint64_t frames_integration_period = 0; // nanoseconds
uint8_t frames_written = 0;

int tfd;
struct itimerspec timerValue;

int sockfd;
struct sockaddr_in  servaddr, cliaddr;

void udp_receive(void);
void udp_transmit(void);
int canfd_init(std::string can_name, int nonblock  );

void ConfigParser(std::string file_path);
////////////////////////////////////////////////
bool getBit(unsigned char byte, int position) // position in range 0-7
{
    return (byte >> position) & 0x1;
}

uint8_t write_can_frame(buffer_instance * s, uint8_t lcl_bus, uint32_t lcl_id, uint8_t data_length, uint8_t *data)
{
	uint8_t can_message_length = data_length + 5; // together with service bytes
	
	write_buffer(s, &can_message_length, 1); // write message length
	
	can_message_length -= 5; // 25 bytes with the service info
	
	uint8_t bus = lcl_bus;
	uint32_t id = lcl_id;
	uint32_t bus_id = encode_bus_id( bus, id );
	
	write_buffer(s, (uint8_t*)&bus_id, 4); // write bus id
	write_buffer(s, data, can_message_length); // write message
	
	return 0;
}

uint8_t gaga_buf[buf_size] = {0};
buffer_instance gaga = {0, 0, 0, gaga_buf};

uint8_t tx_buf[buf_size] = {0};
buffer_instance udp_tx_buf = {0, 0, 0, tx_buf};

string server_address = {0};
string client_address = {0};

int can_sockets[6] = {-1,-1,-1,-1,-1,-1};

bool frame_integraion = true;

uint16_t nominal_baud = 0;
uint16_t data_baud = 0;

// Driver code
int main(int argc, char* argv[])
{
	/// get configs from ini file

    po::options_description desc("Allowed options");

    desc.add_options()
        ("help", "produce help message")
        // ("config", po::value<std::string>()->default_value("../config/config.ini"), "set config file");
        ("config", po::value<std::string>(), "set config file. example: ~/.config/ethernet-can/config.ini");

    po::variables_map vm;
    po::store(po::parse_command_line(argc, argv, desc), vm);
    po::notify(vm);

    if (vm.count("help")) {
        std::cout << desc << "\n";
        return 0;
    }
    if (!vm.count("config")) {
        std::cout << desc << "\n";
        return 0;
    }	

    std::cout << "Config file: " << vm["config"].as<std::string>() << std::endl;

	mINI::INIFile file(vm["config"].as<std::string>());
	mINI::INIStructure ini;
	file.read(ini);
	
	if( ini["DATA_ACQUIZITION"].has("Period") )
	{
		int value = std::stoi( ini.get("DATA_ACQUIZITION").get("Period") ); // convert string from config file to int
		assert(value >= 0 && value < 1000000000);
		frames_integration_period = value;
		
		if( value == 0 )
		{
			frame_integraion = false;
			cout << "Frame integration is disabled " << endl;
		}
		else
		{
			frame_integraion = true;
			cout << "Frame integration is enabled " << endl;
			cout << "Update period is set to " << frames_integration_period << " ns" << endl;
		}
	}
	else
	{
		cout << "Failed to read update period from ini file" << endl;
	}
	
	if( ini["NETWORK_PARAMS"].has("Host_IP_address") )
	{
		server_address = ini.get("NETWORK_PARAMS").get("Host_IP_address");
		cout << "Host address: " << server_address << endl;
	}
	else
	{
		cout << "main: failed to read host IP-address from ini file" << endl;
	}
	
	if( ini["NETWORK_PARAMS"].has("Device_IP_address") )
	{
		client_address = ini.get("NETWORK_PARAMS").get("Device_IP_address");
		cout << "Device address: " << client_address << endl;
	}
	else
	{
		cout << "main: failed to read device IP-address from ini file" << endl;
	}
	
	if( ini["FDCAN_PARAMS"].has("Enabled_buses") )
	{
		uint8_t value = std::stoi( ini.get("FDCAN_PARAMS").get("Enabled_buses"), nullptr, 2);
		assert( value < 64 );
		cout << "Enabled buses are:" << endl;
		
		for( int i = 0; i < 6; i++)
		{
			can_sockets[i] = getBit(value,5-i) - 1; // 1=>0; 0=>-1
			if( can_sockets[i] >= 0 )
			{
				cout << "	CAN" << i << endl;
			}
		}
	}
	else
	{

	}
	
	if( ini["FDCAN_PARAMS"].has("Nominal_baud") )
	{
		int value = std::stoi( ini.get("FDCAN_PARAMS").get("Nominal_baud") ); // convert string from config file to int
		assert( value == 0 || value == 125 || value == 250 || value == 500 || value == 1000 );
		nominal_baud = value;
		
		cout << "Nominal baudrate: " << value << endl;
	}
	else
	{

	}
	
	if( ini["FDCAN_PARAMS"].has("Data_baud") )
	{
		int value = std::stoi( ini.get("FDCAN_PARAMS").get("Data_baud") ); // convert string from config file to int
		assert( value == 0 || value == 1000 || value == 2000 || value == 4000 || value == 8000 );
		data_baud = value;
		
		cout << "Data baudrate: " << value << endl;
	}
	else
	{

	}
	
	if( nominal_baud && data_baud )
	{
		cout << "FDCAN with BRS is enabled" << endl;
	}
	else if( nominal_baud )
	{
		cout << "Classic CAN is enabled" << endl;
	}
	else
	{
		cout << "Why do you want CAN disabled? Exiting" << endl;
		exit(EXIT_FAILURE);
	}
	
	cout << "Setup is complete!" << endl << endl;
	
	/// creating timer
	if ( (tfd = timerfd_create(CLOCK_REALTIME,  0)) < 0 )
	{
		perror("timer creation failed");
		exit(EXIT_FAILURE);
	}
	
	// should frames be sent immediately upon arrival or periodically in batches?
	if( frame_integraion )
	{
		timerValue.it_value.tv_sec = 0;
		timerValue.it_value.tv_nsec = frames_integration_period;
		timerValue.it_interval.tv_sec = 0;
		timerValue.it_interval.tv_nsec = frames_integration_period;
		
		timerfd_settime(tfd, 0, &timerValue, NULL);
	}
	
	/// opening udp rx socket
	
	// Creating socket file descriptor
	if ( (sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0 )
	{
		perror("socket creation failed");
		exit(EXIT_FAILURE);
	}
	
	fcntl(sockfd, F_SETFL, O_NONBLOCK);
	
	// Filling server information
	servaddr.sin_family    = AF_INET; // IPv4
	servaddr.sin_addr.s_addr = inet_addr(server_address.c_str());
	servaddr.sin_port = htons(SRV_PORT);
	
	// Filling client information
	cliaddr.sin_family    = AF_INET; // IPv4
	cliaddr.sin_addr.s_addr = inet_addr(client_address.c_str());
	cliaddr.sin_port = htons(CLT_PORT);
	
	// Bind the socket with the server address
	if ( bind(sockfd, (const struct sockaddr *)&servaddr, sizeof(servaddr)) < 0 )
	{
		perror("bind failed");
		exit(EXIT_FAILURE);
	}
	
	/// setup epoll
	
	struct epoll_event event;
	struct epoll_event events[MAX_EVENTS];
	
	int epoll_fd = epoll_create1(0);
	
	if (epoll_fd == -1)
	{
		perror("epoll creation failed");
		exit(EXIT_FAILURE);
	}	
	
	event.events = EPOLLIN | EPOLLET;
	event.data.fd = tfd;
	
	if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, tfd, &event))
	{
		close(epoll_fd);
		perror("epoll failed to bind timer fd");
		exit(EXIT_FAILURE);
	}
	else
	{
		cout << "Bound timer fd to epoll" << endl;
	}
	
	event.data.fd = sockfd;
	
	if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, sockfd, &event))
	{
		close(epoll_fd);
		perror("epoll failed to bind udp socket");
		exit(EXIT_FAILURE);
	}
	else
	{
		cout << "Bound UDP socket to epoll" << endl;
	}
	
	sosiska.magic_number = 0x9a0a6ac6;
	sosiska.frames_integration_period = frames_integration_period;
	
	for( int i = 0; i < 6; i++ )
	{
		if( can_sockets[i] >= 0 )
		{
			string sock_name = "vcan" + std::to_string(i);
			can_sockets[i] = canfd_init(sock_name.c_str(), true);
			
			if( can_sockets[i] < 0 )
			{
				string error_message = "Failed to open " + sock_name;
				perror(error_message.c_str());
				exit(EXIT_FAILURE);
			}
			else
			{
				cout << "Opened " << sock_name << " socket" << endl;
			}
			
			/////////////////////////////////////////////////////////
			
			event.events = EPOLLIN;// | EPOLLOUT | EPOLLET;
			event.data.fd = can_sockets[i];
			
			if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, can_sockets[i], &event))
			{
				close(epoll_fd);
				perror("epoll failed to bind can socket");
				exit(EXIT_FAILURE);
			}
			else
			{
				cout << "Bound " << sock_name << " socket to epoll" << endl;
			}
			
			sosiska.bus[i].nominal_baudrate = nominal_baud;
			sosiska.bus[i].data_baudrate = data_baud;
		}
	}
	
	if( sendto( sockfd,
	&sosiska,
	sizeof(sosiska),
	0,
	(const struct sockaddr *) &cliaddr, sizeof(cliaddr)) < 0 )
	{
		perror("sendto");
	}
	///////////////////////////////////////////////////////////////

	//cout << "bytes_in_frame " << udp_tx_buf.bytes_written << endl;
	
	while( 1 )
	{
		//cout << "Polling for input..." << endl;
		int event_count = epoll_wait(epoll_fd, events, MAX_EVENTS, -1);
		
		canfd_frame rx_frame; // structure to store incoming CAN message
		rx_frame.flags = CANFD_BRS; // CANFD bit-rate switch is enabled
		
		// iterate over reported events. should not exceed 1 event normally
		for( int j = 0; j < event_count; j++)
		{
			// only EPOLLIN events are processed
			if( events[j].events != EPOLLIN )
			{
				perror("Unsupported event happened");
				exit(EXIT_FAILURE);
			}
			
			// UDP socket event?
			if( events[j].data.fd == sockfd )
			{
				udp_receive();
				continue;
			}
			
			// timer event?
			if( events[j].data.fd == tfd )
			{
				uint8_t dummy_buf[8];
				read(tfd, dummy_buf, 8);
				
				if( frames_written > 0 )
				{
					// send combined frames to the client
					udp_transmit();
				}
				
				continue;
			}
			
			// iterate over all posibly enabled CAN sockets
			for( int i = 0; i < 6; i++)
			{
				// skip disabled socket
				if( can_sockets[i] < 0 )
				{
					continue;
				}
				
				// process enabled socket
				if( events[j].data.fd == can_sockets[i] )
				{
					while( read(can_sockets[i], &rx_frame, CANFD_MTU) == CANFD_MTU ) // while there are valid frames in socket
					{
						if( udp_tx_buf.bytes_written + rx_frame.len + 5 > 512 ) // check if new frame will fit in partialy loaded buffer
						{
							// send full buffer to the client
							udp_transmit();
						}
						
						write_can_frame(&udp_tx_buf, i, rx_frame.can_id, rx_frame.len, rx_frame.data);
						frames_written ++;
						
						if( !frame_integraion )
						{
							// send received frame immediately
							udp_transmit();
						}
					}
				}
			}
		}
	}
	
	close(sockfd);
	
	return 0;
}

uint8_t tx_buffer[buf_size] = {0};
volatile uint64_t packet_counter = 0;

uint8_t my_data[8192] = {0};

void udp_receive(void)
{
	struct sockaddr_in dummy;
	socklen_t len = 0;
	
	int packet_length = recvfrom(  sockfd, my_data, 8192, 0, (struct sockaddr *) &dummy, &len);
	
	if( packet_length < 0 )
	{
		return ;
	}
	
	// cout << "packet_length " << (int)packet_length << endl;
	
	uint16_t index = 0; // specifies number of bytes read from the udp packet.
	
	while( index < packet_length ) // iterate over UDP packet
	{
		canfd_frame tx_frame; // structure to store incoming CAN message
		tx_frame.flags = CANFD_BRS; // CANFD bit-rate switch is enabled
		
		uint32_t bus_id = 0;
		
		// parse one can frame from the rx UDP packet
		uint8_t can_message_length = my_data[index] - 5;
		tx_frame.len = can_message_length;
		index += 1;
		memcpy(&bus_id, &my_data[index], 4);
		index += 4;
		memcpy( tx_frame.data, &my_data[index], can_message_length);
		index += can_message_length;
		
		tx_frame.can_id = decode_can_id( bus_id ) | CAN_EFF_FLAG;
		
		uint8_t bus_num = decode_bus_num( bus_id );
		
		int socket = can_sockets[bus_num]; // select socket to process
		
		if( socket >= 0 ) // process socket if is enabled
		{
			if (write(socket, &tx_frame, CANFD_MTU) != CANFD_MTU)
			{
				perror("Write"); // CANFD_MTU = 72
			}
		}
	}
	
	if( index != packet_length )
	{
		cout << "I'm dead" << endl;
		while(1);
	}
}

void udp_transmit(void)
{
	if( sendto( sockfd,
	udp_tx_buf.buffer_body,
	udp_tx_buf.bytes_written,
	0,
	(const struct sockaddr *) &cliaddr, sizeof(cliaddr)) < 0 )
	{
		perror("sendto");
	}

	cout << "bytes_in_frame " << udp_tx_buf.bytes_written << endl;

	udp_tx_buf.bytes_written = 0;
	udp_tx_buf.head = 0;
	udp_tx_buf.tail = 0;
	frames_written = 0;
}

void ConfigParser(std::string file_path)
{
	//mINI::INIFile file(file_path);
	//mINI::INIStructure ini;
	
	//file.read(ini);
	
	//frames_integration_period =
	
	/*
	for( int i = 1; i < 13; i++)
	{
		std::string DriveNumber = std::to_string(i);
		//check if parameter exists
		if( ini["ACTUATORS"].has("RotDir"+DriveNumber) )
		{
			int value = std::stoi( ini.get("ACTUATORS").get("RotDir"+DriveNumber) ); // convert string from config file to int
			assert(value >= -1 && value <= 2);
			cout << "Read ini: " << value << endl;
		}
		else
		{
			perror("Config");
		}
	}
	*/
	return ;
}

int canfd_init(std::string can_name, int nonblock  )
{
	int enable_canfd = 1;
	struct ifreq ifr;
	struct sockaddr_can addr;
	int s = 0;
	if ((s = socket(PF_CAN, SOCK_RAW, CAN_RAW)) < 0) { perror("Socket");}
	
	if( nonblock )
	{
		fcntl(s, F_SETFL, O_NONBLOCK); // non blocking CAN frame receiving => reading from this socket does not block execution.
	}
	
	strcpy(ifr.ifr_name, can_name.c_str() );
	ioctl(s, SIOCGIFINDEX, &ifr);
	
	memset(&addr, 0, sizeof(addr));
	addr.can_family = AF_CAN;
	addr.can_ifindex = ifr.ifr_ifindex;
	
	if (setsockopt(s, SOL_CAN_RAW, CAN_RAW_FD_FRAMES, &enable_canfd, sizeof(enable_canfd))) { perror("FD");}
	
	//int optval=7; // valid values are in the range [1,7] ; 1- low priority, 7 - high priority
	//if ( setsockopt(s, SOL_SOCKET, SO_PRIORITY, &optval, sizeof(optval))) { perror("Priority");} //makes no difference on receiving
	//if ( setsockopt(*s, SOL_SOCKET, SO_BUSY_POLL, &optval, sizeof(optval))) { perror("Busy poll");} //makes no difference on receiving
	if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) { perror("Bind"); return 0; }
	
	return s;
}
