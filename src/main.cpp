#include <array>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include <arpa/inet.h>
#include <fcntl.h>
#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <sys/epoll.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/timerfd.h>
#include <unistd.h>

namespace {
constexpr std::size_t kBusCount = 6;
constexpr std::uint16_t kServerPort = 1556;
constexpr std::uint16_t kClientPort = 1555;
constexpr std::size_t kMaxUdpPacketSize = 8192;
constexpr std::size_t kMaxBundledPayloadSize = 512;
constexpr int kMaxEvents = 32;
constexpr std::uint32_t kDeviceMagicNumber = 0x9a0a6ac6;

struct FdcanPeripheralParams {
    std::uint16_t nominal_baudrate = 0;
    std::uint16_t data_baudrate = 0;
};

struct DeviceFdcanConfig {
    std::uint32_t magic_number = kDeviceMagicNumber;
    std::uint32_t frames_integration_period = 0;
    std::array<FdcanPeripheralParams, kBusCount> bus {};
};

struct BoardConfig {
    std::string name;
    std::string device_ip;
    std::uint64_t integration_period_ns = 0;
    std::uint16_t nominal_baud = 0;
    std::uint16_t data_baud = 0;
    bool has_period = false;
    bool has_nominal = false;
    bool has_data = false;
    std::array<bool, kBusCount> enabled_buses {};
    std::array<std::string, kBusCount> interface_names {};

    std::string label() const {
        return name + " [" + device_ip + "]";
    }
};

std::uint8_t decode_bus_num(std::uint32_t encoded_bus_num) {
    return encoded_bus_num >> 29;
}

std::uint32_t decode_can_id(std::uint32_t encoded_can_id) {
    return encoded_can_id & 0x1FFFFFFFU;
}

std::uint32_t encode_bus_id(std::uint8_t bus_num, std::uint32_t can_id) {
    return (can_id & 0x1FFFFFFFU) | (static_cast<std::uint32_t>(bus_num) << 29U);
}

class BoardSession {
public:
    explicit BoardSession(BoardConfig cfg) : config(std::move(cfg)) {
        can_fds.fill(-1);

        remote_addr.sin_family = AF_INET;
        remote_addr.sin_port = htons(kClientPort);
        if (inet_pton(AF_INET, config.device_ip.c_str(), &remote_addr.sin_addr) != 1) {
            throw std::runtime_error("invalid device ip in " + config.label());
        }

        for (std::size_t bus = 0; bus < kBusCount; ++bus) {
            if (!config.enabled_buses[bus]) {
                continue;
            }

            const auto& iface = config.interface_names[bus];
            if (iface.empty()) {
                throw std::runtime_error("missing interface for " + config.label() + " bus " + std::to_string(bus));
            }
            if (iface.size() >= IFNAMSIZ) {
                throw std::runtime_error("CAN iface name too long: " + iface);
            }

            const int fd = ::socket(PF_CAN, SOCK_RAW, CAN_RAW);
            if (fd < 0) {
                throw std::runtime_error("socket(PF_CAN) failed for " + iface + ": " + std::strerror(errno));
            }

            if (::fcntl(fd, F_SETFL, O_NONBLOCK) < 0) {
                ::close(fd);
                throw std::runtime_error("fcntl(O_NONBLOCK) failed for " + iface + ": " + std::strerror(errno));
            }

            ifreq ifr {};
            std::strncpy(ifr.ifr_name, iface.c_str(), IFNAMSIZ - 1);
            if (::ioctl(fd, SIOCGIFINDEX, &ifr) < 0) {
                ::close(fd);
                throw std::runtime_error("SIOCGIFINDEX failed for " + iface + ": " + std::strerror(errno));
            }

            int enable_canfd = 1;
            if (::setsockopt(fd, SOL_CAN_RAW, CAN_RAW_FD_FRAMES, &enable_canfd, sizeof(enable_canfd)) < 0) {
                ::close(fd);
                throw std::runtime_error("setsockopt(CAN_RAW_FD_FRAMES) failed for " + iface + ": " +
                                         std::string(std::strerror(errno)));
            }

            sockaddr_can addr {};
            addr.can_family = AF_CAN;
            addr.can_ifindex = ifr.ifr_ifindex;
            if (::bind(fd, reinterpret_cast<const sockaddr*>(&addr), sizeof(addr)) < 0) {
                ::close(fd);
                throw std::runtime_error("bind(can) failed for " + iface + ": " + std::strerror(errno));
            }

            can_fds[bus] = fd;
        }

        if (config.integration_period_ns > 0) {
            timer_fd = ::timerfd_create(CLOCK_REALTIME, TFD_NONBLOCK);
            if (timer_fd < 0) {
                throw std::runtime_error("timerfd_create failed: " + std::string(std::strerror(errno)));
            }

            itimerspec spec {};
            spec.it_value.tv_sec = static_cast<time_t>(config.integration_period_ns / 1000000000ULL);
            spec.it_value.tv_nsec = static_cast<long>(config.integration_period_ns % 1000000000ULL);
            spec.it_interval = spec.it_value;
            if (::timerfd_settime(timer_fd, 0, &spec, nullptr) < 0) {
                ::close(timer_fd);
                timer_fd = -1;
                throw std::runtime_error("timerfd_settime failed: " + std::string(std::strerror(errno)));
            }
        }
    }

