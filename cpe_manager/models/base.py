from enum import Enum
from typing import Optional, List, TypedDict
from ipaddress import IPv4Address
from abc import ABC, abstractmethod
import requests

class Return_Codes(Enum):
    SUCCESS = 0
    ERROR = -1
    EXCEPTION = -2

class Wireless_Client(TypedDict):
    device_mac: str
    rssi_dbm: str 
    power_saving: Optional[str]
    send_rate_mbps: Optional[int]
    packets_send: Optional[int]
    packets_received: Optional[int]

class DHCP_Client(TypedDict):
    device_name: str
    device_ip: str
    device_mac: str
    lease_time: Optional[int]

def logged_in(func):
    """ Decorador para no tener que escribir la validacion de login por cada funcion """
    def decorated(self, *args, **kargs):
        if not self.Loged_In:
            return -1
        return func(self, *args, **kargs)
    return decorated

class CPE_HTTP_Controller:
    """ Definicion base de funcionalidad para que sea consistente en todas las implementaciones"""
    CPE_ADDRESS = None
    LOGIN_SESSION = None
    USERNAME = None
    PASSWORD = None
    Loged_In = False

    def __init__(self, cpe_address, username, password):
        self.CPE_ADDRESS = cpe_address
        self.LOGIN_SESSION = requests.session()
        self.USERNAME = username
        self.PASSWORD = password

    def login(self) -> None:
        raise NotImplementedError
    
    def logout(self) -> None:
        raise NotImplementedError

    def change_admin_password(self, new_password: str):
        raise NotImplementedError

    def get_dhcp_clients(self) -> Optional[List[DHCP_Client]]:
        raise NotImplementedError
    
    def get_wifi_clients(self) -> Optional[List[Wireless_Client]]:
        raise NotImplementedError
    
    def change_wifi_ssid(self, new_ssid: str) -> None:
        raise NotImplementedError
    
    def change_wifi_password(self, new_password: str) -> None:
        raise NotImplementedError