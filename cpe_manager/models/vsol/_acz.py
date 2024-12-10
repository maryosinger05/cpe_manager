from typing import Optional, List, TypedDict
from ipaddress import IPv4Address
from selenium import webdriver
import re
import requests
from bs4 import BeautifulSoup
from cpe_manager.models.base import CPE_HTTP_Controller, Wireless_Client, logged_in, DHCP_Client

class VSOL_ACZ(CPE_HTTP_Controller):
    """ Ha sido probado con V624, hardare V1.0, firmware VSOL-V2.1.0B04-220608"""
    # ------------ URLs ----------------
    LOGIN_URL = "http://{cpe_address}/boaform/admin/formLogin"
    LOGOUT_URL = "http://{cpe_address}/boaform/admin/formLogout"
    LOGIN_SUCCESS_CODE = 302
    LOGOUT_SUCCESS_CODE = 301
    CSRF_REQUEST_URL = "http://{cpe_address}/boaform/getASPdata/FMask"
    PASSWORD_CHANGE_URL = "http://{cpe_address}/boaform/getASPdata/new_formPasswordSetup"
    GET_DHCP_CLIENTS_URL = 'http://{cpe_address}/boaform/getASPdata/E8BDhcpClientList' 

    def login(self) -> None:
        # En la version que se probo no se mantiene la sesion mediante cookies, sino mediante una IP... no es necesario generar una sesion con requests
        try:
            login = requests.post(self.LOGIN_URL.format(cpe_address = self.CPE_ADDRESS), 
                                  data = {"username": self.USERNAME,
                                           "psd": self.PASSWORD}, 
                                           allow_redirects=False)
            if (login.status_code == self.LOGIN_SUCCESS_CODE):
                print(f"Conectado exitosamente a {self.CPE_ADDRESS}")
                self.Loged_In = True
            else:
                print(f"No se logro conectar a {self.CPE_ADDRESS}, respuesta = {login.text}")
        except Exception as e:
            print(f"Hubo un problema con la conexion ha {self.CPE_ADDRESS}")
            print(f"stack trace: {e}")

    @logged_in
    def logout(self) -> None:
        try:
            logout = requests.get(self.LOGOUT_URL.format(cpe_address = self.CPE_ADDRESS), allow_redirects=False)
            if (logout.status_code == self.LOGOUT_SUCCESS_CODE):
                print(f"Desconexion exitosa del CPE: {self.CPE_ADDRESS}")
                self.Loged_In = False
            else: 
                print(f"Hubo un problema tratando de realizar la desconexion del CPE {self.CPE_ADDRESS}, respuesta = {logout.text}")
        except Exception as e:
                print(f"Hubo un problema con logout del CPE: {self.CPE_ADDRESS}")
                print(f"stack trace: {e}") 

    @logged_in
    def change_admin_password(self, new_password: str) -> None:
        """ Cambia la clave de admin del equipo """
        
        # el token csrf hay que pedirlo previo a cada solicitud o esto es lo que parece por los logs, siempre esta cambiando
        try:
            csrfMask = requests.get(self.CSRF_REQUEST_URL.format(cpe_address = self.CPE_ADDRESS))
            password_change = requests.post(self.PASSWORD_CHANGE_URL.format(cpe_address = self.CPE_ADDRESS),
                                 data = {
                                     "UserName": self.USERNAME,
                                     "oldPasswd": self.PASSWORD,
                                     "newPasswd": new_password, 
                                     "affirmPasswd": new_password, 
                                     "csrfMask": csrfMask
                                 })
            if (password_change.status_code == 200 and "success" in password_change.text):
                print(f"Contraseña cambiada correctamente para el CPE {self.CPE_ADDRESS}")
            else:
                print(f"No se logro cambiar la contraseña del CPE: {self.CPE_ADDRESS}, codigo http: {password_change.status_code}, respuesta: {password_change.text}")
        except Exception as e:
            print(f"Hubo un problema intentando cambiar la clave del CPE: {self.CPE_ADDRESS}")
            print(f"stack trace: {e}")

    @logged_in
    def get_dhcp_clients(self) -> Optional[List[DHCP_Client]]:
        """ Devuelve la lista de clientes DHCP activos, este CPE tiene una llamada que entrega esa lista"""
        try: 
            client_list = requests.get(self.GET_DHCP_CLIENTS_URL.format(cpe_address = self.CPE_ADDRESS))
            client_list = client_list.text.split('\n')
            if not client_list:
                return []
            parsed_client_list = []
        except Exception as e:
            print(f"Hubo un problema tratando de obtener la lista DHCP del cpe: {self.CPE_ADDRESS}")
            return
        
        # El ultimo aqui siempre esta vacio
        for client in client_list[:-1]:
            start_index = client.find('(') + 1
            end_index = client.find(')')
            client = client[start_index:end_index]
            # Remove the leading and trailing slashes
            client = client.strip('/')
            pairs = client.split('/')
            parsed_client = {}

            for pair in pairs:
                key, value = pair.split('=')
                parsed_client[key] = value
            
            parsed_client_list.append(parsed_client)

        return parsed_client_list
