# -*- coding: utf-8 -*-
# Subtitrări în română: citește subtitrările de pe ecran și le traduce în română.
# Cum lucrează: la fiecare jumătate de secundă recunoaște textul (OCR-ul Windows din NVDA) din partea de jos
# a ferestrei din față; când apare o subtitrare nouă și rămâne la fel două citiri la rând, o spune.
# Dacă nu e în română, o traduce întâi (Google Translate).

import difflib
import http.client
import json
import os
import re
import threading
import urllib.parse
import urllib.request

import addonHandler
import api
import config
import globalPluginHandler
import queueHandler
import speech
import ui
import wx
from logHandler import log
from scriptHandler import script

try:
	from speech.commands import LangChangeCommand
except Exception:
	LangChangeCommand = None

try:
	from contentRecog import uwpOcr, RecogImageInfo
except Exception:
	uwpOcr = None

try:
	from contentRecog.recogUi import _captureImage   # merge și cu perdeaua de ecran pornită (NVDA nou)
except Exception:
	_captureImage = None

from . import actualizare
from .voce import Voce

CONF = "subtitrariRomana"
config.conf.spec[CONF] = {
	"activ": "boolean(default=False)",
	"voce": "boolean(default=False)",
}
INTERVAL = 250   # milisecunde între două citiri (cât mai des, ca subtitrarea să se audă repede)
ZONA = (0.55, 1.0)   # partea de jos a ferestrei, unde sunt subtitrările (din înălțime)


def _capteaza(info):
	if _captureImage is not None:
		return _captureImage(info)
	import screenBitmap
	sb = screenBitmap.ScreenBitmap(info.recogWidth, info.recogHeight)
	return sb.captureImage(info.screenLeft, info.screenTop, info.screenWidth, info.screenHeight)


def _curata(t):
	t = re.sub(r"\s+", " ", t or "").strip()
	# OCR-ul mai prinde bucăți din butoanele playerului (cifre de timp, simboluri); le scoatem
	t = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?\b", " ", t)
	t = re.sub(r"\s+", " ", t).strip(" -|•·")
	return t


def _asemanator(a, b):
	if not a or not b:
		return False
	return a == b or difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() > 0.9


def _cuvinte(t):
	return [re.sub(r"[^\w']", "", w.lower()) for w in t.split()]


def _acelasi_cuvant(x, y):
	"""Același cuvânt, cu tot cu greșelile de recunoaștere sau tăiat la margine (când subtitrarea apare sau dispare)."""
	if x == y:
		return True
	if len(x) >= 3 and len(y) >= 3 and (x.startswith(y) or y.startswith(x)):
		return True
	return len(x) >= 4 and len(y) >= 4 and difflib.SequenceMatcher(None, x, y).ratio() >= 0.75


def _cuprinsa(a, b):
	"""Adevărat dacă aproape toate cuvintele din a se găsesc în b (a e o bucată din b, cu greșeli de recunoaștere)."""
	wa, wb = [w for w in _cuvinte(a) if w], [w for w in _cuvinte(b) if w]
	if not wa or not wb:
		return False
	return sum(1 for w in wa if any(_acelasi_cuvant(w, v) for v in wb)) >= 0.7 * len(wa)


def _acelasi_rand(x, y):
	return _la_fel(x, y)


def _la_fel(a, b):
	"""Aceeași replică citită de două ori. Pe un film, fundalul se schimbă și recunoașterea dă de fiecare dată
	un text puțin diferit; de aceea se compară și cuvânt cu cuvânt, nu doar literă cu literă."""
	if not a or not b:
		return False
	if _asemanator(a, b):
		return True
	wa, wb = [w for w in _cuvinte(a) if w], [w for w in _cuvinte(b) if w]
	if not wa or not wb:
		return False
	pot_a = sum(1 for w in wa if any(_acelasi_cuvant(w, v) for v in wb))
	pot_b = sum(1 for w in wb if any(_acelasi_cuvant(w, v) for v in wa))
	return pot_a >= 0.8 * len(wa) and pot_b >= 0.8 * len(wb)


