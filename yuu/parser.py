import hmac
import hashlib
import struct
import time
import uuid
import m3u8
import re

from base64 import urlsafe_b64encode
from binascii import unhexlify
from Crypto.Cipher import AES

from .common import _STRTABLE, _HKEY, _MEDIATOKEN_API, _LICENSE_API, _USERAPI, _KEYPARAMS, _PROGRAMAPI, _CHANNELAPI, is_channel

def get_auth_token(session, verbose):
	def key_secret(devid):
		SECRETKEY = (b"v+Gjs=25Aw5erR!J8ZuvRrCx*rGswhB&qdHd_SYerEWdU&a?3DzN9B"
					b"Rbp5KwY4hEmcj5#fykMjJ=AuWz5GSMY-d@H7DMEh3M@9n2G552Us$$"
					b"k9cD=3TxwWe86!x#Zyhe")
		deviceid = devid.encode("utf-8")
		ts_1hour = (int(time.time()) + 60 * 60) // 3600 * 3600
		time_struct = time.gmtime(ts_1hour)
		ts_1hour_str = str(ts_1hour).encode("utf-8")
		
		h = hmac.new(SECRETKEY, digestmod=hashlib.sha256)
		h.update(SECRETKEY)
		tmp = h.digest()
		
		if verbose:
			print('[DEBUG] First salting data: {}'.format(tmp))

		for i in range(time_struct.tm_mon):
			h = hmac.new(SECRETKEY, digestmod=hashlib.sha256)
			h.update(tmp)
			tmp = h.digest()

		if verbose:
			print('[DEBUG] Second salting data: {}'.format(tmp))

		h = hmac.new(SECRETKEY, digestmod=hashlib.sha256)
		h.update(urlsafe_b64encode(tmp).rstrip(b"=") + deviceid)
		tmp = h.digest()

		if verbose:
			print('[DEBUG] Third salting data: {}'.format(tmp))

		for i in range(time_struct.tm_mday % 5):
			h = hmac.new(SECRETKEY, digestmod=hashlib.sha256)
			h.update(tmp)
			tmp = h.digest()

		if verbose:
			print('[DEBUG] Fourth salting data: {}'.format(tmp))

		h = hmac.new(SECRETKEY, digestmod=hashlib.sha256)
		h.update(urlsafe_b64encode(tmp).rstrip(b"=") + ts_1hour_str)
		tmp = h.digest()

		if verbose:
			print('[DEBUG] Fifth salting data: {}'.format(tmp))

		for i in range(time_struct.tm_hour % 5):  # utc hour
			h = hmac.new(SECRETKEY, digestmod=hashlib.sha256)
			h.update(tmp)
			tmp = h.digest()
		
		if verbose:
			print('[DEBUG] Last salting data: {}'.format(tmp))

		finalize = urlsafe_b64encode(tmp).rstrip(b"=").decode("utf-8")

		if verbose:
			print('[DEBUG] Key secret result: {}'.format(finalize))
			
		return finalize

	deviceid = str(uuid.uuid4())
	if verbose:
		print('[DEBUG] Generated Device UUID: {}'.format(deviceid))
	jsonData = {"deviceId": deviceid, "applicationKeySecret": keySecret(deviceid)}
	
	if verbose:
		print('[DEBUG] Sending json data')
	res = session.post(_USERAPI, json=jsonData).json()

	try:
		if verbose:
			print('[DEBUG] Data sended, getting token')
		token = res['token']
		if verbose:
			print('[DEBUG] Usertoken: {}'.format(token))
	except:
		print('[ERROR] Failed to get usertoken')
		import sys; sys.exit(1)
	
	return ['bearer ' + token, deviceid]

def fetch_video_key(ticket=None, authToken=None, session=None, verbose=False):
	if verbose:
		print('[DEBUG] Sending parameter to API')
	restoken = session.get(_MEDIATOKEN_API, params=_KEYPARAMS).json()
	mediatoken = restoken['token']
	if verbose:
		print('[DEBUG] Mediatoken: {}'.format(mediatoken))

	if verbose:
		print('[DEBUG] Sending ticket and mediatoken to License API')
	gl = session.post(_LICENSE_API, params={"t": mediatoken}, json={"kv": "a", "lt": ticket}).json()

	cid = gl['cid']
	k = gl['k']

	if verbose:
		print('[DEBUG] CID: {}'.format(cid))
		print('[DEBUG] K: {}'.format(k))

	if verbose:
		print('[DEBUG] Summing up data with STRTABLE')
	res = sum([_STRTABLE.find(k[i]) * (58 ** (len(k) - 1 - i)) for i in range(len(k))])

	if verbose:
		print('[DEBUG] Result: {}'.format(res))
		print('[DEBUG] Intepreting data')

	encvk = struct.pack('>QQ', res >> 64, res & 0xffffffffffffffff)

	if verbose:
		print('[DEBUG] Encoded video key: {}'.format(encvk))
		print('[DEBUG] Hashing data')

	h = hmac.new(unhexlify(_HKEY), (cid + authToken[1]).encode("utf-8"), digestmod=hashlib.sha256)
	enckey = h.digest()

	if verbose:
		print('[DEBUG] Second Encoded video key: {}'.format(enckey))
		print('[DEBUG] Decrypting result')

	aes = AES.new(enckey, AES.MODE_ECB)
	vkey = aes.decrypt(encvk)

	if verbose:
		print('[DEBUG] Decrypted, Resulting output: {}'.format(vkey))
	
	return vkey

