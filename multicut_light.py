#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import os
import time
import tempfile
import urllib2
import re
import sys
import getopt

C_CLEAR = "\033[0m"
C_RED   = "\033[41;37;1m"
C_BLUE  = "\033[44;37;1m"


multicut_light_date = "12.04.2010"
prog_id = "multicut_light.py/%s" % multicut_light_date
VERBOSITY_LEVEL = 0

prog_help = \
"""
Hilfe für multicut_light.py (%s):

multicut_light.py [--help] [--nocheck] [--verbosity $d] [--config $name] $file1 ...

Die übergebenden Dateien werden geschnitten. Optionen:
	--help
		Zeigt dise Hilfe an

	--nocheck
		Geschnittene Dateien werden nicht zur Überprüfung 
		wiedergegeben.

	--config $name
		Gibt den Namen der zu verwendenden Konfigurationsdatei an.
		[default: ~/.multicut_light.conf]
	--verbosity $d
		Debuginformationen werden entsprechend ausgegeben.
		[default: 0, maximal 5]

In der Konfigurationsdatei zur Verfügung stehenden Einstellungen:
	cutdir= 
		Ausgabepfad [default: .]
	uncutdir=
		Ausgabepfad für alte Dateien [default: .]
	virtualdub=
		Pfad von vdub.exe [default: None]
	vorlauf=
		Vorlauf bei der Überprüfung [default: 10]
	nachlauf=
		Nachlauf bei der Überprüfung [default: 5]
	cutname=
		Ausdruck für Ausgabename (s.u.) [default: {base}-cut{rating}.{ext}]
	uncutname=
		Ausdruck für Ausgabename (s.u.) [default: {full}]

Beschreibung der Sprache für die Namensgebung:
{base}		Dateiname ohne Endung
{ext}		Dateiendung
{shortext}	Dateiendung ohne mpg.
{rating}	Bewertung der Cutlist *100
{full}		Der gesamte Dateiname

Hinweise zur Nutzerinteraktion während der Ausführung:
"Auswahl/Test:" akzeptiert drei Kommandos:
$n:		Wählt die Cutlist $n
test $n:	Zeigt die Schnitte der Cutlist $n an
Nichts:		Überspringt die Datei
""" % multicut_light_date



avidemux_cmds = ["avidemux2_cli", "avidemux_cli", "avidemux2", "avidemux", "avidemux2_gtk", "avidemux_gtk", "avidemux2_qt4", "avidemux_qt4"]


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


class CutList:
	def __init__(self, cutlistprov, cutlist):
		self.cutlistprov = cutlistprov
		#tags: 'id', 'name', 'rating', 'ratingcount', 'author', 'ratingbyauthor', 'actualcontent', 'usercomment', 'cuts', 'filename', 
		# 'filename_original', 'autoname', 'withframes', 'withtime', 'duration', 'errors', 'othererrordescription', 'downloadcount'
		tagvalues = re.findall("<(?P<tag>.*?)>\s*(?P<value>.*?)\s*</(?P=tag)>", cutlist, re.DOTALL) #python is so cool
		self.attr = dict(tagvalues)
		def ToF(a, default):
			try:	return float(a)
			except:	return default
		self.attr["metarating"] = ToF(self.attr['rating'],-1) \
								+ ToF(self.attr['ratingbyauthor'],-1) \
								+ ToF(self.attr['ratingcount'],0)/50 \
								+ ToF(self.attr['downloadcount'],0)/1000

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

	def CutListToText(self, n):
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
		
		outtxt =  "%s\n" % self.attr["metarating"]\
		+ "@RED %s @CLEAR	Schnitte:  @BLUE %s @CLEAR (%s)	Spielzeit: @BLUE %s @CLEAR (hh:mm:ss)\n" % (number, cuts, cutsformat, duration) \
		+ "	Bewertung: @BLUE %s (%s/%s) @CLEAR    	Autor:     @BLUE %s (%s) @CLEAR\n" % (rating, self.attr["ratingcount"], self.attr["downloadcount"], author, self.attr["ratingbyauthor"])\
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
		edlfile = tempdir + filename + ".edl"
		subfile = tempdir + filename + ".sub"
		open(edlfile,"w").write(edl)
		open(subfile,"w").write(sub)
			
		Run("mplayer", ["-edl", edlfile, "-sub", subfile, "-osdlevel", "3", path])
		
		if is_filecut:
			self.Rate()
	
	def Rate(self):
		text =  "\n@RED Bitte eine Bewertung für die Cutlist abgeben... @CLEAR\n"
		text += "[0] Dummy oder keine Cutlist\n"
		text += "[1] Anfang und Ende grob geschnitten\n"
		text += "[2] Anfang und Ende halbwegs genau geschnitten\n"
		text += "[3] Schnitt ist annehmbar, Werbung entfernt\n"
		text += "[4] Doppelte Szenen wurde nicht entfernt oder schönere Schnitte möglich\n"
		text += "[5] Sämtliches unerwünschtes Material wurde framegenau entfernt"
		print text.replace("@BLUE", C_BLUE).replace("@RED", C_RED).replace("@CLEAR", C_CLEAR)

		print "Wertung: ",
		try:
			inp = sys.stdin.readline()[:-1]# without newline
		except StandardError:
			sys.exit()
		inp = inp.strip()
		print
		if inp:
			try:
				i = int(inp)
				if 0 <= i <= 5:
					print u"Sende für Cutlist-ID '%s' die Bewertung %d..." % (self.attr["id"], i),
					print "Antwort: '%s'" % self.cutlistprov.RateCutList(self.attr["id"], i)
			except:
				pass

