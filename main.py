import socket
import re
import xml.etree.ElementTree as ET
import http.client
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def open_upnp_port(port_number: int) -> bool:
    """
    Send a UPnP request to open a specific port on the router.

    Args:
        port_number (int): The port number to open.

    Returns:
        bool: True if the port was successfully opened, False otherwise.
    """
    logging.info(f"Attempting to open UPnP port {port_number}")

    try:
        # UPnP discovery
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(3)

        msg = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST:239.255.255.250:1900\r\n"
            "ST:upnp:rootdevice\r\n"
            "MX:2\r\n"
            'MAN:"ssdp:discover"\r\n'
            "\r\n"
        )

        sock.sendto(msg.encode(), ("239.255.255.250", 1900))
        logging.info("Sent UPnP discovery message")

        while True:
            try:
                data, addr = sock.recvfrom(8192)
                if "LOCATION" in data.decode():
                    location = re.search(r"LOCATION: (.*)\r\n", data.decode()).group(1)
                    logging.info(f"Found UPnP device at {location}")
                    break
            except socket.timeout:
                logging.error("UPnP discovery timed out")
                return False

        # Get control URL
        conn = http.client.HTTPConnection(location.split("/")[2])
        conn.request("GET", "/" + "/".join(location.split("/")[3:]))
        response = conn.getresponse()
        data = response.read()

        root = ET.fromstring(data)
        ns = {"ns": "urn:schemas-upnp-org:device-1-0"}
        for service in root.findall(".//ns:service", ns):
            if service.find("ns:serviceType", ns).text.endswith("WANIPConnection"):
                control_url = service.find("ns:controlURL", ns).text
                break
        else:
            logging.error("Could not find WANIPConnection service")
            return False

        logging.info(f"Found control URL: {control_url}")

        # Send port mapping request
        conn = http.client.HTTPConnection(location.split("/")[2])
        soap_body = f"""<?xml version="1.0"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
            <s:Body>
                <u:AddPortMapping xmlns:u="urn:schemas-upnp-org:service:WANIPConnection:1">
                    <NewRemoteHost></NewRemoteHost>
                    <NewExternalPort>{port_number}</NewExternalPort>
                    <NewProtocol>TCP</NewProtocol>
                    <NewInternalPort>{port_number}</NewInternalPort>
                    <NewInternalClient>{socket.gethostbyname(socket.gethostname())}</NewInternalClient>
                    <NewEnabled>1</NewEnabled>
                    <NewPortMappingDescription>UPnP Port Mapping</NewPortMappingDescription>
                    <NewLeaseDuration>0</NewLeaseDuration>
                </u:AddPortMapping>
            </s:Body>
        </s:Envelope>"""

        headers = {
            "SOAPAction": '"urn:schemas-upnp-org:service:WANIPConnection:1#AddPortMapping"',
            "Content-Type": 'text/xml; charset="utf-8"',
            "Connection": "close",
        }

        conn.request("POST", control_url, soap_body, headers)
        response = conn.getresponse()

        if response.status == 200:
            logging.info(f"Successfully opened UPnP port {port_number}")
            return True
        else:
            logging.error(
                f"Failed to open UPnP port {port_number}. Status: {response.status}"
            )
            return False

    except Exception as e:
        logging.error(f"Error in UPnP port opening: {str(e)}")
        return False


def open_nat_port(port_number: int) -> bool:
    """
    Attempt to open a specific port on the local network.

    Args:
        port_number (int): The port number to open.

    Returns:
        bool: True if the port was successfully opened, False otherwise.
    """
    logging.info(f"Attempting to open local port {port_number}")

    try:
        # Create a socket and bind it to the specified port
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", port_number))

        # Get the local IP address
        local_ip = socket.gethostbyname(socket.gethostname())

        logging.info(f"Bound to local address: {local_ip}:{port_number}")

        # Try to make the port accessible
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Send a broadcast packet
        broadcast_addr = "<broadcast>"
        message = b"Port opening test"
        sock.sendto(message, (broadcast_addr, port_number))

        logging.info(f"Sent broadcast packet from {local_ip}:{port_number}")

        # Keep the socket open briefly
        sock.settimeout(5)
        try:
            data, addr = sock.recvfrom(1024)
            logging.info(f"Received response from {addr}: {data}")
        except socket.timeout:
            logging.info("No response received (expected)")

        logging.info(f"Successfully opened local port {port_number}")
        return True

    except Exception as e:
        logging.error(f"Error in local port opening: {str(e)}")
        return False


if __name__ == "__main__":
    # upnp_result = open_upnp_port(1234)
    # print(f"UPnP port opening result: {'Success' if upnp_result else 'Failure'}")

    nat_result = open_nat_port(1235)
    print(f"NAT port opening result: {'Success' if nat_result else 'Failure'}")
