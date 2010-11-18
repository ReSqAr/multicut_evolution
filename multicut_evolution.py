#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    multicut_evolution -- Eine erweiterte Pythonversion von multicut_light.
    Copyright (C) 2010  Yasin Zähringer (yasinzaehringer+mutlicut@yhjz.de)
	          (C) 2010  Matthias Kümmerer

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program. If not, see <http://www.gnu.org/licenses/>.
"""

import subprocess
import os, shutil, codecs
import time
import random
import tempfile
import urllib2
import re
import sys
import datetime
import getopt
import hashlib
import ast


C_CLEAR			= "\033[0m"
C_RED			= "\033[41;37;1m"
C_BLUE			= "\033[44;37;1m"
C_RED_UNDERLINE	= "\033[41;37;1;4m"

multicut_evolution_date = "17.11.2010"
prog_id = "multicut_evolution.py/%s" % multicut_evolution_date
VERBOSITY_LEVEL = 0

prog_help = \
"""
Hilfe für multicut_evolution.py (%s):

multicut_evolution.py [--help] [--nocheck] [--verbosity $d] [--config $name] $file1 ...

Die übergebenden Dateien werden anhand von auswählbaren Cutlists geschnitten.
Dies geschieht in mehreren Phasen:

Phase 1 - Auswahl der Cutlist
	Für jede angegebene Datei wird eine Cutlistübersichtsseite angegeben. Daraus
	kann man eine Cutlist auswählen, in dem man die Nummer eintippt und mit
	Enter bestätigt und testen, indem man 'test $d' (wobei $d die Nummer der 
	Cutlist ist) eintippt und mit Enter bestätigt. Einfach ohne Eingabe Enter
	drücken, bewirkt, dass keine Cutlist ausgewählt wird.
	Nachdem für alle Filme eine Cutlist ausgewählt wurde, hat man die Option
	einzelne Cutlists umzuwählen oder alle zu bestätigen. Bestätigen
	funktioniert einfach durch Enter drücken. Das Umwählen von Cutlists wird
	durch Eingeben der zu den Filmen gehörenden Nummern ausgelöst. Dabei sind
	Eingaben wie '1', '2-5' und '1,2-5' zulässig.

Phase 2 - Schneiden
	In dieser Phase ist keine Benutzerinteraktion notwendig.

Phase 3 - Überprüfen der Schnitte
	Nun können die Filme ausgewählt werden, die überprüft werden sollen. Dabei
	können gewisse Filme angegeben durch ihre Nummer oder man überprüft alle
	noch nicht überprüften Filme durch Eingabe von 'a'. Alternativ kann man alle
	Filme überprüfen (auch die, die schon überprüft wurden) durch Eingabe von 
	'f'. Desweiteren kann man das Programm durch 'n' beenden.
	
	Das Überprüfen untergliedert sich weiter, zu erst werden die Schnitte 
	angezeigt, danach kann man die Cutlist bewerten mit Noten zwischen 0 - 5. 
	(0 = schlechteste, 5 = beste Bewertung) Seien Sie fair! Danach kann man
	angegeben, ob die geschnitte Datei gelöscht werden soll, was z.B. nach 
	Fehlschnitten hilfreich ist. Dabei wird die Originaldatei an ihren 
	ursprünglichen Ort zurückverschoben.


Optionen:
	--help
		Zeigt dise Hilfe an

	--nocheck
		Geschnittene Dateien werden nicht zur Überprüfung 
		wiedergegeben.

	--config $name
		Gibt den Namen der zu verwendenden Konfigurationsdatei an.
		[default: ~/.multicut_evolution.conf]
	
	--verbosity $d
		Debuginformationen werden entsprechend ausgegeben.
		[default: 0, maximal 5]

In der Konfigurationsdatei zur Verfügung stehenden Einstellungen (der 
Standardpfad für die Konfigurationsdatei ist '~/.multicut_evolution.conf'):
	cutdir= 
		Ausgabepfad [default: .]
	uncutdir=
		Ausgabepfad für alte Dateien [default: .]
	virtualdub=
		Pfad von vdub.exe [default: None]
	avidemux_gui=
		Befehl zum Ausführen einer Avidemux-Version mit GUI. 
		[default: avidemux2_qt4]
	cachedir=
		Pfad zu Cache [default: ~/.cache/mutlicut/]
		Ein leerer Pfad bedeutet kein Cachen.
	vorlauf=
		Vorlauf bei der Überprüfung [default: 10]
	nachlauf=
		Nachlauf bei der Überprüfung [default: 5]
	bewerten=
		Gibt an, ob nach einer Wertung gefragt werden soll. [default:1]
	cutname=
		Ausdruck für Ausgabename (s.u.) [default: {base}-cut{rating}.{ext}]
	uncutname=
		Ausdruck für Ausgabename (s.u.) [default: {full}]
	autor=
		Gibt den Namen an, der als Autor für selbsterstelte Cutlists verwendet
		wird.


Beschreibung der Sprache für die Namensgebung von Dateien:
(siehe auch cutname=, uncutname=)
	{base}		Dateiname ohne Endung
	{ext}		Dateiendung
	{shortext}	Dateiendung ohne mpg.
	{rating}	Bewertung der Cutlist *100
	{full}		Der gesamte Dateiname