class CutListAT:
	def __init__(self, cutoptions):
		self.opener = urllib2.build_opener()
		self.opener.addheaders = [ ('User-agent', prog_id)]
		self.cutoptions = cutoptions
		self.CL_Cache = {}
	
	def Get(self, url):
		return self.opener.open("http://www.cutlist.at/" + url).read()
		
	def ListAll(self, filename):
		url = "getxml.php?name=%s&version=0.9.8.0" % filename
		xml = unicode(self.Get(url), "iso-8859-1")
		cutlists = re.findall('<cutlist row_index="\\d">.*?</cutlist>', xml, re.DOTALL)		
		return [CutList(self,cutlist) for cutlist in cutlists]
	
	def GetCutList(self, cl_id):
		if cl_id not in self.CL_Cache:
			Debug(2, "cutlist: cache miss: %s" % cl_id)
			url = "getfile.php?id=%s" % cl_id
			self.CL_Cache[cl_id] = unicode(self.Get(url), "iso-8859-1")
		else:
			Debug(2, "cutlist: cache hit: %s" % cl_id)
		return self.CL_Cache[cl_id]
	
	def RateCutList(self, cl_id, rating):
		Debug(2, "rate cutlist %s with %d" % (cl_id, rating))
		url = "rate.php?rate=%s&rating=%d" % (cl_id, rating)
		return self.Get(url)
		
class CutOptions:
	def __init__(self, class_cutlistprov, configfile = None):
		self.cutlistprov = class_cutlistprov(self) #init prov

		# init values
		self.tempdir = tempfile.mkdtemp(prefix = "multicut")
		self.cutdir  = os.getcwd()
		self.uncutdir= os.getcwd()

		self.cmd_VirtualDub = None

		self.cutnameformat = "{base}-cut{rating}.{ext}"
		self.uncutnameformat = "{full}"

		self.time_before_cut = 10
		self.time_after_cut  = 5

		if configfile: # parse
			print "Parse Konfigurationsdatei: %s" % configfile
			self.ParseConfig(configfile)


		if not self.tempdir.endswith(os.sep):  self.tempdir  += os.sep
		if not self.cutdir.endswith(os.sep):   self.cutdir   += os.sep
		if not self.uncutdir.endswith(os.sep): self.uncutdir += os.sep

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
		
		print "Using as temp directory: %s" % self.tempdir
		print "Using as cut directory: %s" % self.cutdir
		print "Using as uncut directory: %s" % self.uncutdir
		print "Using as cutnameformat: %s" % self.cutnameformat
		print "Using as uncutnameformat: %s" % self.uncutnameformat
		print "Using as AviDemux: %s (v:%s)" % (self.cmd_AviDemux, self.cmd_AviDemux_version)
		print "Using as VirtualDub: %s" % self.cmd_VirtualDub
		
		self.DefaultProjectClass = AviDemuxProjectClass
		self.RegisteredProjectClasses = {}
		if self.cmd_VirtualDub:
			self.RegisteredProjectClasses[".mpg.HQ.avi"] = VDProjectClass
			self.RegisteredProjectClasses[".mpg.HD.avi"] = VDProjectClass
		
		
	def ParseConfig(self, config):
		config = os.path.expanduser(config)
		Debug(1, "open config %s" % config)
		try:
			for line in open(config):
				try:
					opt = line.split("=",1)[1].strip()
					if line.startswith("cutdir"):
						self.cutdir  = os.path.expanduser(opt)
					elif line.startswith("uncutdir"):
						self.uncutdir= os.path.expanduser(opt)
					elif line.startswith("virtualdub"):
						self.cmd_VirtualDub = os.path.expanduser(opt)
					elif line.startswith("cutname"):
						self.cutnameformat = opt
					elif line.startswith("uncutname"):
						self.uncutnameformat = opt
					elif line.startswith("vorlauf"):
						self.time_before_cut = int(opt)
					elif line.startswith("nachlauf"):
						self.time_after_cut  = int(opt)
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
			format["rating"] = str(int(100*float(cutlist["rating"])+0.5)) if cutlist["rating"] else ''
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
		