    ~BoardSession() {
        for (int fd : can_fds) {
            if (fd >= 0) {
                ::close(fd);
            }
        }
        if (timer_fd >= 0) {
            ::close(timer_fd);
        }
    }

    void send_startup_config(int udp_fd) {
        DeviceFdcanConfig packet;
        packet.frames_integration_period = static_cast<std::uint32_t>(config.integration_period_ns);

        for (std::size_t bus = 0; bus < kBusCount; ++bus) {
            if (!config.enabled_buses[bus]) {
                continue;
            }
            packet.bus[bus].nominal_baudrate = config.nominal_baud;
            packet.bus[bus].data_baudrate = config.data_baud;
        }

        const auto sent = ::sendto(
            udp_fd,
            &packet,
            sizeof(packet),
            0,
            reinterpret_cast<const sockaddr*>(&remote_addr),
            sizeof(remote_addr));

        if (sent != static_cast<ssize_t>(sizeof(packet))) {
            throw std::runtime_error("startup sendto failed for " + config.label() + ": " + std::strerror(errno));
        }
    }

    void on_udp_packet(const std::uint8_t* data, std::size_t size) {
        std::size_t index = 0;
        while (index < size) {
            if (size - index < 5) {
                throw std::runtime_error("truncated UDP frame from " + config.label());
            }

            const std::uint8_t message_length = data[index];
            if (message_length < 5 || index + message_length > size) {
                throw std::runtime_error("malformed UDP packet from " + config.label());
            }

            std::uint32_t bus_id = 0;
            std::memcpy(&bus_id, data + index + 1, sizeof(bus_id));

            const auto bus = decode_bus_num(bus_id);
            if (bus >= kBusCount || can_fds[bus] < 0) {
                throw std::runtime_error("packet for disabled bus " + std::to_string(bus) + " from " + config.label());
            }

            canfd_frame frame {};
            frame.len = static_cast<__u8>(message_length - 5U);
            frame.can_id = decode_can_id(bus_id) | CAN_EFF_FLAG;
            frame.flags = CANFD_BRS;
            std::memcpy(frame.data, data + index + 5, frame.len);

            const auto written = ::write(can_fds[bus], &frame, CANFD_MTU);
            if (written != CANFD_MTU) {
                throw std::runtime_error("write(can) failed for " + config.label() + " bus " + std::to_string(bus) +
                                         ": " + std::strerror(errno));
            }

            index += message_length;
        }
    }

    void on_can_readable(std::size_t bus, int udp_fd) {
        if (bus >= kBusCount || can_fds[bus] < 0) {
            throw std::runtime_error("internal error: invalid CAN bus index");
        }

        while (true) {
            canfd_frame frame {};
            const auto bytes_read = ::read(can_fds[bus], &frame, CANFD_MTU);
            if (bytes_read < 0) {
                if (errno == EAGAIN || errno == EWOULDBLOCK) {
                    break;
                }
                throw std::runtime_error("read(can) failed for " + config.label() + ": " + std::strerror(errno));
            }
            if (bytes_read != CANFD_MTU) {
                throw std::runtime_error("short CAN read for " + config.label());
            }

            if (tx_bundle.size() + frame.len + 5 > kMaxBundledPayloadSize) {
                flush_udp(udp_fd);
            }

            const auto message_length = static_cast<std::uint8_t>(frame.len + 5U);
            const auto bus_id = encode_bus_id(static_cast<std::uint8_t>(bus), frame.can_id);
            tx_bundle.push_back(message_length);
            const auto* bus_bytes = reinterpret_cast<const std::uint8_t*>(&bus_id);
            tx_bundle.insert(tx_bundle.end(), bus_bytes, bus_bytes + sizeof(bus_id));
            tx_bundle.insert(tx_bundle.end(), frame.data, frame.data + frame.len);

            if (config.integration_period_ns == 0) {
                flush_udp(udp_fd);
            }
        }
    }