def parte_noua(vechi, nou):
	"""Ce e nou în replica „nou” față de cea spusă înainte (rândurile sunt despărțite prin \\n).
	La subtitrările care curg (YouTube automat) rândul de jos urcă sus și dedesubt apare altul, sau rândul crește
	cu cuvinte: se spune doar ce e nou. Altfel se spune toată replica, chiar dacă seamănă cu cea de dinainte."""
	ln = [r for r in nou.split("\n") if r.strip()]
	if not ln:
		return ""
	if not vechi:
		return " ".join(ln)
	lv = [r for r in vechi.split("\n") if r.strip()]
	for k in range(min(len(lv), len(ln)), 0, -1):
		if all(_acelasi_rand(lv[len(lv) - k + i], ln[i]) for i in range(k)):
			return " ".join(ln[k:])          # primele rânduri sunt ultimele de dinainte: doar restul e nou
	wl, wf = _cuvinte(lv[-1]), _cuvinte(ln[0])
	if len(wl) >= 2 and len(wf) > len(wl) and wf[:len(wl)] == wl:
		return " ".join(ln[0].split()[len(wl):] + ln[1:])   # rândul a crescut cu cuvinte noi
	return " ".join(ln)


def traduce(text):
	"""(textul în română, limba originală). Fără internet: (text, None)."""
	cale = "/translate_a/single?" + urllib.parse.urlencode({"client": "gtx", "sl": "auto", "tl": "ro", "dt": "t", "q": text})
	try:
		d = json.loads(_cere_traducerea(cale).decode("utf-8"))
		ro = "".join(p[0] for p in d[0] if p and p[0])
		return ro or text, d[2] if len(d) > 2 else None
	except Exception as e:
		log.debug(f"subtitrari: traducerea nu a mers: {e}")
		return text, None


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = "Subtitrări în română"

	def __init__(self):
		super().__init__()
		self._ocr = None
		self._ocupat = False
		self._timer = wx.PyTimer(self._tic)
		self._candidat = ""
		self._spus = ""            # ultima subtitrare recunoscută (originalul)
		self._ultima = ""          # ultima subtitrare spusă (în română)
		self._cache = {}
		self._in_lucru = set()     # replici care se traduc acum
		self._coada = []           # replici confirmate, în ordine, care așteaptă să fie spuse
		self._voce = Voce(self._adauga)
		self._timer_voce = wx.PyTimer(self._tic_voce)
		if config.conf[CONF]["voce"]:
			wx.CallLater(3000, self._porneste_voce)
		elif config.conf[CONF]["activ"]:
			wx.CallLater(3000, self._porneste)
		actualizare.verifica_mai_tarziu()

	def terminate(self):
		try:
			self._timer.Stop()
			self._timer_voce.Stop()
		except Exception:
			pass
		super().terminate()

	# ---- citirea ----
	def _porneste(self):
		if uwpOcr is None:
			ui.message("Recunoașterea textului din Windows nu e disponibilă în acest NVDA.")
			return False
		try:
			self._ocr = uwpOcr.UwpOcr()
		except Exception as e:
			ui.message(f"Recunoașterea textului nu a pornit: {e}")
			return False
		self._candidat = self._spus = ""
		self._timer.Start(INTERVAL)
		return True

	def _opreste(self):
		self._timer.Stop()
		if self._ocr is not None:
			try:
				self._ocr.cancel()
			except Exception:
				pass

	def _tic(self):
		if self._ocupat or self._ocr is None:
			return
		try:
			fg = api.getForegroundObject()
			left, top, width, height = fg.location
		except Exception:
			return
		if width < 50 or height < 50:
			return
		a, b = ZONA
		y0 = top + int(height * a)
		h = max(20, int(height * (b - a)))
		try:
			info = RecogImageInfo.createFromRecognizer(left, y0, width, h, self._ocr)
			pixeli = _capteaza(info)
		except Exception as e:
			log.debug(f"subtitrari: captura nu a mers: {e}")
			return
		self._ocupat = True
		try:
			self._ocr.recognize(pixeli, info, self._rezultat)
		except Exception as e:
			self._ocupat = False
			log.debug(f"subtitrari: OCR nu a mers: {e}")

	def _rezultat(self, rez):
		# vine dintr-un fir al OCR-ului
		self._ocupat = False
		if isinstance(rez, Exception):
			return
		try:
			randuri = [_curata(" ".join(w["text"] for w in linie)) for linie in rez.data]
			text = "\n".join(r for r in randuri if r)
		except Exception:
			return
		queueHandler.queueFunction(queueHandler.eventQueue, self._text_nou, text)

	def _text_nou(self, text):
		valid = len(text) >= 2 and re.search(r"[^\W\d_]{2}", text)
		if not valid:
			# a dispărut subtitrarea: dacă o replică apucase să fie citită o singură dată (a stat foarte puțin
			# pe ecran), se spune totuși, ca să nu se piardă
			self._abandon(self._candidat, "")
			self._candidat = ""
			if not text:
				self._spus = ""      # aceeași replică, dacă revine după o pauză, se spune din nou
			return
		if _la_fel(text, self._spus):
			self._candidat = ""
			return
		if not _la_fel(text, self._candidat):
			# replică nouă: o trimit la tradus imediat, cât aștept să văd că rămâne la fel încă o citire,
			# ca traducerea să fie gata (aproape) când o confirm
			self._abandon(self._candidat, text)
			self._candidat = text
			log.info("subtitrari: citit " + text.replace("\n", " / "))   # în jurnalul NVDA, ca să se vadă ce recunoaște
			bucata = parte_noua(self._spus, text)
			if bucata:
				self._traduce(bucata)
			return
		text = self._candidat           # aceeași replică pentru care a pornit traducerea
		self._candidat = ""
		self._confirma(text)

	def _confirma(self, text):
		bucata = parte_noua(self._spus, text)
		self._spus = text
		if bucata:
			self._adauga(bucata)

	def _adauga(self, bucata):
		self._coada.append(bucata)   # se spun toate, în ordine, fiecare când îi e gata traducerea
		self._traduce(bucata)
		self._goleste()

	# ---- vocea personajelor (Subtitrările live din Windows 11) ----
	def _porneste_voce(self):
		if not self._voce.porneste_windows():
			ui.message("Subtitrările live din Windows nu sunt pe acest calculator. Merg doar pe Windows 11.")
			return False
		self._voce.reset()
		self._fara_fereastra = 0
		self._timer_voce.Start(150)
		return True

	def _opreste_voce(self):
		self._timer_voce.Stop()
		self._voce.inchide_windows()

	def _tic_voce(self):
		try:
			ok = self._voce.tic()
		except Exception as e:
			log.debug(f"subtitrari: voce: {e}")
			ok = False
		if ok:
			self._fara_fereastra = 0
			return
		self._fara_fereastra += 1
		if self._fara_fereastra == 70:          # ~10 secunde fără fereastra Subtitrărilor live
			if not self._voce.porneste_windows():
				self._opreste_voce()
				config.conf[CONF]["voce"] = False

	def _abandon(self, cand, urmatorul):
		"""O replică văzută o singură dată, înlocuită înainte de a doua citire. Se spune, afară de cazul în care
		e doar o bucată din replica de dinainte (când dispare) sau din cea care urmează (când apare)."""
		if not cand or _cuprinsa(cand, self._spus) or (urmatorul and _cuprinsa(cand, urmatorul)):
			return
		self._confirma(cand)

	def _traduce(self, text):
		if text in self._cache or text in self._in_lucru:
			return
		self._in_lucru.add(text)
		threading.Thread(target=self._traduce_fir, args=(text,), daemon=True).start()

	def _traduce_fir(self, text):
		ro, _limba = traduce(text)
		queueHandler.queueFunction(queueHandler.eventQueue, self._gata, text, ro)

	def _gata(self, text, ro):
		self._in_lucru.discard(text)
		if len(self._cache) > 300:
			self._cache = {k: v for k, v in self._cache.items() if k in self._coada}
		self._cache[text] = ro
		self._goleste()

	def _goleste(self):
		while self._coada and self._coada[0] in self._cache:
			self._spune(self._cache[self._coada.pop(0)])

	def _spune(self, text, romana=True):
		# fără să întrerupă replica de dinainte: NVDA le spune una după alta, ca să nu se piardă nimic
		self._ultima = text
		if romana and LangChangeCommand is not None:
			speech.speak([LangChangeCommand("ro"), text])
		else:
			speech.speakMessage(text)

	# ---- tastele ----
	@script(description="Pornește sau oprește ascultarea vocii personajelor, tradusă în română", gesture="kb:NVDA+alt+v")
	def script_voce(self, gesture):
		if self._timer_voce.IsRunning():
			self._opreste_voce()
			config.conf[CONF]["voce"] = False
			ui.message("Nu mai ascult vocea.")
			return
		if self._timer.IsRunning():
			self._opreste()                   # una sau alta: altfel replicile s-ar auzi de două ori
			config.conf[CONF]["activ"] = False
		if self._porneste_voce():
			config.conf[CONF]["voce"] = True
			ui.message("Ascult vocea și o traduc în română.")

	@script(description="Pornește sau oprește citirea subtitrărilor", gesture="kb:NVDA+alt+s")
	def script_comuta(self, gesture):
		if not self._timer.IsRunning() and self._timer_voce.IsRunning():
			self._opreste_voce()
			config.conf[CONF]["voce"] = False
		if self._timer.IsRunning():
			self._opreste()
			config.conf[CONF]["activ"] = False
			ui.message("Subtitrările nu se mai citesc.")
		elif self._porneste():
			config.conf[CONF]["activ"] = True
			ui.message("Citesc subtitrările.")