class CutFile:
	def __init__(self, path, cutoptions):
		self.path = os.path.realpath(path)
		self.cutoptions = cutoptions
		
		self.filename = os.path.basename(path)
	
	def ChooseCutList(self):
		print 
		print "	%s %s %s" % (C_RED, self.filename, C_CLEAR)
		print 
		print "Hole Übersicht von cutlist.at..."
		self.cutlists = self.cutoptions.cutlistprov.ListAll(self.filename)
		print "%d Cutlist(s) gefunden" % len(self.cutlists)
		print

		if not self.cutlists:
			return False


		self.cutlists.sort(key =  lambda x: -float(x['metarating']))
		
		
		for i, cutlist in enumerate(self.cutlists):
			print cutlist.CutListToText(i+1)
			
		def InterpreteNumber(s):
			try:
				if 0 <= int(s)-1 < len(self.cutlists):		return int(s)-1
				else:										return None
			except:											return None
		while True:
			print "Auswahl/Test: ",
			inp = sys.stdin.readline().strip()
			print
			if not inp:
				print "Datei wird nicht geschnitten"
				return False

			if inp.lower().startswith("test "):
				show = InterpreteNumber(inp[5:])
				if show == None:
					print "Invalid: %s" % inp
				else:
					self.cutlists[show].ShowCuts(self.path, is_filecut = False, tempdir = self.cutoptions.tempdir)
			else:
				self.choosen = InterpreteNumber(inp)
				if self.choosen != None:
					break
		self.cutlist = self.cutlists[self.choosen]
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
			os.rename(self.path, self.uncutpath)
			os.rename(self.tmppath, self.cutpath)
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
	
	def GetAspect(self):
		out = Run("mplayer",  ["-vo", "null", "-nosound", "-frames", "1", self.path])[0]
		if "Movie-Aspect is 1.33:1" in out or "Film-Aspekt ist 1.33:1" in out:
			return "4:3"
		if "Movie-Aspect is 0.56:1" in out or "Film-Aspekt ist 0.56:1" in out:
			return "16:9"
		if "Movie-Aspect is 1.78:1" in out or "Film-Aspekt ist 1.78:1" in out:
			return "16:9"
		return "4:3"
		

class AviDemuxProjectClass:
	def __init__(self, cutfile, cutlist, cutoptions):
		self.cutoptions = cutoptions
		self.filename = self.cutoptions.tempdir + "project.js"

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

class VDProjectClass:
	def __init__(self, cutfile, cutlist, cutoptions):
		self.cutoptions = cutoptions
		self.filename = self.cutoptions.tempdir + "project.syl"
			
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
		#text = 'VirtualDub.video.SetCompData(2853,"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");\n'
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
		
		sub = subprocess.Popen(args = "wine %s /x /s project.syl" % self.cutoptions.cmd_VirtualDub, shell = True, stderr = subprocess.PIPE, stdout = subprocess.PIPE)
		
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
	configfile = "~/.multicut_light.conf"

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
	
	o = CutOptions(CutListAT, configfile)

	cutfiles = []
	checkfiles = []

	###
	# choose cutlists
	###
	for avi in args:
		if not avi.endswith(".avi"):
			print "Non-Avi file: %s" % avi
			continue
		
		c = CutFile(avi, o)
		if c.ChooseCutList():
			cutfiles.append(c)

	###
	# cut files
	###
	print
	print
	print "Schneide %d Datei(en)" % len(cutfiles)

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
				print e
				print c.filename
	except:
		print "Fehler während dem Anzeigen von Fehlern..."
		
	if check_cut_files:
		###
		# show files
		###
		print
		print
		print "Zeige %d Datei(en)" % len(checkfiles)

		for i,c in enumerate(checkfiles):
			print
			print "%d von %d" % (i+1, len(checkfiles))
			c.ShowCut()


if __name__ == '__main__':
	main()
