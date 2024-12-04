from typing import Optional, List, Tuple, TypedDict
from ipaddress import IPv4Address
from selenium import webdriver
import re
import requests
from bs4 import BeautifulSoup
from cpe_manager.models.base import CPE_HTTP_Controller, Wireless_Client, logged_in, DHCP_Client, Return_Codes

class Controller(CPE_HTTP_Controller):
    """ Ha sido probado con: XPON+2GE+2WIFI; Hardware: V4.1; Firmware: V2.1.06-230711 """

    # ------------ URLs ----------------
    LOGIN_PROCESS_INIT_URL = "http://{cpe_address}/admin/login.asp"
    LOGIN_URL = "http://{cpe_address}/boaform/admin/formLogin"
    LOGOUT_URL = "http://{cpe_address}/boaform/admin/formLogout"
    ADMIN_PASSWORD_CHANGE_URL = "http://{cpe_address}/boaform/admin/formPasswordSetup"
    GET_DHCP_CLIENTS_URL = "http://{cpe_address}/status_ethernet_info.asp"
    CHANGE_WIFI_SSID_URL = "http://{cpe_address}/boaform/admin/formWlanSetup"
    CHANGE_WIFI_PASSWORD_URL = "http://{cpe_address}/boaform/admin/formWlEncrypt"
    #-----------------------------------

    # --------- Return Codes -----------
    LOGIN_SUCCESS_CODE = 302
    LOGOUT_SUCCESS_CODE = 301
    #-----------------------------------

    # --------- Other
    VERIFICATION_CODE_REGEX_PATTERN = r"document\.getElementById\('check_code'\)\.value='(.*?)';"
    
    WIFI2GHZ_IDX = 1
    WIFI5GHZ_IDX = 0

    def _get_csrf_token(self) -> Optional[str]:
            token_call = requests.get(f"http://{self.CPE_ADDRESS}/mgm_usr_user.asp")
            token_soup = BeautifulSoup(token_call.text, "html.parser")
            csfrtoken = token_soup.find('input', {'name': 'csrftoken'}).get('value') # type: ignore
            return csfrtoken

    def login(self) -> None:
        # Este requiere de leer el CSRF y el codigo de validacion del documento login.asp previo a iniciar ese proceso
        # El token CSRF esta en un input, pero el codigo esta en una funcion de JS por eso hay que leerlo utilizando regex
        # no parece guardar cookies, al igual que la ACZ la sesion la mantiene por IP
        try: 
            login_init = requests.get(self.LOGIN_PROCESS_INIT_URL.format(
                cpe_address = self.CPE_ADDRESS
            ))
            if login_init.status_code == 200 and login_init.text:
                login_soup = BeautifulSoup(login_init.text, "html.parser")
                self.CSRF_TOKEN = login_soup.find('input', {'name': 'csrftoken'}).get('value') # type: ignore
                match = re.search(self.VERIFICATION_CODE_REGEX_PATTERN, login_init.text)
                if match:
                    verification_code = match.group(1)
                else:
                    verification_code = ""

                # No se porque pide el usuario y la clave 2 veces en el mismo form
                login = requests.post(self.LOGIN_URL.format(cpe_address=self.CPE_ADDRESS),
                                      data = {
                                          "username1": self.USERNAME,
                                          "psd1": self.PASSWORD,
                                          "verification_code": verification_code,
                                          "username": self.USERNAME,
                                          "psd": self.PASSWORD,
                                          "sec_lang": "0",
                                          "loginSelinit": "0",
                                          "ismobile": "",
                                          "csrftoken": self.CSRF_TOKEN
                                      }, allow_redirects=False)
                
                if (login.status_code == self.LOGIN_SUCCESS_CODE):
                    self.Loged_In = True
                    return(Return_Codes.SUCCESS,)
                else:
                    return(Return_Codes.ERROR, f"cpe: {self.CPE_ADDRESS} - msg: {login.text}")
            else:
                return(Return_Codes.ERROR, f"cpe: {self.CPE_ADDRESS} - msg: {login_init.status_code}")

        except Exception as e:
            return(Return_Codes.EXCEPTION, f"cpe: {self.CPE_ADDRESS} - msg: {e}")

    def logout(self) -> Tuple[int, Optional[str]]:
        try:
            logout = requests.get(self.LOGOUT_URL.format(cpe_address = self.CPE_ADDRESS), allow_redirects=False)
            if (logout.status_code == self.LOGOUT_SUCCESS_CODE):
                self.Loged_In = False
                return (Return_Codes.SUCCESS,)
            else: 
                return(Return_Codes.ERROR, f"logout error - cpe: {self.CPE_ADDRESS} - msg: {logout.status_code}")
        except Exception as e:
            return(Return_Codes.EXCEPTION, f"cpe: {self.CPE_ADDRESS} - msg: {e}")

    @logged_in
    def change_admin_password(self, new_password: str)  -> Tuple[int, Optional[str]]:
        """ Cambia la clave de admin del equipo """
        
        # el token csrf hay que pedirlo previo a cada solicitud o esto es lo que parece por los logs, siempre esta cambiando
        try:
            csrftoken = self._get_csrf_token()
            password_change = requests.post(self.ADMIN_PASSWORD_CHANGE_URL.format(cpe_address = self.CPE_ADDRESS),
                                 data = {
                                     "UserIdx": "0",
                                     "oldPasswd": self.PASSWORD,
                                     "newPasswd": new_password, 
                                     "affirmPasswd": new_password,
                                     "submit-url": f"http://{self.CPE_ADDRESS}/mgm_usr_user.asp",
                                     "csrftoken": csrftoken
                                 }, allow_redirects=False)
            if password_change.status_code == 302:
                return (Return_Codes.SUCCESS,)
            else:
                return(Return_Codes.ERROR, f"No se logro cambiar la contraseña del CPE: {self.CPE_ADDRESS}, codigo http: {password_change.status_code}, respuesta: {password_change.text}")

        except Exception as e:
            return (Return_Codes.EXCEPTION, e)

    @logged_in
    def get_dhcp_clients(self) -> Optional[List[DHCP_Client]]:
        # Esta es una pagina dinamica y estoy utilizando Selenium para esto, pero para scripts es MUY lento
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        clients_list = []

        driver = webdriver.Chrome(options = options)
        driver.get(self.GET_DHCP_CLIENTS_URL.format(cpe_address = self.CPE_ADDRESS))
        response_soup = BeautifulSoup(driver.page_source, "html.parser")
        table = response_soup.find('table', {'id': 'lstdev'})
        if table:
            tbody = table.find("tbody")
            if tbody:
                rows = tbody.find_all('tr') # type: ignore
                for row in rows:
                    cols = row.find_all('td')
                    cols = [ ele.text.strip() for ele in cols ]
                    if cols:
                        clients_list.append({
                                    "device_name": cols[0],
                                    "device_ip": cols[2],
                                    "device_mac": cols[1],
                                    "lease_time": int(cols[3])
                                })
        return clients_list
    
    @logged_in
    def get_wifi_clients(self) -> Optional[List[Wireless_Client]]:
        client_list = []

        wifi_clients = requests.get(f"http://{self.CPE_ADDRESS}/status_wlan_info_11n.asp")
        if wifi_clients.status_code != 200:
            print(f"Hubo un error con la peticion al CPE {self.CPE_ADDRESS}, codigo: {wifi_clients.status_code}, response: {wifi_clients.text}")
            return
        clients_soup = BeautifulSoup(wifi_clients.text, 'html.parser')

            # La tabla donde estan los clientes no viene con ningun ID que claramente la identifique, es necesario revisar el <p> y <div> previos para rastrearla...
        intro_title = clients_soup.find('p', class_='intro_title', text='Associated Clients')
        table = intro_title.find_next('div', class_='data_common').find('table')
            
        if table:
            rows = table.find_all('tr')[1:]  # type: ignore # Skip the header row
            for row in rows:
                cols = row.find_all('td')
                cols = [ele.get_text(strip=True) for ele in cols]
                if cols:
                    client_list.append({
                            "device_mac": cols[0],
                            "packets_sent": cols[1],
                            "packets_received": cols[2],
                            "send_rate_mbps": cols[3],
                            "rssi_dbm": cols[4],
                            "power_saving": cols[5],
                         #   "Expired Time (sec)": cols[6]
                        })

        return client_list
    
    @logged_in
    def change_wifi_ssid(self, new_ssid)  -> Tuple[int, Optional[str]]:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "ssid": new_ssid,
            "wlan_idx": "",
            "csrftoken": ""
        }
        try:
            payload["csrftoken"] = self._get_csrf_token()
            payload["wlan_idx"] = self.WIFI2GHZ_IDX
            ssid_change_2ghz = requests.post(self.CHANGE_WIFI_SSID_URL.format(cpe_address = self.CPE_ADDRESS),
                                    data = payload, allow_redirects=False,
                                    headers = headers)
            
            payload["csrftoken"] = self._get_csrf_token()
            payload["wlan_idx"] = self.WIFI5GHZ_IDX
            ssid_change_5ghz = requests.post(self.CHANGE_WIFI_SSID_URL.format(cpe_address = self.CPE_ADDRESS),
                                    data = payload, allow_redirects=False,
                                    headers = headers)
            
            if ssid_change_2ghz.status_code == 200 and ssid_change_5ghz.status_code == 200:
                ssid_change_2ghz_soup = BeautifulSoup(ssid_change_2ghz.text, 'html.parser')
                ssid_change_5ghz_soup = BeautifulSoup(ssid_change_5ghz.text, 'html.parser')
                change_2ghz_result = ssid_change_2ghz_soup.find('h4').text
                change_5ghz_result = ssid_change_5ghz_soup.find('h4').text

                if change_2ghz_result == change_5ghz_result == 'Change setting successfully!':
                    return (Return_Codes.SUCCESS,)
            
            return (Return_Codes.ERROR, f"2ghz: {ssid_change_2ghz.status_code} - 5ghz: {ssid_change_5ghz.status_code}")
        except Exception as e:
            return (Return_Codes.EXCEPTION, e)

    @logged_in
    def change_wifi_password(self, new_password)  -> Tuple[int, Optional[str]]:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload =  {
                    "wpaSSID": "0",
                    "security_method": "6",
                    "wpaAuth": "psk",
                    "pskFormat": 0,
                    "pskValue": new_password,
                    "wlan_idx": "",
                    "csrftoken": "",
                    "save": "Apply Changes",
                    "dotIEEE80211W": "0"
                    }
        try:
            payload["csrftoken"] = self._get_csrf_token()
            payload["wlan_idx"] = self.WIFI2GHZ_IDX
            password_change_2ghz = requests.post(self.CHANGE_WIFI_PASSWORD_URL.format(cpe_address = self.CPE_ADDRESS),
                                    data = payload, allow_redirects=False,
                                    headers = headers)
            
            payload["csrftoken"] = self._get_csrf_token()
            payload["wlan_idx"] = self.WIFI5GHZ_IDX
            password_change_5ghz = requests.post(self.CHANGE_WIFI_PASSWORD_URL.format(cpe_address = self.CPE_ADDRESS),
                                    data = payload, allow_redirects=False,
                                    headers = headers)
            
            if password_change_2ghz.status_code == 200 and password_change_5ghz.status_code == 200:
                password_change_2ghz_soup = BeautifulSoup(password_change_2ghz.text, 'html.parser')
                password_change_5ghz_soup = BeautifulSoup(password_change_5ghz.text, 'html.parser')
                change_2ghz_result = password_change_2ghz_soup.find('h4').text
                change_5ghz_result = password_change_5ghz_soup.find('h4').text

                if change_2ghz_result == change_5ghz_result == 'Change setting successfully!':
                    return (Return_Codes.SUCCESS,)
            
            return (Return_Codes.ERROR, f"2ghz: {password_change_2ghz.status_code} - 5ghz: {password_change_5ghz.status_code}")
        
        except Exception as e:
            return (Return_Codes.EXCEPTION, e)
