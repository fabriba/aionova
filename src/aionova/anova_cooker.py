import aiohttp
import datetime
from typing import Optional, Union 

LEGACY_API_URL = 'https://api.anovaculinary.com/cookers/{cooker_id}{action}?secret={secret}'
STATE_URL = 'https://anovaculinary.io/devices/{cooker_id}/states/?limit=1&max-age=10s'  #GET

ANOVA_FIREBASE_KEY = 'AIzaSyDQiOP2fTR9zvFcag2kSbcmG9zPh6gZhHw'
AUTH_URL1 = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={ANOVA_FIREBASE_KEY}" #POST json= {'email': ,'password': ,'returnSecureToken': True }
AUTH_URL2 = 'https://anovaculinary.io/authenticate' #POST json = {}, headers = { 'firebase-token':  }

SAVE_URL = "https://anovaculinary.io/devices/{cooker_id}/current-job" #PUT headers= { 'authorization': f"Bearer {jwt}" }
					# json = { 'cook-time-seconds': int ,'id': '22chars_unique',  'mode': 'COOK'/'IDLE', 'ota-url': '', 'target-temperature': int, 'temperature-unit': 'C'/'F'

class AnovaCooker:
	def __init__(self, cooker_id: str, user_id: str, user_pw: str ):
		self.cooker_id = cooker_id
		self._user_id = user_id
		self._user_pw = user_pw
		self.raw_state = dict()
		self.state = None
		#TODO: enable readonly mode if user_id / user_pw not provided / auth incorrect

	async def _get_raw_state(self):
		"""Get raw device state from the Anova API. This does not require authentication."""
		async with aiohttp.ClientSession() as session:
			device_state_request = session.get('https://anovaculinary.io/devices/{}/states/?limit=1&max-age=10s'.format(self.cooker_id))
		if device_state_request.status_code != 200:
			raise Exception('Error connecting to Anova')

		device_state_body = device_state_request.json()
		if len(device_state_body) == 0:
			raise Exception('Invalid device ID')

		return device_state_body

	async def update_state(self) -> dict:
		state = await self._get_raw_state()

			# [{
			# 'body': {
			#     'boot-id': '12345678901234',
			#     'job': {'cook-time-seconds': 36000,
			#             'id': '12345678901234',
			#             'mode': 'COOK' / 'IDLE',
			#             'ota-url': '',
			#             'target-temperature': 65,
			#             'temperature-unit': 'C'},
			#     'job-status': {'cook-time-remaining': 14417,
			#                     'job-start-systick': 1553,
			#                     'provisioning-pairing-code': 0,
			#                     'state': 'COOKING',
			#                     'state-change-systick': 1553},
			#     'network-info': {'bssid': 'xxxxxxxxxx',
			#                     'connection-status': 'connected-station',
			#                     'is-provisioning': False,
			#                     'mac-address': 'xxxxxxx',
			#                     'mode': 'station',
			#                     'security-type': 'WPA2',
			#                     'ssid': 'xxxxxxxxxx'},
			#     'pin-info': {'device-safe': 0,
			#                 'water-leak': 0,
			#                 'water-level-critical': 0,
			#                 'water-temp-too-high': 0},
			#     'system-info-3220': {'firmware-version': '1.4.4',
			#                         'firmware-version-raw': 'VM176_A_01.04.04',
			#                         'largest-free-heap-size': 28008,
			#                         'stack-low-level': 180,
			#                         'stack-low-task': 7,
			#                         'systick': 9443103,
			#                         'total-free-heap-size': 28784},
			#     'system-info-nxp': {'version-string': 'VM171_A_01.04.04'},
			#     'temperature-info': {'heater-temperature': 65.09,
			#                         'triac-temperature': 51.48,
			#                         'water-temperature': 64.99}},
			# 'header': {'created-at': '2021-03-01T16:29:14.656075Z',
			#         'e-tag': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
			#         'entity-id': '123456789012345'}}]

		self.state = state
		return state

	@property
	def _jwt(self) -> Optional[str]:
		"""Authenticate with Anova via Google Firebase."""
		if hasattr(self, '_j_w_t'):
			return  self._anovaculinary_jwt     
		
		ANOVA_FIREBASE_KEY = 'AIzaSyDQiOP2fTR9zvFcag2kSbcmG9zPh6gZhHw'

		# First authenticate with Firebase and get the ID token
		firebase_req_data = {
			'email': self._user_id,
			'password': self._user_pw,
			'returnSecureToken': True
		}

		firebase_req = requests.post('https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={}'.format(ANOVA_FIREBASE_KEY), json = firebase_req_data)
		firebase_id_token = firebase_req.json().get('idToken')

		if not firebase_id_token:
			raise Exception('Could not log in with Google Firebase')

		# Now authenticate with Anova using the Firebase ID token to get the JWT
		anova_auth_req = requests.post('https://anovaculinary.io/authenticate', json = {}, headers = { 'firebase-token': firebase_id_token })
		self._anovaculinary_jwt = anova_auth_req.json().get('jwt') # Looks like this JWT is valid for an entire year...

		if not self._anovaculinary_jwt:
			raise Exception('Could not authenticate with Anova')

		# return self._anovaculinary_jwt as self._jwt
		return self._anovaculinary_jwt

	@property
	def water_temperature(self) -> Optional[Union[int, float]]:
		return self.state.get('temperature-info').get('water-temperature')

	@property
	def target_temperature(self) -> Optional[Union[int, float]]:
		return self.state.get('job').get('target-temperature')

	@property
	def heater_temperature(self)  -> Optional[Union[int, float]]:
		return  self.state.get('temperature-info').get('heater-temperature')

	@property
	def triac_temperature(self)  -> Optional[Union[int, float]]:
		return self.state.get('temperature-info').get('triac-temperature')

	@property
	def temperature_unit(self) -> Optional[str]:
		return self.state.get('job').get('temperature-unit')

	# the following would be useful, but in the new api there seem to be no way to get them
	# @property                                 
	# def speaker_mode(self) -> Optional[bool]:
	#     return self.state.get('speaker_mode')

	# @property
	# def alarm_active(self) -> Optional[bool]:
	#     return self.state.get('alarm_active', False)

	@property
	def job_update_time(self) -> Optional[datetime.datetime]:
		return datetime.datetime.strptime( self.raw_state[0].get('header').get('created-at'),  '%Y-%m-%dT%H:%M:%S.%fZ')

	@property
	def job_end_time(self) -> Optional[datetime.datetime]:
		return self.job_update_time + datetime.timedelta(seconds=self.time_remaining)

	@property
	def job_start_time(self) -> Optional[datetime.datetime]:
		return self.job_update_time - datetime.timedelta(seconds=(self.timer_length - self.time_remaining) )

	@property
	def heater_duty_cycle(self) -> Optional[float]:
		return self.state.get('heater-control').get('duty-cycle') if self.state.get('heater-control') else None

	@property
	def motor_duty_cycle(self) -> Optional[float]:
		return self.state.get('motor-control').get('duty-cycle') if self.state.get('motor-control') else None

	@property
	def wifi_connected(self) -> Optional[bool]:
		return True if self.state.get('network-info').get('connection-status') == 'connected-station' else False

	@property
	def wifi_ssid(self) -> Optional[str]:
		return self.state.get('network-info').get('ssid')

	@property
	def device_safe(self) -> Optional[bool]:
		return bool(self.state.get('pin-info').get('device-safe'))

	@property
	def water_leak(self) -> Optional[bool]:
		return bool(self.state.get('pin-info').get('water-leak'))

	@property
	def water_level_critical(self) -> Optional[bool]:
		return bool(self.state.get('pin-info').get('water-level-critical'))

	@property
	def water_level_low(self) -> Optional[bool]:
		return bool(self.state.get('pin-info').get('water-level-low'))

	@property
	def mode(self) -> Optional[str]: 
		return self.state.get('job').get('mode')

	@property
	def job_status(self) -> Optional[str]: 
		return self.state.get('job-status').get('state')

	@property
	def time_remaining(self) -> Optional[int]:
		return self.state.get('job-status').get('cook-time-remaining')

	@property
	def timer_length(self) -> Optional[int]:
		return self.state.get('job').get('cook-time-seconds')

	# the following would be useful, but in the new api there seem to be no way to get them
	# async def set_speaker_mode(self, mode: bool):
	#     await self._request(data={'speaker_mode': mode})
	#     self.state['speaker_mode'] = mode

	# async def stop_alarm(self):
	#     await self._request(data={'alarm_active': False})
	#     del self.state['alarm_active']

	async def save(self):
		"""Push local state to the cooker via the API."""
		if not self._jwt:
			raise Exception('No JWT set - before calling save(), you must call authenticate(email, password)')

		# Validate temperature unit
		if self.temperature_unit not in ['F', 'C']:
			raise Exception('Invalid temperature unit - only F or C are supported')

		# Validate cook time and target temperature
		if type(self.timer_length) != int or type(self.target_temp) != float:
			raise Exception('Invalid cook time or target temperature')

		# Now prepare and send the request
		anova_req_headers = {
			'authorization': 'Bearer ' + self._jwt
		}

		anova_req_data = {
			'cook-time-seconds': self.timer_length,
			'id': ''.join(random.choices(string.ascii_lowercase + string.digits, k = 22)), # 22 digit random job ID for a new job at every save
			'mode': self.mode,
			'ota-url': '',
			'target-temperature': self.target_temp,
			'temperature-unit': self.temperature_unit
		}

		async with aiohttp.ClientSession() as session:
		anova_req = session.put('https://anovaculinary.io/devices/{}/current-job'.format(self.device_id), json = anova_req_data, headers = anova_req_headers)
		if anova_req.status_code != 200:
			raise Exception('An unexpected error occurred')

		if anova_req.json() != anova_req_data:
			raise Exception('An unexpected error occurred')

		return True

	async def set_target_temperature(self, temperature: Union[int, float]):
		self.target_temp = float(temperature)
		await self.save()

	async def set_temperature_unit(self, unit: str):
		if unit not in ('', 'c', 'f'):
			raise ValueError(f'Invalid unit: {unit}')

		self.temperature_unit = unit
		await self.save()

	async def set_timer_lenght(self, timer: Union[int, datetime.timedelta]): 
		if isinstance(timer, datetime.timedelta):
			self.timer_length = timer.total_seconds()
		else:
			self.timer_length = timer
		await self.save()

		self.temperature_unit = unit
		await self.save()

	async def start(self):
		self.mode = 'COOK'
		await self.save()

	async def stop(self):
		self.mode = 'IDLE'
		await self.save()