    void on_timer(int udp_fd) {
        if (timer_fd < 0) {
            throw std::runtime_error("internal error: timer event without timer");
        }

        std::uint64_t expirations = 0;
        const auto bytes_read = ::read(timer_fd, &expirations, sizeof(expirations));
        if (bytes_read < 0 && errno != EAGAIN && errno != EWOULDBLOCK) {
            throw std::runtime_error("read(timerfd) failed: " + std::string(std::strerror(errno)));
        }

        flush_udp(udp_fd);
    }

    BoardConfig config;
    sockaddr_in remote_addr {};
    std::array<int, kBusCount> can_fds {};
    int timer_fd = -1;
    std::vector<std::uint8_t> tx_bundle;

private:
    void flush_udp(int udp_fd) {
        if (tx_bundle.empty()) {
            return;
        }

        const auto sent = ::sendto(
            udp_fd,
            tx_bundle.data(),
            tx_bundle.size(),
            0,
            reinterpret_cast<const sockaddr*>(&remote_addr),
            sizeof(remote_addr)
        );

        if (sent != static_cast<ssize_t>(tx_bundle.size())) {
            throw std::runtime_error("sendto failed for " + config.label() + ": " + std::strerror(errno));
        }

        tx_bundle.clear();
    }
};

class HostBridgeApp {
  public:
    HostBridgeApp(std::string host_ip, std::vector<BoardConfig> configs) {
        if (host_ip.empty()) {
            throw std::runtime_error("missing --host-ip");
        }
        if (configs.empty()) {
            throw std::runtime_error("no boards provided");
        }

        std::unordered_set<std::string> board_names;
        std::unordered_set<std::string> device_ips;
        std::unordered_map<std::string, std::string> interface_owners;

        for (const auto& config : configs) {
            if (!board_names.insert(config.name).second) {
                throw std::runtime_error("duplicate board name " + config.name);
            }
            if (!device_ips.insert(config.device_ip).second) {
                throw std::runtime_error("duplicate Device_IP_address " + config.device_ip);
            }

            bool has_bus = false;
            for (std::size_t bus = 0; bus < kBusCount; ++bus) {
                if (!config.enabled_buses[bus]) {
                    continue;
                }

                has_bus = true;
                const auto& iface = config.interface_names[bus];
                const auto owner = config.label() + " Bus" + std::to_string(bus);
                const auto [it, inserted] = interface_owners.emplace(iface, owner);
                if (!inserted) {
                    throw std::runtime_error(
                        "CAN interface collision on " + iface + " between " + it->second + " and " + owner
                    );
                }
            }

            if (!has_bus) {
                throw std::runtime_error("board has no enabled buses: " + config.label());
            }
        }

        udp_fd = ::socket(AF_INET, SOCK_DGRAM, 0);
        if (udp_fd < 0) {
            throw std::runtime_error("socket(AF_INET, SOCK_DGRAM) failed: " + std::string(std::strerror(errno)));
        }
        if (::fcntl(udp_fd, F_SETFL, O_NONBLOCK) < 0) {
            ::close(udp_fd);
            udp_fd = -1;
            throw std::runtime_error("fcntl(O_NONBLOCK) failed on UDP socket: " + std::string(std::strerror(errno)));
        }

        sockaddr_in local_addr {};
        local_addr.sin_family = AF_INET;
        local_addr.sin_port = htons(kServerPort);
        if (inet_pton(AF_INET, host_ip.c_str(), &local_addr.sin_addr) != 1) {
            ::close(udp_fd);
            udp_fd = -1;
            throw std::runtime_error("invalid Host_IP_address " + host_ip);
        }
        if (::bind(udp_fd, reinterpret_cast<const sockaddr*>(&local_addr), sizeof(local_addr)) < 0) {
            ::close(udp_fd);
            udp_fd = -1;
            throw std::runtime_error("bind(udp) failed: " + std::string(std::strerror(errno)));
        }

        epoll_fd = ::epoll_create1(0);
        if (epoll_fd < 0) {
            ::close(udp_fd);
            udp_fd = -1;
            throw std::runtime_error("epoll_create1 failed: " + std::string(std::strerror(errno)));
        }

        epoll_event udp_event {};
        udp_event.events = EPOLLIN;
        udp_event.data.fd = udp_fd;
        if (::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, udp_fd, &udp_event) < 0) {
            throw std::runtime_error("epoll_ctl(udp) failed: " + std::string(std::strerror(errno)));
        }
        bindings.emplace(udp_fd, Binding {.kind = Kind::Udp});

