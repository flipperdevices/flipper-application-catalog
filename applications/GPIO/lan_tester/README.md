# Flipper Zero LAN Tester (W5500)

[github](https://github.com/dok2d/fz-W5500-lan-analyse)

Turn your **Flipper Zero + W5500 Lite** module into a professional-grade portable LAN tester. Analyze Ethernet links, discover network neighbors, scan subnets, fingerprint DHCP servers --- all from a pocket-sized device.

---

## Features

| Feature | Description |
|---|---|
| **Link Info** | PHY link status, speed (10/100 Mbps), duplex (Half/Full), MAC address, W5500 version check |
| **DHCP Analyzer** | Discover-only analysis (no IP lease taken), option fingerprinting, full offer parsing |
| **ARP Scanner** | Active subnet scan with batch requests, OUI vendor lookup (~120 vendors), duplicate detection |
| **Ping** | Echo request/reply to any IP with configurable count and timeout |
| **Continuous Ping** | Real-time RTT graph with min/max/avg and packet loss, configurable interval |
| **DNS Lookup** | Resolve hostnames via UDP DNS, supports custom DNS server |
| **Traceroute** | ICMP-based hop-by-hop path discovery, accepts IPs and hostnames with DNS resolve |
| **Ping Sweep** | ICMP sweep of an entire subnet with interactive host list — click to ping, scan, or WOL |
| **Port Scanner** | TCP connect scan: Top-20, Top-100 presets, or custom port range (1-65535) |
| **LLDP/CDP** | Passive IEEE 802.1AB & Cisco CDP neighbor discovery with full TLV parsing |
| **mDNS/SSDP** | Discover services and devices via multicast DNS and UPnP/SSDP |
| **STP/VLAN** | Passive BPDU listener + 802.1Q VLAN tag detection |
| **Statistics** | Frame counters by type (unicast/broadcast/multicast) and EtherType |
| **Wake-on-LAN** | Send magic packets to any MAC address |
| **Packet Capture** | Standalone PCAP traffic dump — capture raw Ethernet frames to .pcap file on SD card |
| **ETH Bridge** | USB-to-Ethernet bridge: phone/PC gets LAN access via Flipper (CDC-ECM), optional PCAP traffic dump to SD card |
| **PXE Server** | Minimal PXE boot server with built-in DHCP + TFTP, boots .kpxe/.efi files from SD card |
| **File Manager** | Web-based file manager: browse, download, upload, delete files on microSD via HTTP from any browser on the LAN |
| **History** | All scan results auto-saved with timestamps, browsable and deletable |
| **Settings** | Auto-save, sound/vibro, custom DNS server, ping count/timeout/interval, clear history, MAC Changer |

### UX Highlights

- **Hierarchical menu**: features grouped into Network Info, Discovery, Diagnostics, Tools
- **Link status in header**: see UP/DOWN, speed, duplex without entering Link Info
- **DHCP caching**: single negotiation shared across all operations — no repeated 15s waits
- **Visual progress**: countdown timers for listeners, ASCII progress bars for scans
- **LED/vibro feedback**: green blink on success, red on error (optional, toggle in Settings)
- **Smart defaults**: IP inputs pre-populated with DHCP gateway

## Hardware

### Required

- **Flipper Zero** (OFW firmware)
- **W5500 Lite** Ethernet module (or any W5500-based board with SPI)

### Wiring

```
W5500 Module    Flipper Zero GPIO
─────────────   ─────────────────
MOSI (MO)   →   A7  (pin 2)
SCLK (SCK)  →   B3  (pin 5)
CS   (nSS)  →   A4  (pin 4)
MISO (MI)   →   A6  (pin 3)
RESET (RST) →   C3  (pin 7)
3V3  (VCC)  →   3V3 (pin 9)
GND  (G)    →   GND (pin 8 or 11)
```

> The W5500 is powered via Flipper's OTG 3.3V output, which is enabled automatically when the app starts.

## Usage

1. Connect the W5500 module to Flipper Zero using the wiring diagram above
2. Plug an Ethernet cable into the W5500's RJ45 port
3. Open **GPIO → LAN Tester** on the Flipper
4. The menu header shows link status (e.g. `LAN [UP 100M FD]`)
5. Select a category and then a tool:

### Network Info
- **Link Info** — link status, speed, duplex, MAC. Use first to verify hardware.
- **DHCP Analyze** — sends Discover, parses Offer. Does **not** take an IP lease.
- **Statistics** — captures frames for 10s, shows breakdown by type and EtherType.

### Discovery
- **ARP Scan** — scans local subnet via DHCP-detected range, shows IP/MAC/vendor.
- **Ping Sweep** — ICMP sweep of a CIDR range, auto-detected or manually entered.
- **LLDP/CDP** — listens up to 60s for switch neighbor advertisements.
- **mDNS/SSDP** — discovers services via multicast DNS and UPnP.
- **STP/VLAN** — listens 30s for BPDU frames and 802.1Q VLAN tags.

### Diagnostics
- **Ping** — 4 pings to any IP (default: gateway from DHCP).
- **Continuous Ping** — live RTT graph with loss tracking, runs until Back.
- **DNS Lookup** — resolves a hostname via the DHCP-provided DNS server.
- **Traceroute** — hop-by-hop ICMP path discovery up to 30 hops.
- **Port Scan (Top 20/100)** — TCP connect scan of common ports.

### Tools
- **Wake-on-LAN** — send magic packet to wake a device by MAC address.
- **ETH Bridge** — turns Flipper into a USB-to-Ethernet bridge. Phone/PC connects via USB (CDC-ECM), traffic is bridged to LAN via W5500 at Layer 2. The host gets an IP from the LAN's DHCP server transparently. Live stats show frame counts and link status. Press **OK** to start/stop PCAP traffic recording to SD card (Wireshark-compatible `.pcap` files saved to `apps_data/lan_tester/pcap/`). Press Back to stop and restore USB.
- **PXE Server** — minimal PXE boot server. Configure Server/Client IP and subnet, toggle built-in DHCP server. Serves .kpxe/.efi boot files from SD card (`apps_data/lan_tester/pxe/`) via TFTP. Connect Flipper directly to target machine to network-boot it.
- **File Manager** — starts an HTTP server on port 80. Open `http://<flipper-ip>/` in any browser on the LAN to browse the microSD card, download/upload files, create folders, and delete items. Flipper gets its IP via DHCP; the address is displayed on screen.

### Settings
- **Auto-save results** — ON/OFF, controls automatic history saving.
- **Sound & vibro** — ON/OFF, controls LED/vibro notifications.
- **Clear History** — delete all saved result files.
- **MAC Changer** — generate random MAC or enter custom, saved to SD.

## Technical Details

- **W5500 MACRAW mode**: Socket 0 with `MFEN=0` (promiscuous --- receives all frames including multicast)
- **Worker thread**: 8 KB stack, non-blocking UI via ViewDispatcher + worker pattern
- **DHCP caching**: single negotiation, result reused across all subsequent operations
- **Memory-safe**: large buffers heap-allocated, frame buffer on heap (4 KB app stack), bounds checking on all parsers
- **Endianness**: manual big-endian parsing --- no float printf, no `htons`/`ntohs`

## OUI Vendor Database

The built-in lookup table covers ~120 common OUI prefixes including:

> Cisco, HP/HPE, Dell, Intel, Broadcom, Realtek, Apple, Samsung, Huawei, TP-Link, Ubiquiti, Juniper, Arista, MikroTik, Netgear, ASUS, D-Link, Synology, QNAP, VMware, Microsoft, Google, Amazon, Lenovo, Supermicro, Aruba, Fortinet, Palo Alto, WIZnet, Raspberry Pi, Espressif, and more.

## Credits

- Based on [arag0re/fz-eth-troubleshooter](https://github.com/arag0re/fz-eth-troubleshooter) (fork of [karasevia/finik_eth](https://github.com/karasevia/finik_eth))
- Uses [WIZnet ioLibrary_Driver](https://github.com/Wiznet/ioLibrary_Driver) for W5500 hardware abstraction
- Built for [Flipper Zero OFW](https://github.com/flipperdevices/flipperzero-firmware)

## License

MIT License. See [LICENSE](LICENSE) for details.