def parsem3u8(m3u8, session, verbose):
	if verbose:
		print('[DEBUG] Requesting m3u8')
	r = session.get(m3u8)
	if verbose and r.status_code == 200:
		print('[DEBUG] m3u8 requested')
		print('[DEBUG] Parsing m3u8')
	x = M3U8.loads(r.text)
	files = x.files
	iv = x.keys[0].iv
	ticket = x.keys[0].uri[18:]
	if verbose:
		print('[DEBUG] Total files: {}'.format(len(files)))
		print('[DEBUG] IV: {}'.format(iv))
		print('[DEBUG] Ticket key: {}'.format(ticket))
	return [files[1:], iv[2:], ticket]

def webparse_m3u8(m3u8, session, verbose):
	if verbose:
		print('[DEBUG] Requesting data to API')
	reg = re.compile('(program|slot)\/[\w+-]+')
	res = re.search(reg, m3u8)[0]
	eplink = res[res.find('/')+1:]

	if 'slot' in res:
		req = session.get(_CHANNELAPI + eplink)
		if verbose and req.status_code == 200:
			print('[DEBUG] Data requested')
			print('[DEBUG] Parsing json API')
		jsdata = req.json()
		title = jsdata['slot']['title']
		res = m3u8[:m3u8.rfind('/')]
		res = res[res.rfind('/')+1:]

		if verbose:
			print('[DEBUG] M3U8 Link: {}'.format(m3u8))
			print('[DEBUG] Title: {}'.format(title))
		
		return title, res
	else:
		req = session.get(_PROGRAMAPI + eplink)
		if verbose and req.status_code == 200:
			print('[DEBUG] Data requested')
			print('[DEBUG] Parsing json API')
		jsdata = req.json()
		title = jsdata['series']['title']
		epnum = jsdata['episode']['title']
		outputfile = title + ' - ' + epnum

		res = m3u8[:m3u8.rfind('/')]
		res = res[res.rfind('/')+1:]
		
		if verbose:
			print('[DEBUG] M3U8 Link: {}'.format(m3u8))
			print('[DEBUG] Video title: {}'.format(title))
			print('[DEBUG] Episode number: {}'.format(epnum))
			
		return outputfile, res

def webparse(url, res, session, verbose):
	if verbose:
		print('[DEBUG] Requesting data to API')
	eplink = url[url.rfind('/')+1:]

	if is_channel(url):
		req = session.get(_CHANNELAPI + eplink)
		if verbose and req.status_code == 200:
			print('[DEBUG] Data requested')
			print('[DEBUG] Parsing json API')
		jsdata = req.json()
		title = jsdata['slot']['title']
		hls = jsdata['slot']['chasePlayback']['hls']

		m3u8link = '{x}/{r}/playlist.m3u8'.format(x=hls[:hls.rfind('/')], r=res[:-1])

		if verbose:
			print('[DEBUG] M3U8 Link: {}'.format(m3u8link))
			print('[DEBUG] Title: {}'.format(title))

		return title, m3u8link
	else:
		req = session.get(_PROGRAMAPI + eplink)
		if verbose and req.status_code == 200:
			print('[DEBUG] Data requested')
			print('[DEBUG] Parsing json API')
		jsdata = req.json()
		title = jsdata['series']['title']
		epnum = jsdata['episode']['title']
		hls = jsdata['playback']['hls']
		outputfile = title + ' - ' + epnum
		
		m3u8link = '{x}/{r}/playlist.m3u8'.format(x=hls[:hls.rfind('/')], r=res[:-1])
		
		if verbose:
			print('[DEBUG] M3U8 Link: {}'.format(m3u8link))
			print('[DEBUG] Video title: {}'.format(title))
			print('[DEBUG] Episode number: {}'.format(epnum))
			
		return outputfile, m3u8link