        boards.reserve(configs.size());
        for (auto& config : configs) {
            boards.push_back(std::make_unique<BoardSession>(std::move(config)));
        }

        for (const auto& board : boards) {
            boards_by_ip.emplace(board->config.device_ip, board.get());

            for (std::size_t bus = 0; bus < kBusCount; ++bus) {
                if (board->can_fds[bus] < 0) {
                    continue;
                }

                epoll_event can_event {};
                can_event.events = EPOLLIN;
                can_event.data.fd = board->can_fds[bus];
                if (::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, board->can_fds[bus], &can_event) < 0) {
                    throw std::runtime_error("epoll_ctl(can) failed: " + std::string(std::strerror(errno)));
                }

                bindings.emplace(
                    board->can_fds[bus],
                    Binding {
                        .kind = Kind::Can,
                        .board = board.get(),
                        .bus = bus,
                    }
                );

                std::cout << "Opened " << board->config.label() << " Bus" << bus << " on "
                          << board->config.interface_names[bus] << std::endl;
            }

            if (board->timer_fd >= 0) {
                epoll_event timer_event {};
                timer_event.events = EPOLLIN;
                timer_event.data.fd = board->timer_fd;
                if (::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, board->timer_fd, &timer_event) < 0) {
                    throw std::runtime_error("epoll_ctl(timerfd) failed: " + std::string(std::strerror(errno)));
                }

                bindings.emplace(
                    board->timer_fd,
                    Binding {
                        .kind = Kind::Timer,
                        .board = board.get(),
                    }
                );
            }
        }
    }

    ~HostBridgeApp() {
        if (epoll_fd >= 0) {
            ::close(epoll_fd);
        }
        if (udp_fd >= 0) {
            ::close(udp_fd);
        }
    }

    void initialize() {
        for (const auto& board : boards) {
            std::cout << "Sending startup config to " << board->config.label() << std::endl;
            board->send_startup_config(udp_fd);
        }
    }

    void run() {
        std::array<epoll_event, kMaxEvents> events {};
        std::array<std::uint8_t, kMaxUdpPacketSize> udp_buffer {};

        while (true) {
            const int event_count = ::epoll_wait(epoll_fd, events.data(), events.size(), -1);
            if (event_count < 0) {
                if (errno == EINTR) {
                    continue;
                }
                throw std::runtime_error("epoll_wait failed: " + std::string(std::strerror(errno)));
            }

            for (int i = 0; i < event_count; ++i) {
                if ((events[i].events & EPOLLIN) == 0) {
                    throw std::runtime_error("unsupported epoll event");
                }

                const auto binding_it = bindings.find(events[i].data.fd);
                if (binding_it == bindings.end()) {
                    throw std::runtime_error("event for unregistered fd");
                }

                const auto binding = binding_it->second;
                if (binding.kind == Kind::Udp) {
                    while (true) {
                        sockaddr_in peer {};
                        socklen_t peer_len = sizeof(peer);
                        const auto bytes = ::recvfrom(
                            udp_fd,
                            udp_buffer.data(),
                            udp_buffer.size(),
                            0,
                            reinterpret_cast<sockaddr*>(&peer),
                            &peer_len
                        );

                        if (bytes < 0) {
                            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                                break;
                            }
                            throw std::runtime_error("recvfrom failed: " + std::string(std::strerror(errno)));
                        }

                        char ip_buffer[INET_ADDRSTRLEN] = {};
                        if (::inet_ntop(AF_INET, &peer.sin_addr, ip_buffer, sizeof(ip_buffer)) == nullptr) {
                            throw std::runtime_error("inet_ntop failed: " + std::string(std::strerror(errno)));
                        }

                        const auto board_it = boards_by_ip.find(ip_buffer);
                        if (board_it == boards_by_ip.end()) {
                            throw std::runtime_error("UDP packet from unknown device " + std::string(ip_buffer));
                        }

                        board_it->second->on_udp_packet(udp_buffer.data(), static_cast<std::size_t>(bytes));
                    }
                }
                else if (binding.kind == Kind::Can) {
                    binding.board->on_can_readable(binding.bus, udp_fd);
                }
                else {
                    binding.board->on_timer(udp_fd);
                }
            }
        }
    }

  private:
    enum class Kind {
        Udp,
        Can,
        Timer,
    };

    struct Binding {
        Kind kind {};
        BoardSession* board = nullptr;
        std::size_t bus = 0;
    };

    int udp_fd = -1;
    int epoll_fd = -1;
    std::vector<std::unique_ptr<BoardSession>> boards;
    std::unordered_map<std::string, BoardSession*> boards_by_ip;
    std::unordered_map<int, Binding> bindings;
};

} // namespace

