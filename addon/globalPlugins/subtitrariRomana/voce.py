# -*- coding: utf-8 -*-
# Vocea personajelor: Subtitrările live din Windows 11 (LiveCaptions.exe) transformă în text tot ce se aude pe
# calculator. De aici se citește textul lor (UI Automation, elementul CaptionsTextBlock), se iau propozițiile noi
# și se dau mai departe la tradus și spus în română.

import ctypes
import difflib
import os
import re
import subprocess
import time

from logHandler import log

user32 = ctypes.windll.user32
CLASA = "LiveCaptionsDesktopWindow"
PAUZA = 1.0            # secunde: o propoziție neterminată, nemodificată atât, se spune oricum (vorbitorul a făcut pauză)
SFARSIT = re.compile(r"[.!?…。？！]$")


def _norm(t):
	return " ".join(re.sub(r"[^\w']", "", w.lower()) for w in t.split() if re.sub(r"[^\w']", "", w))


class Voce:
	def __init__(self, adauga):
		self.adauga = adauga        # funcția care traduce și spune o bucată de text
		self._el = None
		self._hwnd = 0
		self._pornit_de_mine = False
		self.reset()

	def reset(self):
		self._ultim_text = None
		self._schimbat = 0.0
		self._neterminata = ""
		self._terminate = []        # propozițiile terminate din citirea de dinainte (normalizate)
		self._partial = ""          # o propoziție neterminată spusă în pauza vorbitorului
		self._baza = True           # la prima citire nu se spune ce era deja scris în fereastră

	# ---- fereastra Subtitrărilor live ----
	def porneste_windows(self):
		"""Pornește Subtitrările live dacă nu sunt deschise. Întoarce False dacă nu există pe acest Windows."""
		if user32.FindWindowW(CLASA, None):
			return True
		cale = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "LiveCaptions.exe")
		if not os.path.exists(cale):
			return False
		try:
			subprocess.Popen([cale])
			self._pornit_de_mine = True
		except Exception as e:
			log.error(f"subtitrari: LiveCaptions nu a pornit: {e}")
			return False
		return True

	def inchide_windows(self):
		if self._pornit_de_mine:
			h = user32.FindWindowW(CLASA, None)
			if h:
				user32.PostMessageW(h, 0x0010, 0, 0)     # WM_CLOSE
		self._pornit_de_mine = False

	def _text(self):
		hwnd = user32.FindWindowW(CLASA, None)
		if not hwnd:
			self._el = None
			return None
		import UIAHandler
		h = UIAHandler.handler
		if h is None:
			return None
		try:
			if self._el is None or hwnd != self._hwnd:
				rad = h.clientObject.ElementFromHandle(hwnd)
				cond = h.clientObject.CreatePropertyCondition(UIAHandler.UIA_AutomationIdPropertyId, "CaptionsTextBlock")
				self._el = rad.FindFirst(UIAHandler.TreeScope_Descendants, cond)
				self._hwnd = hwnd
			if self._el is None:
				return None
			return self._el.CurrentName or ""
		except Exception:
			self._el = None
			return None

	# ---- propozițiile noi ----
	@staticmethod
	def _la_fel(a, b, primul=False):
		"""Aceeași propoziție (cu mici corecturi ale recunoașterii). primul: cea de sus poate fi tăiată la început."""
		if a == b:
			return True
		if primul and b.endswith(" " + a):
			return True
		return difflib.SequenceMatcher(None, a, b).ratio() > 0.85

	def _noi(self, cur):
		"""Propozițiile terminate care n-au fost în citirea de dinainte (aliniate după ce s-a păstrat)."""
		prev = self._terminate
		for k in range(min(len(prev), len(cur)), 0, -1):
			if all(self._la_fel(cur[i], prev[len(prev) - k + i], primul=(i == 0)) for i in range(k)):
				return cur[k:]
		if prev and cur and any(self._la_fel(cur[0], x, primul=True) for x in prev):
			# fereastra a sărit peste ceva: iau doar ce nu seamănă cu ce era
			return [c for c in cur if not any(self._la_fel(c, x, primul=True) for x in prev)]
		return cur

	def _spune(self, prop):
		n = _norm(prop)
		if not n:
			return
		p = self._partial
		self._partial = ""
		if p and n != p and n.startswith(p + " "):
			rest = " ".join(prop.split()[len(p.split()):])     # începutul a fost spus în pauza vorbitorului
			if rest.strip():
				self.adauga(rest)
			return
		if p and n == p:
			return
		self.adauga(prop)

	def tic(self):
		t = self._text()
		if t is None:
			return False
		t = re.sub(r"\s+", " ", t).strip()
		acum = time.monotonic()
		if t != self._ultim_text:
			self._ultim_text = t
			self._schimbat = acum
			parti = [p for p in re.split(r"(?<=[.!?…。？！])\s+", t) if p.strip()]
			terminate = parti if parti and SFARSIT.search(parti[-1]) else parti[:-1]
			self._neterminata = "" if len(terminate) == len(parti) else parti[-1]
			cur = [_norm(p) for p in terminate]
			if self._baza:
				# ce era deja în fereastră când ai pornit nu se citește
				self._terminate = cur
				self._neterminata = ""
				self._baza = False
				return True
			noi = self._noi(cur)
			self._terminate = cur
			for p in terminate[len(terminate) - len(noi):] if noi else []:
				self._spune(p)
		elif self._neterminata and acum - self._schimbat > PAUZA:
			p, self._neterminata = self._neterminata, ""
			n = _norm(p)
			if n and n != self._partial:
				self._partial = n
				self.adauga(p)
		return True