""" % multicut_evolution_date


print "multicut_evolution.py Copyright (C) 2010  Yasin Zähringer (yasinzaehringer+mutlicut@yhjz.de)"
print "                                (C) 2010  Matthias Kümmerer"
print "(URL: https://yhjz.de/public/gitweb/gitweb.cgi?p=multicut_evolution.git)"
print "This program comes with ABSOLUTELY NO WARRANTY."
print


avidemux_cmds = ["avidemux2_cli", "avidemux_cli",
					"avidemux2", "avidemux", 
					"avidemux2_gtk", "avidemux_gtk",
					"avidemux2_qt4", "avidemux_qt4"]

search_request_expire_period = datetime.timedelta(hours=2)
cutlist_expire_period = datetime.timedelta(days=14)

#
# helper functions
#
def Debug(level, text):
	if level <= VERBOSITY_LEVEL:
		print "Debug (%d): %s" % (level,text)


def Run(cmd, args):
	Debug(2, "running %s with args %s" % (cmd,args))
	sub = subprocess.Popen(args = [cmd] + args, stdout = subprocess.PIPE, stderr = subprocess.PIPE)	
	out, err = sub.communicate()
	Debug(4, "errout: %s" % err)
	Debug(5, "out: %s" % out)
	return out, err

def ParseIIRange(iis):
	return sum([ParseII(ii) for ii in iis.split(',')],[])

def ParseII(ii):
	"""
	syntax:
	$number
	$a = a
	$a - $b = a..b
	$a - $s - $b = a, a+s, a+2s, ..., b
	"""
	a, step, b = 0, 1, 0
	s = ii.split('-')
	if len(s) == 1:
		a,b = s+s
	elif len(s) == 2:
		a,b = s
	elif len(s) == 3:
		a,step,b = s
	else:
		raise ValueError("Too many '-'")
	a,step,b = int(a), int(step), int(b)
	return range(a,b+1,step)

#
# Helper Class
#
class FileCache:
	def __init__(self, name, directory, getter, expireperiod=None, debug=lambda x:None):
		self.name = name
		self.directory = directory
		self.getter = getter
		self.expireperiod = expireperiod
		self.debug = debug
		
		
		if self.directory:
			self.fileCacheEnabled = True
			# create directory if it doesn't exist
			if not os.path.exists(self.directory):
				os.makedirs(self.directory)
		else:
			self.fileCacheEnabled = False
		
		# cache trackers
		self.memoryCache = {}
		self.fileCache = {}
		
		# load file cache index
		self.loadFileCache()
		
	#
	# file system cache
	#
	def getIndexFileName(self):
		return os.path.join(self.directory, "%s.index" % self.name)
	def getFileName(self, uuid):
		return os.path.join(self.directory, "%s.%s" % (uuid,self.name))
	def convertTime2String(self, dt):
		return str(tuple(list(dt.timetuple())[:6]))
	def convertString2Time(self, dt_raw):
		dt = ast.literal_eval(dt_raw)
		return datetime.datetime(*dt[:6])
		

	def loadFileCache(self):
		if not self.fileCacheEnabled:
			return

		now = datetime.datetime.now()
		self.fileCache = {}
		indexfile = self.getIndexFileName()
		
		try:
			index = codecs.open(indexfile, 'r', 'utf8').read()
		except:
			return
		
		for line in index.split('\n'):
			if not line: continue
			uuid, dt_raw = line.split('\t')
			
			fname = self.getFileName(uuid)
			dt = self.convertString2Time(dt_raw)
			
			if self.expireperiod and dt + self.expireperiod < now:
				self.debug("FileCache('%s')::loadFileCache: removed expired file %s"%(self.name,fname))
				self.debug("FileCache('%s')::loadFileCache: condition: %s + %s < %s" % (self.name, dt, self.expireperiod, now))
				try: 	os.remove(fname)
				except:	pass
			else:
				if os.path.isfile(fname):
					self.fileCache[uuid] = dt_raw
		
		index = []
		for uuid, dt_raw in self.fileCache.items():
			index.append( "%s\t%s" % (uuid, dt_raw) )
		codecs.open(indexfile, 'w', 'utf8').write('\n'.join(index))
	
	
	def appendFileCache(self, uuid, content):
		if not self.fileCacheEnabled:
			return

		fname = self.getFileName(uuid)
		codecs.open(fname, 'w', 'utf8').write(content)
		
		indexfile = self.getIndexFileName()
		now = datetime.datetime.now()
		now_raw = self.convertTime2String(now)
		appendindex = "\n%s\t%s" % (uuid, now_raw)
		codecs.open(indexfile, 'a', 'utf8').write(appendindex)
	
	def readFileContent(self, uuid):
		fname = self.getFileName(uuid)
		return codecs.open(fname, 'r', 'utf8').read()
		
	def updateContent(self, x, content):
		uuid = hashlib.sha1(x).hexdigest()
		
		fname = self.getFileName(uuid)
		
		if uuid in self.fileCache:
			codecs.open(fname, 'w', 'utf8').write(content)
		else:
			self.appendFileCache(uuid, content)
		
		self.memoryCache[uuid] = content
	
	#
	# actual getter
	#
	def get(self, x):
		uuid = hashlib.sha1(x).hexdigest()
		
		if uuid in self.memoryCache:
			self.debug("FileCache('%s')::get('%s'): memory cache hit" % (self.name,x))
			return self.memoryCache[uuid]
		
		try:
			if uuid in self.fileCache and self.fileCacheEnabled:
				self.debug("FileCache('%s')::get('%s'): file cache hit" % (self.name,x))
				content = self.readFileContent(uuid)
				self.memoryCache[uuid] = content
				return content
		except:
			print "File associated with '%s' not found -- ignoring" % uuid
		
		self.debug("FileCache('%s')::get('%s'): total cache miss" % (self.name,x))
		content = self.getter(x)
		self.appendFileCache(uuid, content)
		self.memoryCache[uuid] = content
		return content


#
# CutList Class
#
class CutList:
	def __init__(self, cutlistprov, cutlist=None, cutlist_dict=None):
		self.cutlistprov = cutlistprov
		
		if cutlist:
			#tags:
			# 'id', 'name', 'rating', 'ratingcount', 'author', 'ratingbyauthor', 'actualcontent', 'usercomment', 'cuts', 'filename', 
			# 'filename_original', 'autoname', 'withframes', 'withtime', 'duration', 'errors', 'othererrordescription', 'downloadcount'
			tagvalues = re.findall("<(?P<tag>.*?)>\s*(?P<value>.*?)\s*</(?P=tag)>", cutlist, re.DOTALL) #python is so cool
			self.attr = dict(tagvalues)
		elif cutlist_dict:
			self.attr = dict(cutlist_dict)
		else:
			raise ValueError("CutList was called with illegal arguments.")
		
		#
		# create metarating
		#
		if 'rating' in self.attr and 'ratingbyauthor' in self.attr and 'ratingcount' in self.attr and 'downloadcount' in self.attr:
			def ToF(a, default):
				try:	return float(a)
				except:	return default
			self.attr["metarating"] = ToF(self.attr['rating'],-1) \
									+ ToF(self.attr['ratingbyauthor'],-1) \
									+ ToF(self.attr['ratingcount'],0)/50 \
									+ ToF(self.attr['downloadcount'],0)/1000
		else:
			self.attr["metarating"] = 0.
	
	
	def __contains__(self, key):
		return key in self.attr
	
	def __getitem__(self, key):
		return self.attr[key]

	def __setitem__(self, key, value):
		self.attr[key] = value
	
	def GetCutList(self):
		return self.cutlistprov.GetCutList(self.attr["id"])

	def GetFPS(self):
		cutlisttxt = self.GetCutList()
		return float( re.search("FramesPerSecond=(?P<value>[0-9.]*)", cutlisttxt).group('value') )

	def TimesInFrames(self):
		cutlisttxt = self.GetCutList()
		if "\nStartFrame" in cutlisttxt:
			StartInFrames = re.findall("StartFrame=(?P<value>[0-9]*)", cutlisttxt)
			StartInFrames = [int(d) for d in StartInFrames]
			DurationInFrames= re.findall("DurationFrames=(?P<value>[0-9]*)", cutlisttxt)
			DurationInFrames = [int(d) for d in DurationInFrames]
		else:
			fps = self.GetFPS()
			Start = re.findall("Start=(?P<value>[0-9.]*)", cutlisttxt)
			StartInFrames = [int( float(d) * fps + 0.5 ) for d in Start]
			Duration = re.findall("Duration=(?P<value>[0-9.]*)", cutlisttxt)
			DurationInFrames = [int( float(d) * fps + 0.5 ) for d in Duration]
		return StartInFrames, DurationInFrames
	
	def TimesInSeconds(self):
		cutlisttxt = self.GetCutList()
		Start = re.findall("Start=(?P<value>[0-9.]*)", cutlisttxt)
		Start = [float(d) for d in Start]
		Duration = re.findall("Duration=(?P<value>[0-9.]*)", cutlisttxt)
		Duration = [float(d) for d in Duration]
		return Start, Duration

	def CutListToConsoleText(self, n):
		number = "[%d]" % n
		
		cuts   = self.attr["cuts"]   if self.attr["cuts"]   else "?"
		rating = self.attr["rating"] if self.attr["rating"] else "-"
		author = self.attr["author"] if self.attr["author"] else "---"
		
		cutsformat = "unbekannt"
		if self.attr["withframes"]:	cutsformat = "Frameangaben"
		if self.attr["withtime"]:	cutsformat = "Zeitangaben"
		
		duration = "??:??:??"
		if self.attr["duration"]:
			try:
				sc = int(float(self.attr["duration"]))
				duration = "%2.2d:%2.2d:%2.2d" % (sc//3600, (sc//60)%60, sc%60) # integer division
			except:
				pass
		
		if self.attr["errors"] != "000000":
			errortext = ["Anfang fehlt!", "Ende fehlt!", "Video!", "Audio!", "Fehler: %s" % self.attr["othererrordescription"], "EPG"]
			errors = []
			for i, c in enumerate(self.attr["errors"]):
				if c != '0':
					errors.append(errortext[i])
			errorline = "	Fehler:    @RED %s @CLEAR\n" % " ".join(errors)
		else:
			errorline = ""
		
		outtxt =  \
		  "@RED %s @CLEAR	Schnitte:  @BLUE %s @CLEAR (%s)	Spielzeit: @BLUE %s @CLEAR (hh:mm:ss)\n" % \
													(number, cuts, cutsformat, duration) \
		+ "%s	Bewertung: @BLUE %s (%s/%s) @CLEAR    	Autor:     @BLUE %s (%s) @CLEAR\n" \
				% (self.attr["metarating"], rating, self.attr["ratingcount"], self.attr["downloadcount"], 
																			author, self.attr["ratingbyauthor"])\
		+ errorline
		if self.attr["usercomment"]:
			outtxt += "	Kommentar: @BLUE %s @CLEAR\n" % self.attr["usercomment"]
		
		return outtxt.replace("@BLUE", C_BLUE).replace("@RED", C_RED).replace("@CLEAR", C_CLEAR)
		
	def ShowCuts(self, path, is_filecut, tempdir):
		fps = self.GetFPS()
		Start, Duration = self.TimesInSeconds()
		
		time_before_cut = self.cutlistprov.cutoptions.time_before_cut
		time_after_cut  = self.cutlistprov.cutoptions.time_after_cut
		
		discard = []
		countdown = []
		
		if is_filecut:
			for i in range(len(Duration)):
				ith_cut = sum( Duration[:i] )
				ippth_cut = sum( Duration[:i+1] )
				discard.append( ( ith_cut + time_after_cut, ippth_cut - time_before_cut) )
				countdown.append( ("Schnitt #%d" % (i+1),ippth_cut) )
		else:
			discard.append((0, max(0,Start[0]-time_before_cut)))
			countdown.append( ("Schnitt #0.Post", Start[0]) )
			
			for i in range(len(Start)):
				discard.append( ( Start[i] + time_after_cut, Start[i] + Duration[i] - time_before_cut) )
				
				countdown.append( ("Schnitt #%d.Pre" % (i+1), Start[i] + Duration[i]) )
				if i + 1 < len(Start):
					discard.append( ( Start[i] + Duration[i], Start[i+1] - time_before_cut) )
					countdown.append( ("Schnitt #%d.Post" % (i+1), Start[i+1] ) )
				else:
					discard.append( (Start[i] + Duration[i], 10 * 3600) ) # assume: length < 10h
				

		edl = "\n".join(["%f\t%f\t0" % (s,e) for s,e in discard])
		sub = ""
		
		pre_frames  = int( (12./25.) * fps + 0.5)
		post_frames = int( (13./25.) * fps + 0.5)
		for txt,time in countdown:
			for i in range(-15,16): # -15s until 15s
				frame = int((time + i) * fps + 0.5)
				if i < 0:	text = "%s in %ds" % (txt,-i)
				elif i == 0:text = "=->SCHNITT<-="
				elif i > 0:	text = "%ds nach %s" % (i,txt)
				
				sub += "{%d}{%d}%s\n" % (frame-pre_frames,frame+post_frames,text)
			
		filename = os.path.basename(path)
		d = random.getrandbits(32)
		edlfile = tempdir + "%d_%s.edl" % (d,filename)
		subfile = tempdir + "%d_%s.sub" % (d,filename)
		open(edlfile,"w").write(edl)
		open(subfile,"w").write(sub)
			
		Run("mplayer", ["-edl", edlfile, "-sub", subfile, "-osdlevel", "3", path])
	
	def PostProcessCutList(self):
		self.cutlistprov.PostProcessCutList( self.attr["id"] )


#
# CutListAT as CutlistProviderClass
#
class CutListAT:
	def __init__(self, cutoptions):
		self.opener = urllib2.build_opener()
		self.opener.addheaders = [ ('User-agent', prog_id)]
		self.cutoptions = cutoptions
		
		self.desc = "Cutlists von Cutlist.at herunterladen."
		
		self.cutlistCache = FileCache("cutlist", cutoptions.cachedir, self._GetCutList,
								cutlist_expire_period, lambda x: Debug(2, x))
		self.searchCache = FileCache("search", cutoptions.cachedir, self._GetSearchList,
								search_request_expire_period, lambda x: Debug(2, x))

	def Get(self, url):
		return self.opener.open("http://www.cutlist.at/" + url).read()
		
	def _GetSearchList(self, filename):
		url = "getxml.php?name=%s&version=0.9.8.0" % filename
		return unicode(self.Get(url), "iso-8859-1")
	def ListAll(self, filename):
		xml = self.searchCache.get(filename)
		cutlists = re.findall('<cutlist row_index="\\d">.*?</cutlist>', xml, re.DOTALL)		
		return [CutList(self,cutlist) for cutlist in cutlists]
	
	def _GetCutList(self, cl_id):
		url = "getfile.php?id=%s" % cl_id
		return unicode(self.Get(url), "iso-8859-1")
	def GetCutList(self, cl_id):
		return self.cutlistCache.get(cl_id)
	
	def RateCutList(self, cl_id, rating):
		Debug(2, "rate cutlist %s with %d" % (cl_id, rating))
		url = "rate.php?rate=%s&rating=%d" % (cl_id, rating)
		return self.Get(url)
	
	#
	# getView
	#
	def getView(prov, path):
		filename = os.path.basename(path)
		
		class View:
			def __init__(self):
				print "Hole Übersicht von cutlist.at..."
				self.cutlists = prov.ListAll(filename)
				print "%d Cutlist(s) gefunden" % len(self.cutlists)
				print
				
				self.cutlists.sort(key =  lambda x: -float(x['metarating']))

				for i, cutlist in enumerate(self.cutlists):
					print cutlist.CutListToConsoleText(i+1)
			
			def getCutlist(self, inp, **kwargs):
				try:
					i = int(inp)-1
					if 0 <= i < len(self.cutlists):
						return self.cutlists[i]
					else:
						print "Illegaler Index."
						return None
				except:
					print "Illegale Eingabe."
					return None
		return View()
	
	#
	# rate cutlist
	#
	def PostProcessCutList( self, cl_id ):
		if not self.cutoptions.do_rate:
			print "Bewerten ausgelassen."
			return
			
		print
		print "@RED Bitte eine Bewertung für die Cutlist abgeben... @CLEAR".replace("@RED", C_RED).replace("@CLEAR", C_CLEAR)
		print "[0] Dummy oder keine Cutlist"
		print "[1] Anfang und Ende grob geschnitten"
		print "[2] Anfang und Ende halbwegs genau geschnitten"
		print "[3] Schnitt ist annehmbar, Werbung entfernt"
		print "[4] Doppelte Szenen wurde nicht entfernt oder schönere Schnitte möglich"
		print "[5] Sämtliches unerwünschtes Material wurde framegenau entfernt"
		print

		while True:
			print "Wertung: ",
			try:
				inp = sys.stdin.readline().strip()
			except StandardError:
				sys.exit()
			if not inp:
				break
			else:
				try:
					i = int(inp)
					if 0 <= i <= 5:
						print u"Sende für Cutlist-ID '%s' die Bewertung %d..." % (cl_id, i),
						print "Antwort: '%s'" % self.RateCutList(cl_id, i)
						break
				except:
					print "Illegale Eingabe"

	
#
# CutListOwnProvider
#
class CutListOwnProvider:
	def __init__(self, cutoptions):
		self.cutoptions = cutoptions
		self.desc = "Eigene Cutlists erstellen."
		
		self.cutlistCache = FileCache("mycutlist", cutoptions.cachedir, lambda x: "", None, lambda x: Debug(2, x))
		self.delimiter = "66b29df4086fd34e6c63631553132e8421d5fe3698ba5120358ee31ffed9b518e61d0b0ed6a583ec1fd7367aab7af928196391f3131929\n"
	
	def getCutlists(self, filename):
		precutlists = self.cutlistCache.get(filename)
		precutlists = precutlists.split(self.delimiter) if precutlists else []
		precutlists = [ cutlist.split('\n',1) for cutlist in precutlists ]
		return [ (comment, CutList(self,cutlist_dict={'id':precutlist})) for comment, precutlist in precutlists ]
	
	def addCutlist(self, filename, cutlist):
		precutlists = self.cutlistCache.get(filename)
		precutlists = precutlists.split(self.delimiter) if precutlists else []
		
		addcutlist = "%s\n%s" % (datetime.datetime.now().strftime("%H:%M:%S am %d.%m.%Y"), cutlist)
		
		precutlists.append(addcutlist)
		self.cutlistCache.updateContent(filename, self.delimiter.join(precutlists))
	
	def createCutlist(self, path):
		cutlist = CutListGenerator(self).makeCutList(path)
		if cutlist:
			self.addCutlist(os.path.basename(path), cutlist)
			return CutList(self,cutlist_dict={'id':cutlist}) #full abuse
		else:
			return None
		
	def GetCutList(self, cl_id):
		return cl_id
	
	def UploadCutList(self, cutlist):
		print "Cutlist zum Hochladen:"
		lines = cutlist.split('\n')
		fname = [line for line in lines if line.startswith("ApplyToFile=")]
		if len(fname) != 1:
			print "Illegale Cutlist, uploaden nicht möglich."
			return
		fname = fname[0][len("ApplyToFile="):].strip()
		
		print fname
		print
		print cutlist
		print
		print "Hochladen noch nicht implementiert."
	
	#
	# getView
	#
	def getView(prov, path):
		filename = os.path.basename(path)
		
		class View:
			def __init__(self):
				self.cutlists = prov.getCutlists(filename)
				print "%d Cutlist(s) gefunden" % len(self.cutlists)

				for i, cutlist in enumerate(self.cutlists):
					print "[%2d] Cutlist: %s" % (i+1,cutlist[0])
				print "[ n] neue Cutlist erstellen"

			def getCutlist(self, inp, **kwargs):
				if inp.strip() == 'n':
					cutlist = prov.createCutlist(path)
					if cutlist:
						self.cutlists.append( ('neu erstellt', cutlist) )
						print "[%2d] Cutlist: %s" % (len(self.cutlists),self.cutlists[-1][0])
					return cutlist
				else:
					try:
						i = int(inp)-1
						if 0 <= i < len(self.cutlists):
							return self.cutlists[i][1]
						else:
							print "Illegaler Index."
							return None
					except:
						print "Illegale Eingabe."
						return None
		return View()

	#
	# upload cutlist
	#
	def PostProcessCutList( self, cl_id ):
		print "Hochladen von Cutlists noch nicht implementiert."
		return
		
		
		attr = [	# display				internal  			default
					['Autor',  				'Author', 			self.cutoptions.author],
					['Ihre Bewertung', 	'RatingByAuthor', 	''],
					['Kommentar',			'UserComment',		''],
					['Filmnamensvorschlag', 'SuggestedMovieName',''],
				]
		
			
		sys.stdout.write("Cutlist hochladen [J/n]: ")
		sys.stdout.flush()
		s = sys.stdin.readline().strip()
		if 'n' in s.lower():
			return
		
		print
		
		while True:
			for did in attr:
				display, _, default = did

				sys.stdout.write("%s[%s]: " % (display, default))
				sys.stdout.flush()
				s = sys.stdin.readline().strip()
				if s.lower() == 'clear':
					did[2] = ''
				elif s:
					did[2] = s
			
			infotxt = \
				'[Info]\n'\
				+ ''.join( ["%s=%s\n" % (internal, default) for _, internal, default in attr] ) \
				+ 'EPGError=%s\n' % ""\
				+ 'ActualContent=%s\n' % ""\
				+ 'MissingBeginning=%s\n' % ""\
				+ 'MissingEnding=%s\n' % ""\
				+ 'MissingAudio=%s\n' % ""\
				+ 'MissingVideo=%s\n' % ""\
				+ 'OtherError=%s\n' % ""\
				+ 'OtherErrorDescription=%s\n' % ""
			
			print
			print "Cutlist Infotext:"
			print infotxt
			print
			
			sys.stdout.write("Cutlist annehmen [J/n]: ")
			sys.stdout.flush()
			s = sys.stdin.readline().strip()
			if 'n' in s.lower():
				continue
			else:
				break
			
		self.UploadCutList("%s\n%s" % (cl_id, infotxt))


#
# CutListFileProvider
#
class CutListFileProvider:
	def __init__(self, cutoptions):
		self.cutoptions = cutoptions
		self.desc = "Cutlists von der Festplatte benutzen."
	
	def GetCutList(self, cl_id):
		Debug(2, "CutListFileProvider::GetCutList: %s" % cl_id)
		return open(cl_id).read()

	#
	# getView
	#
	def getView(prov, path):
		class View:
			def __init__(self):
				print "[  ] Dateipfad eingeben."
			
			def getCutlist(self, inp, **kwargs):
				if os.path.isfile(inp):
					return CutList(prov,cutlist_dict={'id':inp})
				else:
					print "'%s' ist keine gültige Datei." % inp
					return None
		return View()

	#
	# noop
	#
	def PostProcessCutList( self, cl_id ):
		pass
#
# CutListGenerator
#
class CutListGenerator:
	def __init__(self, cutlistprov):
		self.cutlistprov = cutlistprov
	
	def makeCutList(self, filename):
		self.filename = filename
		self.basename = os.path.basename(filename)
		self.tmpname = "%s_own_project.js" % random.getrandbits(32)
		self.tmppath = self.cutlistprov.cutoptions.tempdir + self.tmpname
		self.cutlistfile = self.cutlistprov.cutoptions.tempdir+self.basename+'.cutlist'
		self.writePreAvidemuxProject()
		
		#
		# start avidemux
		#

		print "%s Starte Avidemux. Das Projekt muss manuell gespeichert werden und Avidemux beendet. %s" % (C_RED, C_CLEAR)
		cmdoptions = ["--force-smart", "--run", self.tmppath]
		if self.cutlistprov.cutoptions.aviDemux_saveWorkbench:
			cmdoptions += ["--save-workbench", self.tmppath]
		out, err = Run(self.cutlistprov.cutoptions.cmd_AviDemux_Gui, cmdoptions)
		
		#
		# post processing
		#
		try:
			project = open(self.tmppath, 'r').read()
		except:
			print "Keine Datei gespeichert!"
			return None
		if not "app.addSegment" in project:
			print "Keine Schnitte angegeben!"
			return None
		
		self.numberOfCuts = len(project.split("app.addSegment"))-1
		if "app.video.fps1000" in project:
			grapFPS = project.split("app.video.fps1000")[1].split('=')[1].split(';')[0].strip()
		else:
			grapFPS = project.split("app.video.setFps1000")[1].split('(')[1].split(')')[0].strip()
		self.FPS = float(grapFPS)*0.001
		
		#
		# writing cutlist to self.cutlistfile
		#
		cutlist = self.generateCutList(project.split("app.addSegment(0")[1:])
		Debug(3, "Created cutlist:\n"+cutlist)
		open(self.cutlistfile, "w").write(cutlist)
		
		#
		# buidling cutlist
		#
		return cutlist
	
	def writePreAvidemuxProject(self):
		pstr = '//AD\n'\
			+ 'var app = new Avidemux();\n'\
			+ 'app.load("%s");\n' % self.filename
		open(self.tmppath, "a").write(pstr)
	
	def generateCutList(self, segments):
		cstr = '[General]\n'\
			+ 'Application=multicut_evolution.py\n'\
			+ 'Version=%s\n' % multicut_evolution_date\
			+ 'comment1=Diese Cutlist unterliegt den Nutzungsbedingungen von cutlist.at (Stand: 14.Oktober 2008)\n'\
			+ 'comment2=http://cutlist.at/terms/\n'\
			+ 'ApplyToFile=%s\n' % self.basename\
			+ 'OriginalFileSizeBytes=%s\n' % os.path.getsize(self.filename)\
			+ 'FramesPerSecond=%s\n' % self.FPS\
			+ 'IntendedCutApplication=Avidemux\n'\
			+ 'IntendedCutApplicationVersion=2.5\n'\
			+ 'IntendedCutApplicationOptions=\n'\
			+ 'CutCommandLine=\n'\
			+ 'NoOfCuts=%s\n' % self.numberOfCuts

			
		for cut, segment in enumerate(segments):
			start    = segment.split(',')[1]
			duration = segment.split(',')[2].split(')')[0]
			cstr += '[Cut%s]\n' % cut\
				+ 'Start=%f\n' % (float(start)/self.FPS) \
				+ 'StartFrame=%s\n' %start\
				+ 'Duration=%f\n' % (float(duration)/self.FPS) \
				+ 'DurationFrames=%s\n\n' % duration
		
		return cstr

		

#
# CutOptions Class
#
class CutOptions:
	def __init__(self, configfile = None):
		# init values
		self.tempdir = tempfile.mkdtemp(prefix = "multicut_evolution")
		self.cutdir  = os.getcwd()
		self.uncutdir= os.getcwd()
		self.cachedir= os.path.expanduser("~/.cache/multicut_evolution/")
		self.author  = "Mr Wayne"
		
		self.cmd_VirtualDub = None
		self.cmd_AviDemux_Gui = "avidemux2_qt4"
		self.aviDemux_saveWorkbench = True
		
		self.cutnameformat = "{base}-cut{rating}.{ext}"
		self.uncutnameformat = "{full}"

		self.time_before_cut = 10
		self.time_after_cut  = 5
		
		self.do_rate = 1

		# parse
		if configfile:
			print "Parse Konfigurationsdatei: %s" % configfile
			self.ParseConfig(configfile)

		# enforce ending seperator
		if not self.tempdir.endswith(os.sep):  self.tempdir  += os.sep
		if not self.cutdir.endswith(os.sep):   self.cutdir   += os.sep
		if not self.uncutdir.endswith(os.sep): self.uncutdir += os.sep
		if not self.cachedir.endswith(os.sep): self.cachedir += os.sep
		# enforce existance
		dirs = [self.cutdir,self.uncutdir,self.cachedir]
		for d in dirs:
			if not os.path.exists(d):
				Debug(4, "init: create directory: %s" % d)
				os.makedirs(d)
				
		# find avidemux
		for avidemux in avidemux_cmds:
			try:
				out = Run(avidemux, ["--quit"])[0]
				self.cmd_AviDemux = avidemux
				if "Avidemux v2.5" in out:
					self.cmd_AviDemux_version = "2.5"
					break
				elif "Avidemux v2.4" in out:
					self.cmd_AviDemux_version = "2.4"
					break
				else:
					continue # do not use
			except OSError:
				pass # not found
		else:
			raise RuntimeError("avidemux not found")
		
		print "Benutze als temp-Verzeichnis: %s" % self.tempdir
		print "Benutze als cut-Verzeichnis: %s" % self.cutdir
		print "Benutze als uncut-Verzeichnis: %s" % self.uncutdir
		print "Benutze als cache-Verzeichnis: %s" % self.cachedir
		print "Benutze als cutnameformat: %s" % self.cutnameformat
		print "Benutze als uncutnameformat: %s" % self.uncutnameformat
		print "Benutze als AviDemux: %s (v:%s)" % (self.cmd_AviDemux, self.cmd_AviDemux_version)
		print "Benutze als VirtualDub: %s" % self.cmd_VirtualDub
		
		self.cutlistprovider = {
								'internet': CutListAT(self),
								'own': 		CutListOwnProvider(self),
								'file':		CutListFileProvider(self),
							}
		self.defaultprovider = 'internet'

		self.DefaultProjectClass = AviDemuxProjectClass
		self.RegisteredProjectClasses = {}
		if self.cmd_VirtualDub:
			self.RegisteredProjectClasses[".mpg.HQ.avi"] = VDProjectClass
			self.RegisteredProjectClasses[".mpg.HD.avi"] = VDProjectClass
		
		
	def ParseConfig(self, config):
		config = os.path.expanduser(config)
		Debug(1, "CutOptions::ParseConfig: open config '%s'" % config)
		try:
			for line in open(config):
				if not line.strip():
					continue
				try:
					cmd, opt = line.split("=",1)
					cmd, opt = cmd.strip(), opt.strip()
					Debug(2, "CutOptions::ParseConfig: config read:'%s' = '%s'" % (cmd,opt))
					if cmd == "cutdir":
						self.cutdir  = os.path.expanduser(opt)
					elif cmd == "uncutdir":
						self.uncutdir= os.path.expanduser(opt)
					elif cmd == "virtualdub":
						self.cmd_VirtualDub = os.path.expanduser(opt)
					elif cmd == 'avidemux_gui':
						self.cmd_AviDemux_Gui = os.path.expanduser(opt)
					elif cmd == 'avidemux_saveworkbench':
						self.aviDemux_saveWorkbench = (opt=='True' or opt=='1')
					elif cmd == "cachedir":
						self.cachedir= os.path.expanduser(opt)

					elif cmd == "cutname":
						self.cutnameformat = opt
					elif cmd == "uncutname":
						self.uncutnameformat = opt
					elif cmd == "vorlauf":
						self.time_before_cut = int(opt)
					elif cmd == "nachlauf":
						self.time_after_cut  = int(opt)
					elif cmd == "bewerten":
						self.do_rate = int(opt)
					elif cmd == "autor":
						self.author = opt
					
				except StandardError, e:
					print "ConfigParse: Could not parse '%s' due to:" % line
					print e
		except:
			pass
	
	def FormatString(self, name, data):
		if name == "cutname" or name == "uncutname":
			cutlist, filename = data
			format = {}
			# cutlist relevant
			format["rating"] = str(int(100*float(cutlist["rating"])+0.5)) if "rating" in cutlist and cutlist["rating"] else ''
			format["metarating"] = str(int(100*float(cutlist["metarating"])+0.5))
			#filename relevant
			format["full"] = filename
			format["base"], format["shortext"] = filename.split(".mpg.")
			format["ext"] = 'mpg.%s' % format["shortext"]
			if name == "cutname":
				return self.cutnameformat.format(**format)
			else:
				return self.uncutnameformat.format(**format)
			
		raise ValueError("'%s' is not valid" % name)


#
# CutFile Class
#
class CutFile:
	def __init__(self, path, cutoptions):
		self.path = os.path.realpath(path)
		self.cutoptions = cutoptions
		
		self.filename = os.path.basename(path)
	
	def ChooseCutList(self):
		print 
		print "	%s %s %s" % (C_RED, self.filename, C_CLEAR)
		print 

		self.currentprov = None
		self.cutlist = None
		
		while not self.cutlist:
			if not self.currentprov:
				self.currentprov = self.cutoptions.cutlistprovider[self.cutoptions.defaultprovider].getView(self.path)
				
			print "Auswahl/Test: ",
			inp = sys.stdin.readline().strip()
			print
			
			if not inp:
				print "Datei wird nicht geschnitten"
				return False
			
			doTest = False
			
			# consume input string
			while inp.strip():
				inp = inp.lstrip()
				
				for prov in self.cutoptions.cutlistprovider.keys():
					if inp.startswith(prov.lower()):
						inp = inp[len(prov):]
						
						print "Providerwechsel nach '%s'" % prov
						self.currentprov = self.cutoptions.cutlistprovider[prov].getView(self.path)
						break
				else:
					if inp.lower().startswith('test'):
						doTest = True
						inp = inp[len('test'):]
					else:
						data, _, inp = inp.partition(' ')
						self.cutlist = self.currentprov.getCutlist(data, currentcutlist = self.cutlist)
			
			if doTest:
				if self.cutlist:
					self.cutlist.ShowCuts(self.path, is_filecut = False, tempdir = self.cutoptions.tempdir)
					self.cutlist = None
				else:
					print "Keine Cutlist angegeben zum Testen!"

		return True


	def Cut(self):		
		self.cutname = self.cutoptions.FormatString("cutname",   (self.cutlist, self.filename))
		self.tmpname = "$$$$-" + self.cutname 
		self.uncutname = self.cutoptions.FormatString("uncutname", (self.cutlist, self.filename))
		
		self.cutpath = self.cutoptions.cutdir + self.cutname
		self.tmppath = self.cutoptions.cutdir + self.tmpname
		self.uncutpath = self.cutoptions.uncutdir + self.uncutname

		print "%s Schneide %s %s" % (C_RED, self.filename, C_CLEAR)
		print "Ausgabename: %s" % self.cutname
		
		
		for extension, registeredclass in self.cutoptions.RegisteredProjectClasses.items():
			if extension in self.filename:
				projectclass = registeredclass
				break
		else:
			projectclass = self.cutoptions.DefaultProjectClass
		
		project = projectclass(self, self.cutlist, self.cutoptions)
		
		print "Schneide mit %s" % project.Name()
		print "Framerate: %g fps" % self.cutlist.GetFPS()
		
		start = time.time()
		project.Run() # run
		end = time.time()
		print "Fertig, benötigte Zeit: %ds" % int(end-start)
			
		if os.path.isfile(self.tmppath):
			shutil.move(self.path, self.uncutpath)
			shutil.move(self.tmppath, self.cutpath)
			return True
		else:
			print "Schneiden war nicht erfolgreich"
			return False
	
	def ShowCut(self):		
		print "%s Prüfe %s %s" % (C_RED, self.filename, C_CLEAR)
		print "Schnitte mit mplayer zeigen -> Eingabetaste [Überspringen mit 'n']"
		inp = sys.stdin.readline().strip()
		if inp != 'n':
			self.cutlist.ShowCuts(self.cutpath, is_filecut = True, tempdir = self.cutoptions.tempdir)		
			self.cutlist.PostProcessCutList()
		
		print
		sys.stdout.write("Annehmen? [J/n]: ")
		sys.stdout.flush()
		s = sys.stdin.readline().strip()
		if 'n' in s.lower():
			sys.stdout.write("Sind Sie sicher, dass die geschnitte Datei gelöscht werden soll? [J/n]")
			sys.stdout.flush()
			s = sys.stdin.readline().strip()
			if not 'n' in s.lower():
				print "%s Lösche %s %s" % (C_RED, self.cutpath, C_CLEAR)
				try:	os.remove(self.cutpath)
				except: pass # doesn't matter
				shutil.move(self.uncutpath, self.path)
					
	def GetAspect(self):
		out = Run("mplayer",  ["-vo", "null", "-nosound", "-frames", "1", self.path])[0]
		if "Movie-Aspect is 1.33:1" in out or "Film-Aspekt ist 1.33:1" in out:
			return "4:3"
		if "Movie-Aspect is 0.56:1" in out or "Film-Aspekt ist 0.56:1" in out:
			return "16:9"
		if "Movie-Aspect is 1.78:1" in out or "Film-Aspekt ist 1.78:1" in out:
			return "16:9"
		return "4:3"
		

#
# AviDemuxProjectClass
#
class AviDemuxProjectClass:
	def __init__(self, cutfile, cutlist, cutoptions):
		self.cutoptions = cutoptions
		self.filename = self.cutoptions.tempdir + "%d_project.js" % random.getrandbits(32)

		self.Start(cutfile.path)
		
		StartInFrames, DurationInFrames = cutlist.TimesInFrames()
		for start, duration in zip(StartInFrames, DurationInFrames):
			self.Append("app.addSegment(0,%d,%d);" % (start, duration))
		
		self.End(cutfile.tmppath, cutoptions.cmd_AviDemux_version, cutlist.GetFPS())

	def Name(self):
		return "Avidemux"
	
	def Write(self, text, mode = "a"):
		open(self.filename, mode).write(text)
	
	def Start(self,path):
		text = 	'//AD\n' \
			 +	'var app = new Avidemux();\n' \
			 +	'//** Video **\n' \
			 +	'// 01 videos source\n' \
			 +	'app.load("%s");\n' % path \
			 + 	'\n' \
			 +	'// 02 segments\n' \
			 +	'app.clearSegments();\n'
		self.Write(text,"w")
	
	def Append(self, append):
		self.Write(append + "\n")
	
	def End(self,tmppath,version,fps):
		if version == "2.5":
			text = 	'app.video.setPostProc(3,3,0);\n' \
				+	'app.video.fps1000=%d;\n' % (fps*1000) \
				+	'app.video.codec("Copy","CQ=4","0 ");\n' \
				+	'app.audio.reset();\n' \
				+ 	'app.audio.codec("copy",128,0,"");\n' \
				+	'app.audio.normalizeMode=0;\n' \
				+	'app.audio.normalizeValue=0;\n' \
				+	'app.audio.delay=0;\n' \
				+	'app.audio.mixer="NONE";\n' \
				+	'app.audio.scanVBR="";\n' \
				+	'app.setContainier="AVI";\n' \
				+ 	'setSuccess(app.save("%s"));\n' % tmppath
		else:
			text = 	'app.video.setPostProc(3,3,0);\n' \
				+	'app.video.setFps1000(%d);\n' % (fps*1000) \
				+	'app.video.codec("Copy","CQ=4","0 ");\n' \
				+	'app.audio.reset();\n' \
				+ 	'app.audio.codec("copy",128,0,"");\n' \
				+	'app.audio.normalizeMode=0;\n' \
				+	'app.audio.normalizeValue=0;\n' \
				+	'app.audio.delay=0;\n' \
				+	'app.audio.mixer("NONE");\n' \
				+	'app.audio.scanVBR();\n' \
				+	'app.setContainer("AVI");\n' \
				+ 	'setSuccess(app.save("%s"));\n' % tmppath
		self.Write(text,"a")
	
	def Run(self):
		Debug(1, "starting avidemux")
		return Run(self.cutoptions.cmd_AviDemux, ["--force-smart", "--run", self.filename, "--quit"])

#
# VDProjectClass
#
class VDProjectClass:
	def __init__(self, cutfile, cutlist, cutoptions):
		self.cutoptions = cutoptions
		self.projectname = "%d_project.syl" % random.getrandbits(32)
		self.filename = self.cutoptions.tempdir + self.projectname
			
		self.Start(cutfile.path)
			
		self.SetAspectRatio(cutfile.GetAspect())
			
		self.Append("VirtualDub.subset.Clear();")
		StartInFrames, DurationInFrames = cutlist.TimesInFrames()
		for start, duration in zip(StartInFrames, DurationInFrames):
			self.Append("VirtualDub.subset.AddRange(%d,%d);" % (start, duration))
			
		self.End(cutfile.tmppath)

	def Name(self):
		return "VirtualDub"
		
	def Write(self, text, mode = "a"):
		open(self.filename, mode).write(text)

	def Start(self, path):
		text = 	'VirtualDub.Open("%s",0,0);\n' % path \
			 +	'VirtualDub.audio.SetMode(0);\n' \
			 +	'VirtualDub.video.SetMode(1);\n' \
			 +	'VirtualDub.video.SetSmartRendering(1);\n' \
			 +	'VirtualDub.video.SetCompression(0x53444646,0,10000,0);\n'
		self.Write(text, "w")
		
	def Append(self, append):
		self.Write(append + '\n')
	
	def SetAspectRatio(self, ratio):
		# old:
		#text = 'VirtualDub.video.SetCompData(2853,"AAcoDAIAAAApDB8AAAAqDAAAAAArDH0AAAAslQAthQIulQAvlQAwlQAxlAAGMgwABAAAMwwyXQU0lQA1lAAENgwDAAAAN4wECjgMEAAAADkMZAAAADqVADudAjyVAD2VAD6VAD+VAECVAEGXAEIMFF0RQ5UARJQABEUMECcAAEaVAEeNBEqUAApLDICWmABMDDwAAABNlQBOnwJPDApLGlAMHk8QUQwZTRBShwJTDPpNFlSMBARVDAEAAABWlwBXDPRTAVgMWl0FWYUCWo0HW50aXIUCXY0BXo0HX5UAYJQABGEM/P///2KPAWMMB10LZI8BZQxGXQtmjQFnlQBolQBplQBqlQBrlQBslQBtlSRujQ15lQB8nAIEfQxSR0IykY0BkpUAlZUAlp0FmIwBAFHIDAgREhPJDBUXGRvKDBESExXLDBcZGxzMDBQVFhfNDBgaHB7ODBUWFxjPDBocHiDQDBYXGBrRDBweICPSDBcYGhzTDB4gIybUDBkaHB7VDCAjJinWDBscHiDXDCMmKS3YDBBdC9mVCdp+CxTblAkE3AwSExQV3XQJARneDBNRDd92CRvghAUE4QwZGhsc4oQFBOMMGhscHuRmBRrlZAsLH+YMFxgZG+cMHB4fIeiUGATpDFlWMTLsjAEE7QwgAwAA7o0B75UA8JUA8ZUA8pUA85UA9I0l9ZcA9wwTXTj4n1D5DAhdPvqfAvsMBUVE/Z0F/pQAAf8MoA9IAgQNuAsAAAENUgYAApYAAw1ARwEABA1QUQMFhQIGhQIHlQAIlAAECQ0AAgAACo0BC5UADIYFDQ1sXgQODRAQEBAPlQAQlQARlQASlQATlQAUlQAVlQAWlQAXlQAYlQAZlQAalQAblQAclQAdlQAehQ4flQAglgAhDX5cIg1hGiSFAiWdESaMAQUnDf////8tDWRidB0OAAC5C4QDAAC6C5CyCAC7CwJEVgACvAtVAAAAvQtsBwAAvgtIMjY0vwtmZcALZiPBC20iwpUAw5UAxJUAxZUAxo0Ex5UAyIUCyZUAypQACssLgD4AAMwL+CoAAM2NBM6VAM+VA9CWANELfz7SCwZVftOFAtSVANWWANYLbTHXlQbYhQLZnQXajQHblQDclQPdjQHflQDglQDilAAK4wuoYQAA5AvoAwAA5YUF5pUA55UD6JUA6ZUA6p0C640B7JUA7ZUA7pcA7wsEQSHwjQHxhQXyjQHzlQD0lgP1C3ZO9gt9TfecAgT4CwAAigL5nQX6hQL7jQH8jAEE/QsAPwAA/o4BIAxtMSGMsgQiDLD///8jjVUknQIlnQImjQEnjAEACbjz//5cAHYAaQBkAGUAbwAuAHMAdABhAHQAc12wty13AGcAay2EAAUi9P/+AAAf9C4XAWYAZiskAVKiGQBiQUYAYbxHjQFhlQBiQyIAAGONAXyUAAR9ANwFAAB+jwF/AF5ZBoCOAYIAYVAJfqMACpUAC5UAbpYAbwdoZwVwBwAIAABxB1IGAHKFAnOFAjJ0KQUAMwUgAQAAWW4kAFqUAAAPf////m0AcABsAGEAeQBlAHIAYwAuAGUAeABlADsAAADIlQTJlQDKlQDLlQDMlQDNlQDOlQDQlgDRAmUP6I0B6ZUA6pUA8J4C8gJhaf2GAnkFWgsAepYAewVqAn8FbSOBhQKGlwCIBf9FJ4meAooFZguMBW0gjZUDjpUAj5UAkJUAkY4EkgVtPpOFApSWAHz6eTR7lQCrhQKshQWtlQCuhgKvBWHtsJ4LsQVtKbKVALONE7SGBbUFagW2BXpstwV6LrgFcVW5lQO6lQC7lQC8lQC9nAUEvgX///8Av2oHAD+OEGUAZQhmYiAAZ5UAaJUAapUAa5UAbWekAG4AaT9vhQJwlQBylgBzAGP8dAAoUY51hQJ3lQB4egUAeY0Be5cAyQCAUbjKjQHLlwDMAEBVBs2OAc4AdR7PlVLVhQLWhQLXlQDYlQDZjQralQPblgDcAGUa3Z0C3oUC35UA4JUAf298AIAEfjWBBHEBgo0Bg2gBBQCEBHgAAABBYyAAQgZxIkONAUSWAEUGfxFGBv9Zb0eFAkiNAUmNAUqWAEsGZQtMjQFNlQBOjQRPjgFQBm1JUY0BUpUAU5UDVJUAVYUCVpUAV5UAWJUAWZUAWpUAW5UAXJUAXZUAXpUAX5UAYJUAYZUAYpUAY5UAZJUATY4cTgRxAU+NAVCVAFGVAFKVAFOVAFSVAFWVAFadI1eNAViVAFmWAIUDYiqGA3LThwN9TYiFAomVAIyVAI2WAJADbiKRA3xBBZMDvAIAAJQDdoiVA2HWmY0EmpUAm5UAnJ0FnYwBBJ4DLAEAAJ+OAaADegChA3cwogOWWcmjYAIFAKQDkAEAAKWEBQSmA1gCAACnnQKonQipjQGRaxAAkgFmU5MBbgeUAX0RlZ0ClpYAlwF9ZZiOAZ0BdgyeAXHun4UCoJcApwHIWh6oAWUOqYUCqpYAqwF5AKxzAAC4ASLpLLmVAKOXDKQBgE1Gr5cDsAEJTUyxjQGylAAEswFABgAAtJ4FtQFlRLadAreNAbqFC7uFApljFACaCH2Mm44BnghhA5+OAWT3ZYljlQD1egIA9o4H9wFuNPgBdQb5jwr6AQtVJ/uNBP6NBP+NAQCEoYoEAAJjEQADAm0ZBI4BBQJ6DAYCfQgHhwIIAn9NGQmNBAqFAguFAgyVAA2WADQNaQu9lwO+AoBVM7+NAcCMDQTBAuABAADCkA0EwwJ6VAEAxJUDxZUAxpUAx5cA0gIMTRbTjQHUlQDWlQDXlQDYlgDZAmpT2gJpPtudC92dAt6PAd8CgFUB4I8B4QLgXQ7ijQHjlAAE5AIAsAQA5UcEAADmlQDnnQLsjAEK7QJ+BAAA7gK2AwAA75wCBPEC0AcAAPONAfSNBPWVAPaVAPeFGviNAfmVAPqVAPueBfwCbbgDYkEABJYABQl9TQaVAAeVAAidAgmWAAoJbSgLjQH9czAA/ggi9Sf/lT8AnAKaSgACjQchYyAAKgNuNysDItkzLIQCBC0D6AMAAC6fYi8DDk03MY0BOZUAO40EPI0BPoUFQYUCQpUAQ50CRI4BRQN9LEaFcUeFAkiVAEmNBEqdekuNfEydg06VA0+VAFGWAFIDYbRTlYFUhQJVhQJXjQFanQhclgDL/HVasJUAIoQCBCMDGgAAACSNByWNHCaVACiOBykDfb83jgE4AyLpOD2NAT+NB0CNFlaFAi6GUy8NYyowDbRMCgrM/P/+QQByAGkAYQBsVU3jexwA5AR1gOWOAecEZTHolQDplQDqlQDrlQDslQDthQXulgDvBHVl8JYAGvtlGbGeArIEZUCznQW0hQK1lQC2hQLDcAwBAMQBEU3hxY4BxgFlN8eVAMiVAMmVAMqVAMuXAMwB9F2gzZ4FzgF5AM9yAADQlgDRAX7Z0gEiqDcL0wEUFRYX1AEREhMU1QEi4jjWASKoNwXXARYXGBnYASKoNwTZARcYGhvahgXbASKpN9yGBd0BIqk33mQFBhrfARscHh/gASKqN+EBIqk3c3LLAHSX4HUGEk0qdoYCeAZtUXmVAHqFAnuN4XyPAX0GgE5Rifl9I9FoyQEA0gcTXS/TjgHWB2UX144B2AdxGdmOAdoHb2bbB25WDNwHIhkx3ZUD3pQABiz4//5jADoAXFwIAiv4//5nXzphAGJFKi1qCAAVIxUkFpUAF5UAGJUAGZUAGpUAG5UAHJUAHXIQACUjxSUmjQFGjQFHjQFIjQFJjQFKnQVLjQFMjQFOjQFPjAQJUAUAAAAAUQUAAAAAEQAA");\n'
		#text = 'VirtualDub.video.SetCompData(2847,"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");\n'
		# current source:
		# http://github.com/elbersb/otr-verwaltung/blob/master/otrverwaltung/codec.py#L14
		if ratio == "16:9":
			self.Append('VirtualDub.video.SetCompData(2952,"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");')
		else:
			self.Append('VirtualDub.video.SetCompData(2951,"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");')

	def End(self, cutpath):
		text =	'VirtualDub.SaveAVI("%s");\n' % cutpath \
			 +	'VirtualDub.Close();\n'
		self.Write(text)

	def Run(self):
		os.chdir(self.cutoptions.tempdir)

		Debug(1, "starting vd")
		
		sub = subprocess.Popen(args = "wine %s /x /s %s" % (self.cutoptions.cmd_VirtualDub,self.projectname),
											shell = True, stderr = subprocess.PIPE, stdout = subprocess.PIPE)
		
		errtext = ''
		while True:
			if sub.poll() != None:
				break
			
			adderrtxt = sub.stderr.read(1)
			if adderrtxt == '\n':
				Debug(4, errtext.rpartition('\n')[-1])
			errtext += adderrtxt
			if 'fixme:avifile:AVIFileExit' in errtext:
				sub.send_signal(9) # python >=2.6
				break


def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "h", ["help", "nocheck","config=","verbosity="])
	except getopt.GetoptError, err:
		print C_RED + str(err) + C_CLEAR # will print something like "option -a not recognized"
		print prog_help
		sys.exit(2)
	
	check_cut_files = True
	configfile = "~/.multicut_evolution.conf"

	for o, a in opts:
		if o in ("-h", "--help"):
			print prog_help
			sys.exit()
		elif o in ("--nocheck",):
			check_cut_files = False
		elif o in ("--config",):
			configfile = a
		elif o in ("--verbosity",):
			global VERBOSITY_LEVEL
			VERBOSITY_LEVEL = int(a)
			print "Setze verbosity auf %d" % VERBOSITY_LEVEL
	
	if not args:
		print C_RED + "Fehler: Keine Dateien übergeben" + C_CLEAR
		print
		print prog_help
		sys.exit()
	
	o = CutOptions(configfile)


	###
	# choose cutlists
	###
	avis = []
	for avi in args:
		if not avi.endswith(".avi"):
			print "Non-Avi Datei ausgelassen: %s" % avi
			continue
		else:
			avis.append(avi)
	
	avis.sort()
	avis2Choose = avis
	cutfiles = {}
	
	print
	print
	print "%s Cutlists auswählen für insgesamt %d Datei(en): %s" %(C_RED_UNDERLINE, len(avis), C_CLEAR)
	print
	print "Verfügbare Provider:"
	for key, value in sorted(o.cutlistprovider.items(), key=lambda x:x[0]): #sort by name
		std = " [default]" if key == o.defaultprovider else ""
		print "  %s - %s%s" % (key,value.desc,std)
	print
	print
	
	
	while avis2Choose:
		# choose
		print
		print
		print "%s Cutlists auswählen für %d Datei(en): %s" %(C_RED, len(avis2Choose), C_CLEAR)
		print
		
		for avi in avis2Choose:
			c = CutFile(avi, o)
			if c.ChooseCutList():
				cutfiles[avi] = c
			else:
				if avi in cutfiles:
					del cutfiles[avi]
		print
		print
		print "%s Cutlists umwählen: %s" %(C_RED, C_CLEAR)
		print
		# confirm selection
		for i,avi in enumerate(avis):
			aviname = os.path.basename(avi)
			cut = 'x' if avi in cutfiles else ' '
			print "[%2d] %s %s" % (i+1,cut,aviname)
		print "[ a] alle neu wählen"
		print "[ n] oder leere Eingabe: nichts neu wählen und anfangen zu schneiden"
		
		avis2Choose = None
		while True:
			sys.stdout.write("Auswahl(1,1-3,1-2-9): ")
			sys.stdout.flush()
			s = sys.stdin.readline().strip()
			if not s or 'n' in s:
				break
			elif 'a' in s:
				avis2Choose = avis
				break
			else:
				try:
					iis = ParseIIRange(s)
					iis = sorted(list(set(iis)))
					iis = [i-1 for i in iis]
					if not (0 <= min(iis) and max(iis) < len(avis)):
						print "%sIhre Eingabe ist fehlerhaft, versuchen Sie es erneut.%s" %(C_RED,C_CLEAR)
						continue
					avis2Choose = [avis[i] for i in iis]
					break
				except:
					print "%sEin Fehler ist aufgetreten, versuchen Sie es erneut.%s" %(C_RED,C_CLEAR)
					continue

		
	cutfiles = cutfiles.values()
	
	###
	# cut files
	###
	print
	print
	print
	print
	print "%s Schneide %d Datei(en): %s" %(C_RED_UNDERLINE, len(cutfiles), C_CLEAR)
	print

	checkfiles = []
	errors = []
	
	for i,c in enumerate(cutfiles):
		print
		print "%d von %d" % (i+1, len(cutfiles))
		try:
			if c.Cut():
				checkfiles.append(c)
		except StandardError,e:
			print e
			print "Life has to go on..."
			errors.append( (e,c) )
	
	try:
		if errors:
			for e,c in errors:
				print 70*'#'
				print c.filename
				print e
	except:
		print "Fehler während dem Anzeigen von Fehlern..."
		
	if check_cut_files:
		###
		# show files
		###
		print
		print
		
		checkfiles = [ [f,0] for f in checkfiles ]

		print
		print
		print "%s Schnitte überprüfbar von insgesamt %d Datei(en): %s" %(C_RED_UNDERLINE, len(checkfiles), C_CLEAR)
		print
		print
		
		while checkfiles:
			print
			print
			print "%s Schnitte überprüfen von %d Datei(en): %s" %(C_RED, len(checkfiles), C_CLEAR)
			print
			
			checkfiles.sort( key = lambda (_,n): n )
			filesNeedCheck = [ c_n for c_n in checkfiles if c_n[1] == 0 ]
			
			for i,(c,n) in enumerate(checkfiles):
				aviname = c.filename
				checked = "x" if n > 0 else " "
				print "[%2d] %s %s" % (i+1,checked,aviname)
			if filesNeedCheck:
				print "[ n] keine prüfen und beenden"
				print "[ f] alle überprüfen"
				print "[ a] oder leere Eingabe: alle noch nicht überprüften überprüfen"
			else:
				print "[ f] alle überprüfen"
				print "[ a] beenden"
				
			avis2Check = None
			while True:
				sys.stdout.write("Auswahl(1,1-3,1-2-9): ")
				sys.stdout.flush()
				s = sys.stdin.readline().strip()
				if not s or 'a' in s:
					avis2Check = filesNeedCheck if filesNeedCheck else None
					break
				elif 'f' in s:
					avis2Check = checkfiles
					break
				elif 'n' in s:
					avis2Check = None
					break
				else:
					try:
						iis = ParseIIRange(s)
						iis = sorted(list(set(iis)))
						iis = [i-1 for i in iis]
						if not (0 <= min(iis) and max(iis) < len(checkfiles)):
							print "%sIhre Eingabe ist fehlerhaft, versuchen Sie es erneut.%s" %(C_RED,C_CLEAR)
							continue
						avis2Check = [checkfiles[i] for i in iis]
						break
					except:
						print "%sEin Fehler ist aufgetreten, versuchen Sie es erneut.%s" %(C_RED,C_CLEAR)
						continue
			
			if avis2Check == None:
				break

			for i,c_n in enumerate(avis2Check):
				print
				print
				print "%d von %d" % (i+1, len(avis2Check))
				c_n[0].ShowCut()	
				c_n[1] += 1




if __name__ == '__main__':
	main()