int main(int argc, char* argv[]) {
    try {
        std::string host_ip;
        std::vector<BoardConfig> configs;
        BoardConfig* current = nullptr;

        auto require_value = [&](int& index, std::string_view option) -> const char* {
            if (index + 1 >= argc) {
                throw std::runtime_error("missing value for " + std::string(option));
            }
            return argv[++index];
        };

        for (int i = 1; i < argc; ++i) {
            const std::string_view arg = argv[i];

            if (arg == "--help" || arg == "-h") {
                std::cout << "Usage: " << argv[0]
                          << " --host-ip IP --board NAME --device-ip IP --period NS --nominal KBIT --data KBIT "
                             "[--bus0 IFACE] ... [--bus5 IFACE] [--board NAME ...]"
                          << std::endl;
                return 0;
            }

            if (arg == "--host-ip") {
                if (!host_ip.empty()) {
                    throw std::runtime_error("duplicate --host-ip");
                }
                host_ip = require_value(i, arg);
                continue;
            }

            if (arg == "--board") {
                configs.emplace_back();
                current = &configs.back();
                current->name = require_value(i, arg);
                continue;
            }

            if (current == nullptr) {
                throw std::runtime_error("option before first --board: " + std::string(arg));
            }

            if (arg == "--device-ip") {
                if (!current->device_ip.empty()) {
                    throw std::runtime_error("duplicate --device-ip for board " + current->name);
                }
                current->device_ip = require_value(i, arg);
            }
            else if (arg == "--period") {
                if (current->has_period) {
                    throw std::runtime_error("duplicate --period for board " + current->name);
                }
                current->integration_period_ns = std::stoull(require_value(i, arg));
                current->has_period = true;
            }
            else if (arg == "--nominal") {
                if (current->has_nominal) {
                    throw std::runtime_error("duplicate --nominal for board " + current->name);
                }
                current->nominal_baud = static_cast<std::uint16_t>(std::stoul(require_value(i, arg)));
                current->has_nominal = true;
            }
            else if (arg == "--data") {
                if (current->has_data) {
                    throw std::runtime_error("duplicate --data for board " + current->name);
                }
                current->data_baud = static_cast<std::uint16_t>(std::stoul(require_value(i, arg)));
                current->has_data = true;
            }
            else if (
                arg == "--bus0" ||
                arg == "--bus1" ||
                arg == "--bus2" ||
                arg == "--bus3" ||
                arg == "--bus4" ||
                arg == "--bus5"
            ) {
                const std::size_t bus = static_cast<std::size_t>(arg[5] - '0');
                if (current->enabled_buses[bus]) {
                    throw std::runtime_error("duplicate " + std::string(arg) + " for board " + current->name);
                }
                current->enabled_buses[bus] = true;
                current->interface_names[bus] = require_value(i, arg);
            }
            else {
                throw std::runtime_error("unknown argument: " + std::string(arg));
            }
        }

        if (host_ip.empty()) {
            throw std::runtime_error("missing --host-ip");
        }
        if (configs.empty()) {
            throw std::runtime_error("no boards provided");
        }

        for (const auto& config : configs) {
            if (config.name.empty()) {
                throw std::runtime_error("board without name");
            }
            if (config.device_ip.empty()) {
                throw std::runtime_error("board missing --device-ip: " + config.name);
            }
            if (!config.has_period) {
                throw std::runtime_error("board missing --period: " + config.name);
            }
            if (!config.has_nominal) {
                throw std::runtime_error("board missing --nominal: " + config.name);
            }
            if (!config.has_data) {
                throw std::runtime_error("board missing --data: " + config.name);
            }
        }

        HostBridgeApp app(std::move(host_ip), std::move(configs));
        app.initialize();
        app.run();
    }
    catch (const std::exception& e) {
        std::cerr << "host process fatal error: " << e.what() << std::endl;
        return 1;
    }
}
